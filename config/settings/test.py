"""
Test-specific Django settings.

Uses SQLite for tests to avoid database permission issues.
This is faster and doesn't require special database permissions.
"""

from .base import *  # noqa: F403

# Use SQLite for tests (in-memory, fast, no permissions needed)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable migrations for faster tests (optional)
# If you need to test migrations, remove this
# class DisableMigrations:
#     def __contains__(self, item):
#         return True
#     def __getitem__(self, item):
#         return None
# MIGRATION_MODULES = DisableMigrations()

# Speed up password hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable logging during tests
LOGGING_CONFIG = None
