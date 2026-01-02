"""
Tests for admin chat functionality
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wpg_engine.config.settings import TelegramSettings
from wpg_engine.core.admin_utils import (
    determine_player_role,
    is_admin,
    is_admin_from_env,
)
from wpg_engine.models import PlayerRole


class TestAdminChatSupport:
    """Test admin chat support functionality"""

    def test_is_admin_chat_with_negative_id(self):
        """Test that negative admin_id is recognized as chat"""
        # Create settings with negative admin_id (chat), bypassing env validation
        telegram_settings = TelegramSettings.model_construct(
            token="test", admin_id=-1001234567890
        )
        assert telegram_settings.is_admin_chat() is True
        assert telegram_settings.is_admin_user() is False

    def test_is_admin_user_with_positive_id(self):
        """Test that positive admin_id is recognized as user"""
        telegram_settings = TelegramSettings.model_construct(
            token="test", admin_id=123456789
        )
        assert telegram_settings.is_admin_user() is True
        assert telegram_settings.is_admin_chat() is False

    def test_is_admin_from_env_with_chat(self):
        """Test is_admin_from_env with admin chat"""
        # Mock settings with admin chat
        telegram_settings = TelegramSettings.model_construct(
            token="test", admin_id=-1001234567890
        )

        with patch("wpg_engine.core.admin_utils.settings") as mock_settings:
            mock_settings.telegram = telegram_settings

            # User from admin chat should be admin
            assert (
                is_admin_from_env(
                    telegram_id=999999999,  # Any user
                    chat_id=-1001234567890,  # Admin chat
                )
                is True
            )

            # User from different chat should not be admin
            assert (
                is_admin_from_env(
                    telegram_id=999999999,
                    chat_id=-1009876543210,  # Different chat
                )
                is False
            )

            # User in private message should not be admin (no chat_id)
            assert is_admin_from_env(telegram_id=999999999, chat_id=None) is False

    def test_is_admin_from_env_with_user(self):
        """Test is_admin_from_env with admin user"""
        # Mock settings with admin user
        telegram_settings = TelegramSettings.model_construct(
            token="test", admin_id=123456789
        )

        with patch("wpg_engine.core.admin_utils.settings") as mock_settings:
            mock_settings.telegram = telegram_settings

            # Specific user should be admin
            assert is_admin_from_env(telegram_id=123456789, chat_id=None) is True

            # Different user should not be admin
            assert is_admin_from_env(telegram_id=987654321, chat_id=None) is False

            # Even in a chat, specific user is admin
            assert (
                is_admin_from_env(telegram_id=123456789, chat_id=-1001234567890) is True
            )

    @pytest.mark.asyncio
    async def test_determine_player_role_with_admin_chat(self):
        """Test determine_player_role with admin chat"""
        # Mock settings with admin chat
        telegram_settings = TelegramSettings.model_construct(
            token="test", admin_id=-1001234567890
        )

        with patch("wpg_engine.core.admin_utils.settings") as mock_settings:
            mock_settings.telegram = telegram_settings

            # Mock database session with proper async mock
            db_mock = MagicMock()
            result_mock = MagicMock()
            result_mock.scalars.return_value.all.return_value = []
            db_mock.execute = AsyncMock(return_value=result_mock)

            # Any user from admin chat should get ADMIN role
            role = await determine_player_role(
                telegram_id=999999999, game_id=1, db=db_mock, chat_id=-1001234567890
            )
            assert role == PlayerRole.ADMIN

            # User from different chat should not be auto-admin from env
            # Mock that there are existing players with admin
            player_mock = MagicMock()
            player_mock.role = PlayerRole.ADMIN

            result_mock2 = MagicMock()
            result_mock2.scalars.return_value.all.return_value = [player_mock]
            db_mock.execute = AsyncMock(return_value=result_mock2)

            role = await determine_player_role(
                telegram_id=999999999,
                game_id=1,
                db=db_mock,
                chat_id=-1009876543210,  # Different chat
            )
            assert role == PlayerRole.PLAYER  # Not admin from env, and players exist

    @pytest.mark.asyncio
    async def test_is_admin_with_chat_id(self):
        """Test is_admin function with chat_id parameter"""
        # Mock settings with admin chat
        telegram_settings = TelegramSettings.model_construct(
            token="test", admin_id=-1001234567890
        )

        with patch("wpg_engine.core.admin_utils.settings") as mock_settings:
            mock_settings.telegram = telegram_settings

            # Mock database session with proper mock
            db_mock = MagicMock()
            result_mock = MagicMock()
            result_mock.scalar_one_or_none.return_value = None  # No player in DB
            db_mock.execute = AsyncMock(return_value=result_mock)

            # User from admin chat should be admin (from env)
            is_admin_result = await is_admin(
                telegram_id=999999999, db=db_mock, chat_id=-1001234567890
            )
            assert is_admin_result is True

            # User from different chat should not be admin
            is_admin_result = await is_admin(
                telegram_id=999999999, db=db_mock, chat_id=-1009876543210
            )
            assert is_admin_result is False
