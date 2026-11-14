"""Fail-safe release configuration checks for Hist-Soc Assistant.

This command NEVER changes Railway, secrets, files, or database data. It only
reads two caller-supplied env snapshots. Do not commit env snapshots to Git!
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from app.core.pilot_auth import is_strong_shared_key, parse_course_bindings
from telegram_bot.course_selection import parse_course_bindings as parse_bot_course_bindings


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
    elif not is_strong_shared_key(api_key) or not is_strong_shared_key(bot_key):
        add("PILOT_API_KEY_WEAK", "ERROR", "Shared API access key must be a generated high-entropy token of at least 43 characters.")
    elif api_key != bot_key:
        add("PILOT_API_KEY_MISMATCH", "ERROR", "Backend and bot have different shared API access keys.")
    else:
        add("PILOT_API_KEY", "INFO", "Shared API key is present and consistent.")

    token = bot.get("TELEGRAM_BOT_TOKEN", "")
    if not token or token.lower().startswith(("replace", "your", "example")):
        add("TELEGRAM_BOT_TOKEN", "ERROR", "Telegram bot token is not configured.")

    if api.get("APP_ENV", "").strip().casefold() not in {"prod", "production"}:
        add("APP_ENV_NOT_PRODUCTION", "ERROR", "Backend APP_ENV must identify production.")
    if api.get("AUTO_CREATE_TABLES", "").strip().casefold() not in {
        "false",
        "0",
        "no",
        "off",
    }:
        add(
            "AUTO_CREATE_TABLES_ENABLED",
            "ERROR",
            "Automatic schema creation must be disabled in production.",
        )

    allowlist = bot.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    allowed_tokens = re.split(r"[,;\s]+", allowlist) if allowlist else []
    if not allowed_tokens:
        add("TELEGRAM_ALLOWLIST_EMPTY", "ERROR", "No Telegram users are allowed; bot will refuse all requests.")
    elif not all(x.isascii() and x.isdecimal() and int(x) > 0 for x in allowed_tokens):
        add("TELEGRAM_ALLOWLIST_INVALID", "ERROR", "Telegram allowlist has an invalid user ID.")
    else:
        add("TELEGRAM_ALLOWLIST", "INFO", "Telegram allowlist has authorized user IDs.")
        api_allowlist = api.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
        api_tokens = re.split(r"[,;\s]+", api_allowlist) if api_allowlist else []
        if not api_tokens:
            add("BACKEND_ALLOWLIST_MISSING", "ERROR", "Backend Telegram allowlist is missing.")
        elif set(api_tokens) != set(allowed_tokens):
            add("ALLOWLIST_MISMATCH", "ERROR", "Backend and bot Telegram allowlists differ.")
        else:
            add("ALLOWLIST_MATCH", "INFO", "Backend and bot Telegram allowlists match.")

    api_bindings = api.get("TELEGRAM_COURSE_BINDINGS_JSON", "").strip()
    bot_bindings = bot.get("TELEGRAM_COURSE_BINDINGS_JSON", "").strip()
    try:
        parsed_api_bindings = json.loads(api_bindings) if api_bindings else {}
        parsed_bot_bindings = json.loads(bot_bindings) if bot_bindings else {}
        normalized_api_bindings = parse_course_bindings(api_bindings)
        normalized_bot_bindings = parse_bot_course_bindings(bot_bindings)
    except (TypeError, ValueError):
        add("COURSE_BINDINGS_INVALID", "ERROR", "Course bindings are not valid JSON.")
    else:
        if parsed_api_bindings != parsed_bot_bindings:
            add("COURSE_BINDINGS_MISMATCH", "ERROR", "Backend and bot course bindings differ.")
        elif normalized_api_bindings and normalized_bot_bindings:
            add("COURSE_BINDINGS_MATCH", "INFO", "Backend and bot course bindings match.")
        else:
            add("COURSE_BINDINGS_EMPTY", "ERROR", "No user-scoped courses are configured.")

    provider = api.get("GENERATION_PROVIDER", "").strip().casefold()
    provider_ready = (
        provider == "openai_responses" and bool(api.get("OPENAI_API_KEY", "").strip())
    ) or (
        provider == "http"
        and bool(api.get("GENERATION_HTTP_BASE_URL", "").strip())
        and bool(api.get("GENERATION_HTTP_API_KEY", "").strip())
    )
    if not provider_ready:
        add(
            "GENERATION_PROVIDER_NOT_READY",
            "ERROR",
            "A credentialed production generation provider is required.",
        )

    raw_dir = api.get("OUTPUT_STORAGE_DIR", "data/generated_outputs").strip()
    raw_mount = api.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if not raw_dir:
        add("OUTPUT_DIR_MISSING", "ERROR", "Output directory cannot be empty.")
    elif not raw_mount:
        add("OUTPUT_NOT_PROVEN_DURABLE", "ERROR", "No Railway volume mount is declared for backend output storage.")
    else:
        output = _absolute_path(raw_dir, app_dir)
        mount = _absolute_path(raw_mount, app_dir)
        if mount.parent == mount or not output.is_relative_to(mount):
            add("OUTPUT_EPHEMERAL", "ERROR", "Output directory is outside the backend's persistent Railway volume.")
        elif output == mount:
            add(
                "OUTPUT_MOUNT_ROOT",
                "ERROR",
                "Generated exports require a dedicated subdirectory inside the volume.",
            )
        else:
            add("OUTPUT_PERSISTENT", "INFO", "Output directory is inside a mounted Railway volume.")
            legacy_raw = api.get("OUTPUT_LEGACY_STORAGE_ROOTS_JSON", "[]")
            try:
                legacy_roots = json.loads(legacy_raw)
            except (TypeError, ValueError):
                add("LEGACY_OUTPUT_ROOTS_INVALID", "ERROR", "Legacy output roots are not valid JSON.")
            else:
                if not isinstance(legacy_roots, list) or len(legacy_roots) > 8:
                    add("LEGACY_OUTPUT_ROOTS_INVALID", "ERROR", "Legacy output roots must be a short JSON list.")
                elif any(
                    not isinstance(item, str)
                    or not Path(item).is_absolute()
                    or Path(item).resolve().parent == Path(item).resolve()
                    or not Path(item).resolve().is_relative_to(mount)
                    for item in legacy_roots
                ):
                    add("LEGACY_OUTPUT_ROOTS_UNSAFE", "ERROR", "Legacy output roots must stay inside the declared volume.")
                elif legacy_roots:
                    add("LEGACY_OUTPUT_ROOTS", "INFO", "Legacy output roots are explicitly read-only and volume-scoped.")

    admin_key = api.get("ADMIN_API_KEY", "")
    if not is_strong_shared_key(admin_key):
        add(
            "ADMIN_API_KEY_WEAK",
            "ERROR",
            "Administrator key must be a generated high-entropy token of at least 43 characters.",
        )
    elif admin_key == api_key and api_key:
        add("ADMIN_PILOT_KEY_REUSED", "ERROR", "Administrator and pilot API keys must be different.")

    confirmations = {
        "EXPORT_INVENTORY_CONFIRMED": "Read-only legacy export inventory has not been confirmed.",
        "EXPORT_BACKUP_CONFIRMED": "A restorable database and file backup has not been confirmed.",
        "OUTPUT_STORAGE_MIGRATION_CONFIRMED": "The output storage migration plan has not been confirmed.",
    }
    for name, message in confirmations.items():
        if api.get(name, "").strip().casefold() != "true":
            add(name, "ERROR", message)
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
