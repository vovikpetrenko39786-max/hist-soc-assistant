"""Initialize universal datasets for Pilot 1.0.

Run after the database is up and FastAPI has created tables.
Idempotent importers make repeated execution safe.
"""
import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(script: str):
    print(f"\n=== {script} ===")
    subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT, check=True)


if __name__ == "__main__":
    run("import_official_curricula.py")
    run("import_exam_mapping_2027.py")
    run("import_source_catalog.py")
    print("\nPilot datasets initialized.")
