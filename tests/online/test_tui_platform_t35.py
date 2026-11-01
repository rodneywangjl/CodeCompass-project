"""T3.5 (Spec 005) Windows and macOS safe terminal behaviour: tests first.

Contract under test (Spec 005 AC-4.2 to AC-4.5):
  - the start command shown when llama-server is down is quoted for the platform and
    uses a placeholder path in that platform's style
  - on Windows, ANSI escape handling is switched on once at start-up; elsewhere it is not
  - stdout and stderr are told to replace characters their encoding cannot show, on every
    platform, when the stream allows it
  - the user-level config is read from %APPDATA%\\codecompass on Windows (falling back to
    ~/.config) and from $XDG_CONFIG_HOME or ~/.config elsewhere
The platform is faked by patching sys.platform, so these run on any machine.
"""

import sys
from types import SimpleNamespace

import pytest

import codecompass.online.tui as tui
from codecompass.online.config import ModelProfile
from tests.online.test_tui_main_t12 import In, Out, world, write_toml  # noqa: F401 (fixture)

PROFILE = ModelProfile(model_id="m", gguf_file="my model.gguf", context_window=8192,
                       server_args=("-ngl", "26"))
URL = "http://127.0.0.1:8080"


# --- the start command (AC-4.2) --------------------------------------------------------


def test_the_start_command_uses_windows_quoting_and_a_windows_placeholder_path(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    command = tui._start_command(PROFILE, URL)
    assert command.startswith("llama-server -m ")
    assert '"C:\\path\\to\\my model.gguf"' in command  # double quotes, backslashes
    assert "'" not in command  # no POSIX single quotes
    assert "--port 8080" in command and "-c 8192" in command and "-ngl 26" in command


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_the_start_command_uses_posix_quoting_elsewhere(monkeypatch, platform):
    monkeypatch.setattr(sys, "platform", platform)
    command = tui._start_command(PROFILE, URL)
    assert "'/path/to/my model.gguf'" in command
    assert "\\" not in command and '"' not in command


# --- the terminal (AC-4.3, AC-4.4) -----------------------------------------------------


@pytest.fixture
def started(world, monkeypatch):  # noqa: F811
    """Run main() once on a fake platform; return what start-up did to the terminal."""
    monkeypatch.chdir(world.repo.path)
    calls = SimpleNamespace(system=[], reconfigured=[])
    monkeypatch.setattr(tui.os, "system", lambda cmd: calls.system.append(cmd) or 0)

    class Stream(Out):
        def reconfigure(self, **kwargs):
            calls.reconfigured.append(kwargs)

    def start(platform):
        monkeypatch.setattr(sys, "platform", platform)
        calls.system.clear()
        calls.reconfigured.clear()
        code = tui.main([], stdin=In(tty=False), stdout=Stream(), stderr=Stream(tty=False))
        return code, calls

    return start


def test_windows_turns_on_ansi_escape_handling_once_at_start(started):
    code, calls = started("win32")
    assert code == 0 and calls.system == [""]  # the standard trick that enables VT mode


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_other_platforms_leave_the_console_mode_alone(started, platform):
    _, calls = started(platform)
    assert calls.system == []


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_output_streams_replace_characters_they_cannot_encode(started, platform):
    _, calls = started(platform)
    assert calls.reconfigured == [{"errors": "replace"}, {"errors": "replace"}]  # out, err


def test_streams_without_reconfigure_are_left_alone(world, monkeypatch):  # noqa: F811
    monkeypatch.chdir(world.repo.path)
    code, _, _ = world.run([], "q?\n")  # the plain Out streams have no reconfigure()
    assert code == 0


# --- the user-level config (AC-4.5) ----------------------------------------------------


def banner_files(world, monkeypatch, platform, tty=True):  # noqa: F811
    monkeypatch.chdir(world.repo.path)
    monkeypatch.setattr(sys, "platform", platform)
    _, _, err = world.run([], tty=tty)
    return err


def test_windows_reads_the_user_config_from_appdata(world, monkeypatch):  # noqa: F811
    appdata = world.tmp / "AppData" / "Roaming"
    user = write_toml(appdata / "codecompass" / "codecompass.toml", "win")
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.delenv("XDG_CONFIG_HOME")  # an explicit XDG_CONFIG_HOME would win (below)
    err = banner_files(world, monkeypatch, "win32")
    assert f"config: {user}" in err and "profile p-win" in err


def test_an_explicit_xdg_config_home_wins_on_windows_too(world, monkeypatch):  # noqa: F811
    appdata = world.tmp / "AppData" / "Roaming"
    write_toml(appdata / "codecompass" / "codecompass.toml", "win")
    monkeypatch.setenv("APPDATA", str(appdata))
    xdg = write_toml(world.tmp / "xdg" / "codecompass" / "codecompass.toml", "xdg")
    err = banner_files(world, monkeypatch, "win32")  # the fixture sets XDG_CONFIG_HOME
    assert f"config: {xdg}" in err and "p-win" not in err


def test_windows_falls_back_to_dot_config_without_appdata(world, monkeypatch):  # noqa: F811
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME")
    user = write_toml(world.tmp / "home" / ".config" / "codecompass" / "codecompass.toml", "dot")
    err = banner_files(world, monkeypatch, "win32")
    assert f"config: {user}" in err


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_other_platforms_ignore_appdata(world, monkeypatch, platform):  # noqa: F811
    appdata = world.tmp / "AppData" / "Roaming"
    write_toml(appdata / "codecompass" / "codecompass.toml", "win")
    monkeypatch.setenv("APPDATA", str(appdata))
    xdg = write_toml(world.tmp / "xdg" / "codecompass" / "codecompass.toml", "xdg")
    err = banner_files(world, monkeypatch, platform)
    assert f"config: {xdg}" in err and "p-win" not in err
