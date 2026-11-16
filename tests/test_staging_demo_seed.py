import os

import pytest

from scripts.staging_demo_seed import DEMO_DATASET_ID, validate_staging_environment


def valid_environment() -> dict[str, str]:
    return {
        "APP_ENV": "staging",
        "DEMO_SEED_ENABLED": "true",
        "DEMO_DATASET_ID": DEMO_DATASET_ID,
        "RAILWAY_ENVIRONMENT_NAME": "staging",
    }


def test_demo_seed_accepts_only_explicit_staging_profile():
    validate_staging_environment(valid_environment())


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APP_ENV", "production"),
        ("DEMO_SEED_ENABLED", "false"),
        ("DEMO_DATASET_ID", "unexpected"),
        ("RAILWAY_ENVIRONMENT_NAME", "production"),
    ],
)
def test_demo_seed_rejects_unsafe_environment(name, value):
    environment = valid_environment()
    environment[name] = value
    with pytest.raises(RuntimeError):
        validate_staging_environment(environment)


def test_demo_seed_does_not_depend_on_process_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    validate_staging_environment(valid_environment())
    assert os.environ["APP_ENV"] == "production"
