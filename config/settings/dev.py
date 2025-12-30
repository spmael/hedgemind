# config/settings/dev.py
from __future__ import absolute_import, unicode_literals

from .base import *  # noqa: F403

DEBUG = True

# In dev allow all hosts to reduce friction during development
ALLOWED_HOSTS = ["*"]
