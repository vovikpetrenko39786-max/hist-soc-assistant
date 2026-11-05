"""Fail-safe release configuration checks for Hist-Soc Assistant.

This command NEVER changes Railway, secrets, files, or database data. It only
reads two caller-supplied env snapshots. Do not commit env snapshots to Git!
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    code: str
    level: str  # ERROR, WARNING, INFO
    message: str


def parse_env_file(path: Path) -> dict[str, str]:
    """Minimal safe parser for flat KEY=value exports (never echo values)."""
    data: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        if item.startswith("export "):
            item = item[7:].strip()
        if "=" not in item:
            raise ValueError(f"Invalid env assignment at line {number} in {path.name}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z_][A-Z_0-9]*", key):
            raise ValueError(f"Invalid env key at line {number} in {path.name}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key in data:
            raise ValueError(f"Duplicate env key at line {number} in {path.name}")
        data[key] = value
    return data


def _absolute_path(raw: str, app_dir: str) -> Path:
    p = Path(raw)
    return (p if p.is_absolute() else Path(app_dir) / p).resolve()


def validate_release_configuration(
    api: dict[str, str],
    bot: dict[str, str],
    *,
    app_dir: str = "/app",
) -> list[Finding]:
    """Check only release blockers that can be established from env metadata.

    Doesn't prove full production readiness, tenant ownership, backups or tests.
    Sensitive values are NEVER included in returned Finding.message.
    """
    findings: list[Finding] = []

    def add(code: str, level: str, message: str) -> None:
        findings.append(Finding(code, level, message))

    api_key = api.get("PILOT_API_KEY", "")
    bot_key = bot.get("PILOT_API_KEY", "")
    if not api_key or not bot_key:
        add("PILOT_API_KEY_MISSING", "ERROR", "Shared API access key must be set in both services.")
    elif len(api_key) < 32 or len(bot_key) < 32:
        add("PILOT_API_KEY_WEAK", "ERROR", "Shared API access key must be at least 32 characters.")
    elif api_key != bot_key:
        add("PILOT_API_KEY_MISMATCH", "ERROR", "Backend and bot have different shared API access keys.")
    else:
        add("PILOT_API_KEY", "INFO", "Shared API key is present and consistent.")

    token = bot.get("TELEGRAM_BOT_TOKEN", "")
    if not token or token.lower().startswith(("replace", "your", "example")):
        add("TELEGRAM_BOT_TOKEN", "ERROR", "Telegram bot token is not configured.")

    allowlist = bot.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    allowed_tokens = re.split(r"[,;\s]+", allowlist) if allowlist else []
    if not allowed_tokens:
        add("TELEGRAM_ALLOWLIST_EMPTY", "ERROR", "No Telegram users are allowed; bot will refuse all requests.")
    elif not all(x.isascii() and x.isdecimal() and int(x) > 0 for x in allowed_tokens):
        add("TELEGRAM_ALLOWLIST_INVALID", "ERROR", "Telegram allowlist has an invalid user ID.")
    else:
        add("TELEGRAM_ALLOWLIST", "INFO", "Telegram allowlist has authorized user IDs.")

    raw_dir = api.get("OUTPUT_STORAGE_DIR", "data/generated_outputs").strip()
    raw_mount = api.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if not raw_dir:
        add("OUTPUT_DIR_MISSING", "ERROR", "Output directory cannot be empty.")
    elif not raw_mount:
        add("OUTPUT_NOT_PROVEN_DURABLE", "ERROR", "No Railway volume mount is declared for backend output storage.")
    else:
        output = _absolute_path(raw_dir, app_dir)
        mount = _absolute_path(raw_mount, app_dir)
        if mount == Path("/") or not output.is_relative_to(mount):
            add("OUTPUT_EPHEMERAL", "ERROR", "Output directory is outside the backend's persistent Railway volume.")
        else:
            add("OUTPUT_PERSISTENT", "INFO", "Output directory is inside a mounted Railway volume.")
            if output == mount:
                add("OUTPUT_MOUNT_ROOT", "WARNING", "Prefer a dedicated subdirectory for generated exports.")

    admin_key = api.get("ADMIN_API_KEY", "")
    if not admin_key or len(admin_key) < 32:
        add("ADMIN_API_KEY_WEAK", "WARNING", "Configure a strong separate administrator key.")
    elif admin_key == api_key and api_key:
        add("ADMIN_PILOT_KEY_REUSED", "WARNING", "Administrator and pilot API keys should be different.")

    add("EXPORT_MIGRATION", "WARNING", "Check existing exported_files.file_path records before changing OUTPUT_STORAGE_DIR; old files are not migrated automatically.")
    add("NO_DEPLOY_APPROVAL", "WARNING", "Passing this check does not replace full pytest, database backup, tenant security review or end-to-end tests.")
    return findings


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--api-env", type=Path, required=True, help="Backend env snapshot; local secure file only")
    cli.add_argument("--bot-env", type=Path, required=True, help="Bot env snapshot; local secure file only")
    cli.add_argument("--app-dir", default="/app")
    args = cli.parse_args(argv)
    try:
        findings = validate_release_configuration(
            parse_env_file(args.api_env),
            parse_env_file(args.bot_env),
            app_dir=args.app_dir,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Preflight input error: {type(exc).__name__}; check env files", file=sys.stderr)
        return 2

    for finding in findings:
        print(f"{finding.level}: {finding.code} — {finding.message}")
    failures = sum(f.level == "ERROR" for f in findings)
    print(f"Preflight config blockers: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
