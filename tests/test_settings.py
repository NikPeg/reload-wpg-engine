"""
Test settings loading
"""

from wpg_engine.config.settings import settings

print("Settings loaded:")
print(f"Database URL: {settings.database.url}")
print(f"Database Echo: {settings.database.echo}")
print(f"Telegram Token: {settings.telegram.token}")
print(f"Telegram Admin ID: {settings.telegram.admin_id}")
print(f"Debug: {settings.debug}")
print(f"Log Level: {settings.log_level}")
