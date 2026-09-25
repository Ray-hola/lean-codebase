"""App config. Toy demo code, not real software.

Imports settings at module top; settings imports back — a 2-cycle that
measure.py flags. The fix is to move the shared helper to a neutral module.
"""
import settings


def database_url():
    return settings.env("DATABASE_URL", "sqlite://:memory:")
