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

Usage:
    from ariadne.i18n import _, set_locale, available_locales, get_locale_display

    # Get translated string
    label = _("Search")

    # Switch language at runtime
    set_locale("fr")

    # Query current locale
    current = get_locale()   # e.g. "fr"
    display = get_locale_display()  # e.g. "Français"

Language files are stored in:
    ariadne/locale/<lang>/LC_MESSAGES/ariadne.mo

To compile .po → .mo:
    msgfmt ariadne/locale/<lang>/LC_MESSAGES/ariadne.po -o ariadne/locale/<lang>/LC_MESSAGES/ariadne.mo
"""

from __future__ import annotations

import gettext as _gettext
import os
import threading
from pathlib import Path
from typing import Optional

__all__ = [
    "_",
    "set_locale",
    "get_locale",
    "get_locale_display",
    "available_locales",
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

# Language code → domain name (all share the same .mo files)
DOMAIN = "ariadne"
LOCALE_DIR = Path(__file__).parent.parent / "locale"

# Thread-safe current locale
_current_locale: str = "en"
_locale_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Translation function
# ---------------------------------------------------------------------------

def _get_translation(locale: str) -> _gettext.GNUTranslations:
    """Load and return the translation object for the given locale."""
    try:
        return _gettext.translation(
            domain=DOMAIN,
            localedir=str(LOCALE_DIR),
            languages=[locale],
        )
    except FileNotFoundError:
        # Fall back to no translation (English strings)
        return _gettext.NullTranslations()


# The global translator — swapped by set_locale()
_translator: _gettext.GNUTranslations = _gettext.NullTranslations()


def _load_translator(locale: str) -> None:
    global _translator
    _translator = _get_translation(locale)


# Load English (null translator / identity) by default
_load_translator("en")


def _(message: str) -> str:
    """
    Translate *message* to the current locale.

    This is the standard gettext interface used throughout the codebase.
    In the English locale, this is a no-op (identity function).
    """
    return _translator.gettext(message)


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

    Note:
        Arabic (ar) sets LANG to "ar" but the UI framework (Tkinter)
        must additionally configure text direction (LTR/RTL) separately.
    """
    global _current_locale
    valid_codes = {code for code, _ in AVAILABLE_LOCALES}
    if locale not in valid_codes:
        return False
    with _locale_lock:
        _current_locale = locale
        _load_translator(locale)
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
    Called automatically by cli.py and gui.py entry points.
    Call this manually if you use the library programmatically.
    """
    env_locale = os.environ.get("ARIADNE_LANG", "")
    if env_locale:
        set_locale(env_locale)
