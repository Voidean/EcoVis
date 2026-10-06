from enum import IntEnum

from sdl3 import SDL as sdl


class MouseButton(IntEnum):
    LEFT = sdl.SDL_BUTTON_LEFT
    MIDDLE = sdl.SDL_BUTTON_MIDDLE
    RIGHT = sdl.SDL_BUTTON_RIGHT


KEY_ESCAPE = sdl.SDL_SCANCODE_ESCAPE

_LEGACY_TO_SDL_SUFFIX = {
    "LEFT_CONTROL": "LCTRL",
    "RIGHT_CONTROL": "RCTRL",
    "LEFT_SHIFT": "LSHIFT",
    "RIGHT_SHIFT": "RSHIFT",
    "LEFT_ALT": "LALT",
    "RIGHT_ALT": "RALT",
    "LEFT_SUPER": "LGUI",
    "RIGHT_SUPER": "RGUI",
    "PAGE_UP": "PAGEUP",
    "PAGE_DOWN": "PAGEDOWN",
    "CAPS_LOCK": "CAPSLOCK",
    "SCROLL_LOCK": "SCROLLLOCK",
    "NUM_LOCK": "NUMLOCKCLEAR",
    "PRINT_SCREEN": "PRINTSCREEN",
}
_SDL_TO_LEGACY_SUFFIX = {
    sdl_name: legacy_name for legacy_name, sdl_name in _LEGACY_TO_SDL_SUFFIX.items()
}


def scancode_from_config(value):
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return value

    suffix = value
    if suffix.startswith("SDL_SCANCODE_"):
        suffix = suffix.removeprefix("SDL_SCANCODE_")
    elif suffix.startswith("KEY_"):
        suffix = suffix.removeprefix("KEY_")

    suffix = _LEGACY_TO_SDL_SUFFIX.get(suffix, suffix)
    return getattr(sdl, f"SDL_SCANCODE_{suffix}", value)


def scancode_config_name(scancode):
    for name, value in vars(sdl).items():
        if name.startswith("SDL_SCANCODE_") and value == scancode:
            suffix = name.removeprefix("SDL_SCANCODE_")
            suffix = _SDL_TO_LEGACY_SUFFIX.get(suffix, suffix)
            return f"KEY_{suffix}"
    return f"SCANCODE_{scancode}"


def scancode_display_name(scancode):
    name = sdl.SDL_GetScancodeName(scancode)
    if name:
        decoded = name.decode("utf-8")
        if decoded:
            return decoded
    return scancode_config_name(scancode).replace("KEY_", "").replace("_", " ").title()
