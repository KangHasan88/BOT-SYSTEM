"""Demo data helpers for local user walkthroughs."""

from trading_bot.demo.data_pack import DemoDataPackResult, seed_demo_data_pack
from trading_bot.demo.local_demo import LocalDemoCheck, LocalDemoReport, build_local_demo_report, save_local_demo_report
from trading_bot.demo.vps_demo import VpsDemoCheck, VpsDemoReport, build_vps_demo_report, save_vps_demo_report

__all__ = [
    "DemoDataPackResult",
    "LocalDemoCheck",
    "LocalDemoReport",
    "VpsDemoCheck",
    "VpsDemoReport",
    "build_local_demo_report",
    "build_vps_demo_report",
    "save_local_demo_report",
    "save_vps_demo_report",
    "seed_demo_data_pack",
]
