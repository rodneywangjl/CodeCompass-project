"""T3.2 colour support tests (tests-first).

Contract under test (Spec 004 AC-5.1, 5.2, 5.6; Plan 004 section 8; Articles VI.3, VI.5):
  - colour only on a real terminal (a file descriptor that is a tty), never with NO_COLOR,
    --no-color or TERM=dumb; 24-bit, the 256-colour fallback, or none
  - two themes, dark (Rosé Pine Moon) and light (Rosé Pine Dawn), chosen by --theme,
    CODECOMPASS_THEME or COLORFGBG, with an error for an unknown name
  - paint() wraps text in exact sequences, and strip_escapes() gives the text back
  - every colour keeps a contrast floor on its backgrounds, errors a higher one
"""

import io

import pytest

from codecompass.online import tui_view as view

ROLES = ("accent", "info", "warn", "tag", "danger", "ok", "muted")
TTY_FD = 7  # the stand-in terminal's file descriptor; os.isatty is patched to accept it


class FakeTerminal(io.StringIO):
    """A stream that has a file descriptor, like a real terminal does."""

    def fileno(self):
        return TTY_FD


class NoDescriptor(io.StringIO):
    def fileno(self):
        raise io.UnsupportedOperation("fileno")


@pytest.fixture(autouse=True)
def tty_is_fd_7(monkeypatch):
    monkeypatch.setattr("os.isatty", lambda fd: fd == TTY_FD)


# --- color_level (AC-5.2) ------------------------------------------------------------


def level(env, stream=None, no_color=False):
    return view.color_level(stream or FakeTerminal(), env, no_color=no_color)


def test_a_stream_without_a_file_descriptor_never_gets_colour():
    assert view.color_level(io.StringIO(), {"COLORTERM": "truecolor"}) == "none"
    assert view.color_level(NoDescriptor(), {"COLORTERM": "truecolor"}) == "none"


def test_a_pipe_or_file_never_gets_colour():
    class Pipe(io.StringIO):
        def fileno(self):
            return 3  # a descriptor that is not a tty

    assert view.color_level(Pipe(), {"COLORTERM": "truecolor"}) == "none"


@pytest.mark.parametrize("env", [{"COLORTERM": "truecolor"}, {"COLORTERM": "24bit"},
                                 {"WT_SESSION": "abc-123"},
                                 {"COLORTERM": "truecolor", "TERM": "xterm-256color"}])
def test_truecolor_terminals(env):
    assert level(env) == "truecolor"


def test_256_colour_terminals():
    assert level({"TERM": "xterm-256color"}) == "256"
    assert level({"TERM": "screen-256color"}) == "256"


@pytest.mark.parametrize("env", [{}, {"TERM": "xterm"}, {"TERM": "vt100"}])
def test_other_terminals_get_no_colour(env):
    assert level(env) == "none"


def test_no_color_variable_turns_colour_off_when_it_has_a_value():
    assert level({"COLORTERM": "truecolor", "NO_COLOR": "1"}) == "none"
    assert level({"COLORTERM": "truecolor", "NO_COLOR": "anything"}) == "none"


def test_an_empty_no_color_variable_does_not():
    assert level({"COLORTERM": "truecolor", "NO_COLOR": ""}) == "truecolor"


def test_the_no_color_flag_turns_colour_off():
    assert level({"COLORTERM": "truecolor"}, no_color=True) == "none"


def test_a_dumb_terminal_gets_no_colour():
    assert level({"COLORTERM": "truecolor", "TERM": "dumb"}) == "none"


# --- theme_name (AC-5.6) -------------------------------------------------------------


@pytest.mark.parametrize("fgbg", ["0;15", "0;7", "15;0;7", "0;default;15"])
def test_auto_picks_light_when_the_terminal_says_its_background_is_light(fgbg):
    assert view.theme_name(None, {"COLORFGBG": fgbg}) == "light"
    assert view.theme_name("auto", {"COLORFGBG": fgbg}) == "light"


@pytest.mark.parametrize("env", [{}, {"COLORFGBG": ""}, {"COLORFGBG": "15;0"},
                                 {"COLORFGBG": "0;default"}, {"COLORFGBG": "abc"},
                                 {"COLORFGBG": "0;8"}])
def test_auto_picks_dark_otherwise(env):
    assert view.theme_name(None, env) == "dark"


def test_the_flag_beats_the_environment_variable_which_beats_auto():
    light_terminal = {"COLORFGBG": "0;15"}
    assert view.theme_name("dark", light_terminal) == "dark"
    assert view.theme_name(None, {**light_terminal, "CODECOMPASS_THEME": "dark"}) == "dark"
    assert view.theme_name("light", {"CODECOMPASS_THEME": "dark"}) == "light"
    assert view.theme_name(None, {"CODECOMPASS_THEME": "light"}) == "light"
    assert view.theme_name(None, {"CODECOMPASS_THEME": ""}) == "dark"  # empty means unset


@pytest.mark.parametrize("flag, env", [("neon", {}), (None, {"CODECOMPASS_THEME": "neon"}),
                                       ("LIGHT", {})])
