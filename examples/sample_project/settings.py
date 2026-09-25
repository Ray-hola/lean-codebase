"""Settings lookup. Toy demo code, not real software."""
import os

import config


def env(key, default):
    return os.environ.get(key, default)


def is_debug():
    return config.database_url().startswith("sqlite")
