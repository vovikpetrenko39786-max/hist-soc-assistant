"""Test-only compatibility shim for environments where pgvector is not installed.

Production declares pgvector as a required dependency. The execution sandbox used to
validate this source tree can be offline, so unit tests that do not exercise vector
SQL receive a harmless SQLAlchemy JSON stand-in.
"""
import sys
import types

try:
    import pgvector.sqlalchemy  # noqa: F401
except ModuleNotFoundError:
    from sqlalchemy import JSON

    pkg = types.ModuleType("pgvector")
    sub = types.ModuleType("pgvector.sqlalchemy")

    class Vector(JSON):
        pass

    sub.Vector = Vector
    pkg.sqlalchemy = sub
    sys.modules["pgvector"] = pkg
    sys.modules["pgvector.sqlalchemy"] = sub