def test_an_unknown_theme_is_an_error_naming_the_allowed_values(flag, env):
    with pytest.raises(ValueError, match="auto, dark, light"):
        view.theme_name(flag, env)


# --- the palettes (AC-5.1) -----------------------------------------------------------

DARK = {"accent": ("#c4a7e7", False), "info": ("#9ccfd8", False), "warn": ("#f6c177", False),
        "tag": ("#ea9a97", False), "danger": ("#eb6f92", True), "ok": ("#3e8fb0", False),
        "muted": ("#6272a4", False)}
LIGHT = {"accent": ("#907aa9", True), "info": ("#286983", False), "warn": ("#b4637a", False),
         "tag": ("#797593", False), "danger": ("#91344f", True), "ok": ("#286983", False),
         "muted": ("#797593", False)}


def test_the_palettes_are_the_ones_in_the_spec():
    assert view.PALETTES == {"dark": DARK, "light": LIGHT}


def test_the_light_error_colour_is_not_the_warning_colour():
    assert view.PALETTES["light"]["danger"][0] != view.PALETTES["light"]["warn"][0]


def _luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_the_reference_backgrounds():
    assert view.BACKGROUNDS == {"dark": ("#232136", "#000000"),
                                "light": ("#faf4ed", "#ffffff")}


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("role", ROLES)
def test_every_colour_has_at_least_3_to_1_contrast(theme, role):
    colour, _ = view.PALETTES[theme][role]
    for background in view.BACKGROUNDS[theme]:
        assert _contrast(colour, background) >= 3.0, (theme, role, colour, background)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_errors_have_at_least_4_5_to_1_contrast(theme):
    colour, bold = view.PALETTES[theme]["danger"]
    assert bold
    for background in view.BACKGROUNDS[theme]:
        assert _contrast(colour, background) >= 4.5


# --- paint and strip_escapes (AC-5.1, 5.2) -------------------------------------------


def test_truecolor_sequences_are_exact():
    dark = view.Style("truecolor", "dark")
    assert dark.paint("hi", "accent") == "\x1b[38;2;196;167;231mhi\x1b[0m"
    assert dark.paint("hi", "danger") == "\x1b[1;38;2;235;111;146mhi\x1b[0m"
    light = view.Style("truecolor", "light")
    assert light.paint("hi", "danger") == "\x1b[1;38;2;145;52;79mhi\x1b[0m"
    assert light.paint("hi", "info") == "\x1b[38;2;40;105;131mhi\x1b[0m"


def test_256_colour_sequences_use_the_nearest_palette_entry():
    out = view.Style("256", "dark").paint("hi", "accent")
    index = view.to_256("#c4a7e7")
    assert out == f"\x1b[38;5;{index}mhi\x1b[0m"
    assert view.Style("256", "light").paint("hi", "danger") == (
        f"\x1b[1;38;5;{view.to_256('#91344f')}mhi\x1b[0m")


def test_no_colour_leaves_the_text_untouched():
    for theme in ("dark", "light"):
        style = view.Style("none", theme)
        assert all(style.paint("hi there", role) == "hi there" for role in ROLES)


def test_an_unknown_role_is_an_error():
    with pytest.raises(KeyError):
        view.Style("truecolor", "dark").paint("hi", "sparkle")


@pytest.mark.parametrize("level_name", ["truecolor", "256", "none"])
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_stripping_the_escapes_gives_the_text_back(level_name, theme):
    style = view.Style(level_name, theme)
    for role in ROLES:
        for text in ("hi", "two words", "[UNVERIFIED] [1] src/a.py, lines 1-2", "", "é ✓ ⚠"):
            assert view.strip_escapes(style.paint(text, role)) == text


def test_strip_escapes_removes_only_colour_sequences():
    assert view.strip_escapes("a\x1b[1;38;2;1;2;3mb\x1b[0mc\nd") == "abc\nd"
    assert view.strip_escapes("plain [1] text") == "plain [1] text"


# --- the 256-colour fallback ---------------------------------------------------------


def _xterm_256():
    levels = (0, 95, 135, 175, 215, 255)
    cube = [(16 + 36 * r + 6 * g + b, (levels[r], levels[g], levels[b]))
            for r in range(6) for g in range(6) for b in range(6)]
    grey = [(232 + i, (8 + 10 * i,) * 3) for i in range(24)]
    return cube + grey


def _rgb(hex_colour):
    return tuple(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))


def _distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def test_known_colours_map_to_known_indexes():
    assert view.to_256("#000000") == 16
    assert view.to_256("#ffffff") == 231
    assert view.to_256("#808080") == 244
    assert view.to_256("#ff0000") == 196


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("role", ROLES)
def test_every_palette_colour_maps_to_a_nearest_entry(theme, role):
    colour, _ = view.PALETTES[theme][role]
    chosen = dict(_xterm_256())[view.to_256(colour)]
    best = min(_distance(_rgb(colour), rgb) for _, rgb in _xterm_256())
    assert _distance(_rgb(colour), chosen) == best
