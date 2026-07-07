"""
后台前台服务（foreground service）：
- 息屏也持续运行（需求三），配合 buildozer.spec 里的 WAKE_LOCK / FOREGROUND_SERVICE 权限
- 每隔 cfg['interval_minutes'] 分钟刷新一次链上数据（需求一）
- 计算 CGC/WGDC 实时比例，与用户设置的第2档(低)、第3档(高)阈值比较，触发通知（需求二）

每轮循环都会重新读取 config.json，所以用户在 UI 里改了间隔或阈值，
下一轮循环就会生效，不需要重启服务。
"""
import os
import sys
import time
import traceback

# 让这个 service 进程也能 import 到项目根目录下的共享模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_store import load_config, save_config  # noqa: E402
from monitor_core import fetch_amounts_and_ratio  # noqa: E402
from notify import send_notification  # noqa: E402

try:
    from jnius import autoclass
    PythonService = autoclass("org.kivy.android.PythonService")
    PythonService.mService.setAutoRestartService(True)
except Exception:
    pass


def main_loop():
    while True:
        interval_minutes = 5
        try:
            cfg = load_config()
            interval_minutes = max(1, int(cfg.get("interval_minutes", 5)))

            cgc, wgdc, ratio = fetch_amounts_and_ratio(cfg)

            cfg["last_cgc"] = cgc
            cfg["last_wgdc"] = wgdc
            cfg["last_ratio"] = ratio
            cfg["last_update"] = time.time()
            cfg["service_running"] = True
            save_config(cfg)

            low_ratio = float(cfg.get("low_ratio", 0))
            high_ratio = float(cfg.get("high_ratio", 0))

            if ratio is not None:
                if ratio < low_ratio:
                    send_notification("MyCGC 提醒", "GDC NOW LOW!")
                elif ratio > high_ratio:
                    send_notification("MyCGC 提醒", "GDC NOW HAGH!")

        except Exception:
            traceback.print_exc()

        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    main_loop()
