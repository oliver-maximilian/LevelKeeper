import os

import pytest

from levelkeeper.lockfile import LockFile, LockHeldError


def test_acquire_and_release(tmp_path):
    path = tmp_path / "lk.lock"
    lock = LockFile(path)
    lock.acquire()
    assert path.exists()
    lock.release()
    assert not path.exists()


def test_double_acquire_raises(tmp_path):
    path = tmp_path / "lk.lock"
    lock1 = LockFile(path)
    lock1.acquire()
    try:
        with pytest.raises(LockHeldError):
            LockFile(path).acquire()
    finally:
        lock1.release()


def test_stale_lock_is_cleared(tmp_path):
    path = tmp_path / "lk.lock"
    path.write_text("999999")  # pid very unlikely to be running
    lock = LockFile(path)
    lock.acquire()
    assert path.read_text().strip() == str(os.getpid())
    lock.release()


def test_context_manager(tmp_path):
    path = tmp_path / "lk.lock"
    with LockFile(path):
        assert path.exists()
    assert not path.exists()
