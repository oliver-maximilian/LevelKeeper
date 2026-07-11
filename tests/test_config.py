import pytest

from levelkeeper.config import Config, ConfigError, load_config, parse_size, parse_threshold


def test_parse_size_plain_bytes():
    assert parse_size("2048") == 2048


def test_parse_size_units():
    assert parse_size("1KB") == 1024
    assert parse_size("2MB") == 2 * 1024**2
    assert parse_size("1.5GB") == int(1.5 * 1024**3)
    assert parse_size("1TB") == 1024**4
    assert parse_size("2 GB") == 2 * 1024**3
    assert parse_size("500mb") == 500 * 1024**2


def test_parse_size_invalid_unit():
    with pytest.raises(ConfigError):
        parse_size("5XB")


def test_parse_threshold_percentage():
    quota = 2 * 1024**3
    assert parse_threshold("80%", quota) == int(quota * 0.8)


def test_parse_threshold_absolute():
    assert parse_threshold("1.2GB", 2 * 1024**3) == int(1.2 * 1024**3)


def _base_config(**overrides) -> Config:
    cfg = Config(
        imap_host="imap.example.com",
        imap_user="user@example.com",
        imap_password="secret",
        smtp_host="smtp.example.com",
        smtp_user="user@example.com",
        smtp_password="secret",
        archive_root="/archive",
        quota="2GB",
        trigger="80%",
        target="70%",
        report_recipients=["me@example.com"],
    )
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def test_resolve_and_validate_ok():
    cfg = _base_config()
    cfg.resolve_and_validate()
    assert cfg.quota_bytes == 2 * 1024**3
    assert cfg.trigger_bytes == int(2 * 1024**3 * 0.8)
    assert cfg.target_bytes == int(2 * 1024**3 * 0.7)
    assert cfg.error_recipients == ["me@example.com"]


def test_resolve_and_validate_target_must_be_below_trigger():
    cfg = _base_config(trigger="70%", target="80%")
    with pytest.raises(ConfigError):
        cfg.resolve_and_validate()


def test_resolve_and_validate_trigger_above_quota_rejected():
    cfg = _base_config(trigger="150%", target="70%")
    with pytest.raises(ConfigError):
        cfg.resolve_and_validate()


@pytest.mark.parametrize("field", ["imap_host", "smtp_host", "archive_root", "quota"])
def test_resolve_and_validate_missing_required_field(field):
    cfg = _base_config(**{field: ""})
    with pytest.raises(ConfigError):
        cfg.resolve_and_validate()


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVELKEEPER_IMAP_HOST", "imap.override.example.com")
    monkeypatch.setenv("LEVELKEEPER_IMAP_USER", "u@example.com")
    monkeypatch.setenv("LEVELKEEPER_IMAP_PASSWORD", "pw")
    monkeypatch.setenv("LEVELKEEPER_SMTP_HOST", "smtp.override.example.com")
    monkeypatch.setenv("LEVELKEEPER_SMTP_USER", "u@example.com")
    monkeypatch.setenv("LEVELKEEPER_SMTP_PASSWORD", "pw")
    monkeypatch.setenv("LEVELKEEPER_ARCHIVE_ROOT", str(tmp_path))
    monkeypatch.setenv("LEVELKEEPER_QUOTA", "1GB")
    monkeypatch.setenv("LEVELKEEPER_TRIGGER", "80%")
    monkeypatch.setenv("LEVELKEEPER_TARGET", "70%")
    monkeypatch.setenv("LEVELKEEPER_REPORT_RECIPIENTS", "a@example.com,b@example.com")

    cfg = load_config(None)

    assert cfg.imap_host == "imap.override.example.com"
    assert cfg.report_recipients == ["a@example.com", "b@example.com"]
    assert cfg.quota_bytes == 1024**3


def test_load_config_toml_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[imap]
host = "imap.strato.de"
user = "me@example.com"
password = "secret"

[smtp]
host = "smtp.strato.de"
user = "me@example.com"
password = "secret"

[quota]
quota = "2GB"
trigger = "80%"
target = "70%"

[archive]
root = "/archive"

[notify]
report_recipients = ["me@example.com"]
"""
    )
    cfg = load_config(config_file)
    assert cfg.imap_host == "imap.strato.de"
    assert cfg.quota_bytes == 2 * 1024**3
