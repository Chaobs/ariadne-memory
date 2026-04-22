"""
Internationalization (i18n) support for Ariadne.

Supports 8 languages:
  - zh_CN  Simplified Chinese
  - zh_TW  Traditional Chinese
  - ja     Japanese
  - en     English
  - fr     French
  - es     Spanish
  - ru     Russian
  - ar     Arabic (RTL)

The Web UI uses its own frontend i18n (React i18next).
This module provides the backend locale registry and configuration.

Usage:
    from ariadne.i18n import set_locale, available_locales, get_locale_display

    # Switch language at runtime
    set_locale("fr")

    # Query current locale
    current = get_locale()   # e.g. "fr"
    display = get_locale_display()  # e.g. "Français"
"""

from __future__ import annotations

import os
import threading

__all__ = [
    "set_locale",
    "get_locale",
    "get_locale_display",
    "available_locales",
    "init_locale",
    "is_rtl",
]

# ---------------------------------------------------------------------------
# Locale registry
# ---------------------------------------------------------------------------

AVAILABLE_LOCALES: list[tuple[str, str]] = [
    ("zh_CN", "简体中文"),
    ("zh_TW", "繁體中文"),
    ("ja",    "日本語"),
    ("en",    "English"),
    ("fr",    "Français"),
    ("es",    "Español"),
    ("ru",    "Русский"),
    ("ar",    "العربية"),
]

# Thread-safe current locale
_current_locale: str = "en"
_locale_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Locale management
# ---------------------------------------------------------------------------

def set_locale(locale: str) -> bool:
    """
    Switch the UI language at runtime.

    Args:
        locale: Language code, e.g. "zh_CN", "fr", "ar".

    Returns:
        True if the locale was found and activated, False otherwise.
    """
    global _current_locale
    valid_codes = {code for code, _ in AVAILABLE_LOCALES}
    if locale not in valid_codes:
        return False
    with _locale_lock:
        _current_locale = locale
    return True


def get_locale() -> str:
    """Return the current locale code (e.g. "fr")."""
    with _locale_lock:
        return _current_locale


def get_locale_display() -> str:
    """Return the display name of the current locale (e.g. "Français")."""
    code = get_locale()
    for c, name in AVAILABLE_LOCALES:
        if c == code:
            return name
    return code


def available_locales() -> list[tuple[str, str]]:
    """Return list of (code, display_name) pairs for all supported locales."""
    return AVAILABLE_LOCALES.copy()


def is_rtl() -> bool:
    """Return True if the current locale is right-to-left (Arabic only)."""
    return get_locale() == "ar"


# ---------------------------------------------------------------------------
# CLI convenience: set locale from environment variable or argument
# ---------------------------------------------------------------------------

def init_locale() -> None:
    """
    Auto-initialize locale from the ARIADNE_LANG environment variable.
    Called automatically by cli.py and web entry points.
    Call this manually if you use the library programmatically.
    """
    env_locale = os.environ.get("ARIADNE_LANG", "")
    if env_locale:
        set_locale(env_locale)
