"""Test release-preflight rules with synthetic non-secret values."""
import pytest

from release_preflight import main, parse_env_file, validate_release_configuration

KEY = "a" * 48
ADMIN = "b" * 48


def configs():
    api = {
        "PILOT_API_KEY": KEY,
        "ADMIN_API_KEY": ADMIN,
        "OUTPUT_STORAGE_DIR": "/app/data/source_files/generated_outputs",
        "RAILWAY_VOLUME_MOUNT_PATH": "/app/data/source_files",
    }
    bot = {
        "PILOT_API_KEY": KEY,
        "TELEGRAM_BOT_TOKEN": "test-not-a-live-token",
        "TELEGRAM_ALLOWED_USER_IDS": "12345,67890",
    }
    return api, bot


def errors(api, bot):
    return [f.code for f in validate_release_configuration(api, bot) if f.level == "ERROR"]


def test_valid_configuration_has_no_critical_blockers():
    assert errors(*configs()) == []


def test_unconfigured_pilot_token_fails_closed():
    api, bot = configs()
    del bot["PILOT_API_KEY"]
    assert "PILOT_API_KEY_MISSING" in errors(api, bot)


def test_short_pilot_token_rejected():
    api, bot = configs()
    api["PILOT_API_KEY"] = bot["PILOT_API_KEY"] = "weak"
    assert "PILOT_API_KEY_WEAK" in errors(api, bot)


def test_different_pilot_tokens_rejected_without_leakage():
    api, bot = configs()
    bot["PILOT_API_KEY"] = "d" * 48
    findings = validate_release_configuration(api, bot)
    assert "PILOT_API_KEY_MISMATCH" in [f.code for f in findings]
    assert KEY not in repr(findings)
    assert bot["PILOT_API_KEY"] not in repr(findings)


def test_empty_telegram_allowlist_rejected():
    api, bot = configs()
    bot["TELEGRAM_ALLOWED_USER_IDS"] = ""
    assert "TELEGRAM_ALLOWLIST_EMPTY" in errors(api, bot)


def test_invalid_telegram_allowlist_rejected():
    api, bot = configs()
    bot["TELEGRAM_ALLOWED_USER_IDS"] = "123, -42"
    assert "TELEGRAM_ALLOWLIST_INVALID" in errors(api, bot)


def test_default_ephemeral_output_path_is_rejected():
    api, bot = configs()
    api.pop("OUTPUT_STORAGE_DIR")
    assert "OUTPUT_EPHEMERAL" in errors(api, bot)


def test_no_volume_metadata_is_rejected():
    api, bot = configs()
    api.pop("RAILWAY_VOLUME_MOUNT_PATH")
    assert "OUTPUT_NOT_PROVEN_DURABLE" in errors(api, bot)


def test_path_sibling_not_treated_as_mount_child():
    api, bot = configs()
    api["OUTPUT_STORAGE_DIR"] = "/app/data/source_files_shadow/exports"
    assert "OUTPUT_EPHEMERAL" in errors(api, bot)


def test_relative_output_path_resolves_under_app():
    api, bot = configs()
    api["OUTPUT_STORAGE_DIR"] = "data/source_files/generated_outputs"
    assert errors(api, bot) == []


def test_path_traversal_outside_volume_rejected():
    api, bot = configs()
    api["OUTPUT_STORAGE_DIR"] = "data/source_files/../../unsafe"
    assert "OUTPUT_EPHEMERAL" in errors(api, bot)


def test_duplicate_env_keys_rejected(tmp_path):
    file = tmp_path / "env"
    file.write_text("PILOT_API_KEY=a\nPILOT_API_KEY=b\n")
    with pytest.raises(ValueError, match="Duplicate"):
        parse_env_file(file)


def test_cli_does_not_echo_secret_on_invalid_env(tmp_path, capsys):
    api = tmp_path / "api.env"
    bot = tmp_path / "bot.env"
    api.write_text("PILOT_API_KEY=secret-not-to-echo\nPILOT_API_KEY=duplicate\n")
    bot.write_text("TELEGRAM_BOT_TOKEN=test\n")
    assert main(["--api-env", str(api), "--bot-env", str(bot)]) == 2
    out = capsys.readouterr()
    assert "secret-not-to-echo" not in out.out + out.err
