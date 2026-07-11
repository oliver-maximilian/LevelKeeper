from levelkeeper.mount_check import check_mount


def test_check_mount_missing_dir(tmp_path):
    assert not check_mount(tmp_path / "does-not-exist", ".marker").ok


def test_check_mount_missing_marker(tmp_path):
    assert not check_mount(tmp_path, ".marker").ok


def test_check_mount_ok(tmp_path):
    (tmp_path / ".marker").touch()
    assert check_mount(tmp_path, ".marker").ok
