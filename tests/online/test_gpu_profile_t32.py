"""T3.2 (Spec 005) the dev-7b-gpu profile: tests first, against the real codecompass.toml.

Contract under test (Spec 005 AC-2.1 to AC-2.4):
  - dev-7b-gpu uses the same GGUF file and SHA-256 as dev-7b, an 8192 context, a
    1024-token answer cap and the llama-server flags that keep it small enough to share
    the GPU with the re-ranker (26 layers, -ub 256, q8 cache: Spec 005 section 1)
  - it passes the start-up budget check and leaves room for at least 5 chunks of 512 tokens
  - the warning printed when the server is down gives a start command with all of it
  - the file records the llama.cpp build and that this is a development profile
  - dev-7b and the default profile are unchanged
"""

from pathlib import Path

import pytest

from codecompass.online.agent.harness import system_prompt
from codecompass.online.config import load_online_config
from codecompass.online.context import check_round_reserve, chunk_budget
from codecompass.online.tui import _start_command

TOML = Path(__file__).resolve().parents[2] / "codecompass.toml"


@pytest.fixture(scope="module")
def cfg():
    return load_online_config(TOML)


@pytest.fixture(scope="module")
def gpu(cfg):
    return cfg.generator.profiles["dev-7b-gpu"]


def test_the_profile_uses_the_same_model_file_and_checksum_as_dev_7b(cfg, gpu):
    base = cfg.generator.profiles["dev-7b"]
    assert gpu.gguf_file == base.gguf_file == "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    assert gpu.gguf_checksum == base.gguf_checksum != ""
    assert gpu.quantisation == base.quantisation == "Q4_K_M"
    assert gpu.model_id == base.model_id == "Qwen2.5-Coder-7B-Instruct"
    assert (gpu.temperature, gpu.stop_tokens) == (base.temperature, base.stop_tokens)


def test_the_context_and_answer_cap_are_the_small_gpu_values(gpu):
    assert (gpu.context_window, gpu.max_tokens) == (8192, 1024)


def test_the_server_flags_keep_it_small_enough_to_share_the_gpu(gpu):
    args = list(gpu.server_args)
    assert args[args.index("-ngl") + 1] == "26"  # all layers ran out of memory (Spec 005)
    assert args[args.index("-ub") + 1] == "256"
    assert args[args.index("--cache-type-k") + 1] == "q8_0"
    assert args[args.index("--cache-type-v") + 1] == "q8_0"


def test_the_profile_passes_the_budget_check_with_room_for_five_chunks(cfg, gpu):
    prompt_tokens = 2 * len(system_prompt(tools_enabled=True).split())  # tokens > words
    check_round_reserve(gpu, cfg.tools, prompt_tokens)  # raises when no room is left
    assert chunk_budget(gpu, cfg.tools, prompt_tokens + 100) >= 5 * 512


def test_the_warning_for_a_server_that_is_down_prints_the_full_start_command(cfg, gpu):
    command = _start_command(gpu, cfg.generator.server_url)
    assert command.startswith("llama-server -m ")
    assert "qwen2.5-coder-7b-instruct-q4_k_m.gguf" in command
    for part in ("--host 127.0.0.1", "--port 8080", "-c 8192", "-ngl 26", "-ub 256",
                 "--cache-type-k q8_0", "--cache-type-v q8_0"):
        assert part in command


def test_the_file_records_the_llama_cpp_build_and_that_this_is_a_development_profile():
    text = TOML.read_text()
    block = text[text.index("[generator.profiles.dev-7b-gpu]") - 1800:
                 text.index("[generator.profiles.dev-7b-gpu]")]
    assert "b11960" in block and "8642541b2" in block
    assert "development" in block.lower() and "VIII.5" in block


def test_dev_7b_and_the_default_profile_are_unchanged(cfg):
    dev7 = cfg.generator.profiles["dev-7b"]
    assert (dev7.context_window, dev7.max_tokens, dev7.server_args) == (16384, 2048, ())
    assert cfg.generator.default_profile == "dev"
