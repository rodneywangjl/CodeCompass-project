"""T5.3 writer lock tests (tests-first)."""

import os
import pathlib
import subprocess
import sys
import threading
import time

import pytest

from codecompass.offline.lock import LockTimeout, acquire_lock

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_second_acquirer_waits_then_succeeds(tmp_path):
    lock = str(tmp_path / "index.lock")
    order = []
    with acquire_lock(lock, timeout_seconds=5):
        order.append("first-in")

        def second():
            with acquire_lock(lock, timeout_seconds=5):
                order.append("second-in")

        t = threading.Thread(target=second)
        t.start()
        time.sleep(0.2)
        assert order == ["first-in"]  # second waits
        order.append("first-out")
    t.join()
    assert order == ["first-in", "first-out", "second-in"]


def test_timeout_raises_lock_timeout(tmp_path):
    lock = str(tmp_path / "index.lock")
    with acquire_lock(lock, timeout_seconds=5):
        with pytest.raises(LockTimeout):
            with acquire_lock(lock, timeout_seconds=0.2):
                pass


def test_two_processes_do_not_overlap(tmp_path):
    lock = tmp_path / "index.lock"
    log = tmp_path / "order.log"
    script = tmp_path / "holder.py"
    script.write_text(
        "import sys, time\n"
        "from codecompass.offline.lock import acquire_lock\n"
        "lock, log, tag, nap = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])\n"
        "with acquire_lock(lock, timeout_seconds=10):\n"
        "    open(log, 'a').write(tag + '-in\\n')\n"
        "    time.sleep(nap)\n"
        "    open(log, 'a').write(tag + '-out\\n')\n"
    )
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    pa = subprocess.Popen(
        [sys.executable, str(script), str(lock), str(log), "A", "0.6"], env=env)
    time.sleep(0.3)  # let A take the lock first
    pb = subprocess.Popen(
        [sys.executable, str(script), str(lock), str(log), "B", "0"], env=env)
    assert pa.wait(timeout=30) == 0 and pb.wait(timeout=30) == 0
    assert log.read_text().split() == ["A-in", "A-out", "B-in", "B-out"]
