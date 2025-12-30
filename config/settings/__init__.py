import os

env = os.environ.get("DJANGO_ENV", "dev")
if env == "prod":
    from .prod import *  # noqa: F403
else:
    from .dev import *  # noqa: F403
