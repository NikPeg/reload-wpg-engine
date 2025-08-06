"""
Telegram bot handlers
"""

from aiogram import Dispatcher

from wpg_engine.adapters.telegram.handlers.admin import register_admin_handlers
from wpg_engine.adapters.telegram.handlers.common import register_common_handlers
from wpg_engine.adapters.telegram.handlers.player import register_player_handlers
from wpg_engine.adapters.telegram.handlers.registration import (
    register_registration_handlers,
)


def register_handlers(dp: Dispatcher) -> None:
    """Register all bot handlers"""
    register_common_handlers(dp)
    register_registration_handlers(dp)
    register_player_handlers(dp)
    register_admin_handlers(dp)
