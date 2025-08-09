"""
Тесты конфигурации и настроек
"""

from wpg_engine.config.settings import DatabaseSettings, Settings, TelegramSettings


class TestSettings:
    """Тесты настроек приложения"""

    def test_database_settings_defaults(self):
        """Тест настроек базы данных по умолчанию"""
        db_settings = DatabaseSettings()

        assert db_settings.url == "sqlite:///./wpg_engine.db"
        assert db_settings.echo is False

    def test_telegram_settings_structure(self):
        """Тест структуры настроек Telegram"""
        tg_settings = TelegramSettings()

        # Проверяем, что настройки имеют правильные атрибуты
        assert hasattr(tg_settings, "token")
        assert hasattr(tg_settings, "webhook_url")
        assert hasattr(tg_settings, "admin_id")

    def test_main_settings_defaults(self):
        """Тест основных настроек по умолчанию"""
        settings = Settings()

        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.telegram, TelegramSettings)

    def test_settings_structure(self):
        """Тест структуры настроек"""
        settings = Settings()

        # Проверяем, что все подсистемы настроек присутствуют
        assert hasattr(settings, "database")
        assert hasattr(settings, "telegram")
        assert hasattr(settings, "vk")
        assert hasattr(settings, "ai")

        # Проверяем основные поля
        assert hasattr(settings, "debug")
        assert hasattr(settings, "log_level")

    def test_database_url_sqlite_conversion(self):
        """Тест преобразования URL базы данных для SQLite"""
        from wpg_engine.models.base import engine

        # URL должен быть преобразован для aiosqlite
        assert "sqlite+aiosqlite://" in str(engine.url)
