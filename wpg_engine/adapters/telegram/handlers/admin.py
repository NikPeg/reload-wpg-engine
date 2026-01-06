"""
Admin handlers - main registration file
"""

from aiogram import Dispatcher
from aiogram.filters import Command

from .admin_commands import (
    active_command,
    game_stats_command,
    random_command,
    update_game_command,
)
from .admin_delete import (
    delete_country_command,
    delete_user_command,
    process_delete_country_confirmation,
    process_delete_user_confirmation,
    process_final_message,
)
from .admin_events import event_command, process_event_message
from .admin_examples import add_example_command, process_example_message
from .admin_game_management import (
    process_restart_confirmation,
    restart_game_command,
)
from .admin_gen import gen_command, process_gen_callback
from .admin_utils import AdminStates


def register_admin_handlers(dp: Dispatcher) -> None:
    """Register admin handlers"""
    # Simple commands (no FSM)
    dp.message.register(game_stats_command, Command("game_stats"))
    dp.message.register(active_command, Command("active"))
    dp.message.register(update_game_command, Command("update_game"))
    dp.message.register(random_command, Command("random"))

    # Game management commands (with FSM)
    dp.message.register(restart_game_command, Command("restart_game"))
    dp.message.register(
        process_restart_confirmation, AdminStates.waiting_for_restart_confirmation
    )

    # Event commands (with FSM)
    dp.message.register(event_command, Command("event"))
    dp.message.register(process_event_message, AdminStates.waiting_for_event_message)

    # Generation commands (with FSM)
    dp.message.register(gen_command, Command("gen"))
    dp.callback_query.register(process_gen_callback, AdminStates.waiting_for_gen_action)
    # Register callback handlers for admin chat buttons (no state required)
    dp.callback_query.register(
        process_gen_callback,
        lambda c: c.data
        and (
            c.data.startswith("gen_verdict_resend:")
            or c.data.startswith("gen_verdict_undo:")
        ),
    )

    # Delete commands (with FSM)
    dp.message.register(delete_country_command, Command("delete_country"))
    dp.message.register(
        process_delete_country_confirmation,
        AdminStates.waiting_for_delete_country_confirmation,
    )
    dp.message.register(process_final_message, AdminStates.waiting_for_final_message)
    dp.message.register(delete_user_command, Command("delete_user"))
    dp.message.register(
        process_delete_user_confirmation,
        AdminStates.waiting_for_delete_user_confirmation,
    )

    # Example commands (with FSM)
    dp.message.register(add_example_command, Command("add_example"))
    dp.message.register(
        process_example_message, AdminStates.waiting_for_example_message
    )
