"""Safety controls package."""

from trading_bot.safety.kill_switch import (
    KillSwitchState,
    activate_kill_switch,
    clear_kill_switch,
    read_kill_switch,
)

__all__ = [
    "KillSwitchState",
    "activate_kill_switch",
    "clear_kill_switch",
    "read_kill_switch",
]
