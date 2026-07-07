"""
MyCGC 监控 App 主界面（Kivy）。

功能：
- 显示第1档：实时 CGC / WGDC 数量与比例
- 设置刷新间隔分钟数（需求一）
- 设置第2档（低阈值）、第3档（高阈值）（需求二）
- 启动/停止后台前台服务（需求三，息屏也监控）
- 请求通知权限 & 引导用户关闭电池优化，避免系统杀掉后台服务
"""
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView

from config_store import load_config, save_config
from monitor_core import fetch_amounts_and_ratio

SERVICE_ENTRY_NAME = "monitor"  # 对应 buildozer.spec 里 services = monitor:service/main.py


class MyCGCApp(App):
    def build(self):
        self.cfg = load_config()
        self.title = "MyCGC 监控"

        root = BoxLayout(orientation="vertical", padding=16, spacing=10)

        self.status_label = Label(
            text="尚未刷新",
            font_size="18sp",
            size_hint_y=None,
            height=90,
            halign="left",
            valign="middle",
        )
        self.status_label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        root.add_widget(self.status_label)

        form = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        form.add_widget(Label(text="需求一：刷新间隔（分钟，可任意设置）", size_hint_y=None, height=28))
        self.interval_input = TextInput(
            text=str(self.cfg.get("interval_minutes", 5)),
            input_filter="int",
            multiline=False,
            size_hint_y=None,
            height=44,
        )
        form.add_widget(self.interval_input)

        form.add_widget(Label(
            text="需求二 第2档：低阈值（实时比例 < 此值 → 提醒 GDC NOW LOW!）",
            size_hint_y=None, height=44,
        ))
        self.low_input = TextInput(
            text=str(self.cfg.get("low_ratio", 90)),
            input_filter="float",
            multiline=False,
            size_hint_y=None,
            height=44,
        )
        form.add_widget(self.low_input)

        form.add_widget(Label(
            text="需求二 第3档：高阈值（实时比例 > 此值 → 提醒 GDC NOW HAGH!）",
            size_hint_y=None, height=44,
        ))
        self.high_input = TextInput(
            text=str(self.cfg.get("high_ratio", 110)),
            input_filter="float",
            multiline=False,
            size_hint_y=None,
            height=44,
        )
        form.add_widget(self.high_input)

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(form)
        root.add_widget(scroll)

        btn_row1 = BoxLayout(size_hint_y=None, height=56, spacing=8)
        save_btn = Button(text="保存设置")
        save_btn.bind(on_press=self.save_settings)
        refresh_btn = Button(text="立即刷新一次")
        refresh_btn.bind(on_press=self.manual_refresh)
        btn_row1.add_widget(save_btn)
        btn_row1.add_widget(refresh_btn)
        root.add_widget(btn_row1)

        btn_row2 = BoxLayout(size_hint_y=None, height=56, spacing=8)
        start_btn = Button(text="启动后台监控")
        start_btn.bind(on_press=self.start_service)
        stop_btn = Button(text="停止后台监控")
        stop_btn.bind(on_press=self.stop_service)
        btn_row2.add_widget(start_btn)
        btn_row2.add_widget(stop_btn)
        root.add_widget(btn_row2)

        battery_btn = Button(
            text="关闭电池优化（息屏监控必须点这个）",
            size_hint_y=None, height=56,
        )
        battery_btn.bind(on_press=self.request_ignore_battery_optimization)
        root.add_widget(battery_btn)

        self.request_runtime_permissions()
        Clock.schedule_interval(self.refresh_status_label, 5)
        return root

    # ---------- 权限相关 ----------
    def request_runtime_permissions(self):
        try:
            from android.permissions import request_permissions, Permission
            perms = [Permission.INTERNET]
            for name in ("POST_NOTIFICATIONS",):
                p = getattr(Permission, name, None)
                if p:
                    perms.append(p)
            request_permissions(perms)
        except Exception:
            pass

    def request_ignore_battery_optimization(self, instance):
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            Settings = autoclass("android.provider.Settings")
            Uri = autoclass("android.net.Uri")
            activity = PythonActivity.mActivity
            intent = Intent()
            intent.setAction(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
            intent.setData(Uri.parse("package:" + activity.getPackageName()))
            activity.startActivity(intent)
        except Exception as e:
            self.status_label.text = f"请求电池优化白名单失败: {e}"

    # ---------- 设置 ----------
    def save_settings(self, instance):
        try:
            self.cfg["interval_minutes"] = int(self.interval_input.text)
            self.cfg["low_ratio"] = float(self.low_input.text)
            self.cfg["high_ratio"] = float(self.high_input.text)
            save_config(self.cfg)
            self.status_label.text = "设置已保存"
        except Exception as e:
            self.status_label.text = f"保存失败: {e}"

    # ---------- 服务启停 ----------
    def start_service(self, instance):
        self.save_settings(instance)
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            activity = PythonActivity.mActivity
            service_class = activity.getPackageName() + ".Service" + SERVICE_ENTRY_NAME.capitalize()
            intent = Intent()
            intent.setClassName(activity.getPackageName(), service_class)
            activity.startService(intent)
            self.cfg["service_running"] = True
            save_config(self.cfg)
            self.status_label.text = "后台监控已启动"
        except Exception as e:
            self.status_label.text = f"启动失败: {e}"

    def stop_service(self, instance):
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            activity = PythonActivity.mActivity
            service_class = activity.getPackageName() + ".Service" + SERVICE_ENTRY_NAME.capitalize()
            intent = Intent()
            intent.setClassName(activity.getPackageName(), service_class)
            activity.stopService(intent)
            self.cfg["service_running"] = False
            save_config(self.cfg)
            self.status_label.text = "后台监控已停止"
        except Exception as e:
            self.status_label.text = f"停止失败: {e}"

    # ---------- 手动刷新 / 状态展示 ----------
    def manual_refresh(self, instance):
        self.status_label.text = "刷新中..."
        threading.Thread(target=self._do_manual_refresh, daemon=True).start()

    def _do_manual_refresh(self):
        try:
            cgc, wgdc, ratio = fetch_amounts_and_ratio(self.cfg)
            self.cfg["last_cgc"] = cgc
            self.cfg["last_wgdc"] = wgdc
            self.cfg["last_ratio"] = ratio
            self.cfg["last_update"] = time.time()
            save_config(self.cfg)
        except Exception as e:
            print("manual refresh error:", e)

    def refresh_status_label(self, dt):
        cfg = load_config()
        ratio = cfg.get("last_ratio")
        cgc = cfg.get("last_cgc")
        wgdc = cfg.get("last_wgdc")
        ts = cfg.get("last_update")
        if ratio is not None and cgc is not None and wgdc is not None:
            t_str = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "-"
            self.status_label.text = (
                f"CGC: {cgc:.4f}   WGDC: {wgdc:.4f}\n"
                f"实时比例(第1档): {ratio:.4f}\n"
                f"更新于 {t_str}"
            )


if __name__ == "__main__":
    MyCGCApp().run()
