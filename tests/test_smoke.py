"""Smoke tests: verify entrypoint and critical modules import without error."""
import importlib
import importlib.util
from pathlib import Path

import pytest


def test_entrypoint_importable() -> None:
    """main.py must load without ImportError (catches missing modules like md_app)."""
    spec = importlib.util.spec_from_file_location(
        "main", Path(__file__).resolve().parents[1] / "main.py"
    )
    assert spec is not None, "main.py not found"
    module = importlib.util.module_from_spec(spec)
    # exec_module runs top-level code but NOT __main__ block — enough to catch bad imports.
    spec.loader.exec_module(module)


def test_core_models_importable() -> None:
    """src.core.models must import without Kivy (pure Python domain layer)."""
    mod = importlib.import_module("src.core.models")
    assert hasattr(mod, "Transaction")
    assert hasattr(mod, "TransactionType")


def test_core_reporting_importable() -> None:
    """src.core.reporting must import without Kivy."""
    mod = importlib.import_module("src.core.reporting")
    assert hasattr(mod, "totals_for_period")


def test_infra_importable() -> None:
    """Infrastructure layer must import without Kivy."""
    mod = importlib.import_module("src.infra.db.repositories")
    assert hasattr(mod, "TransactionRepository")


def test_crypto_importable() -> None:
    """Crypto module must import cleanly."""
    mod = importlib.import_module("src.infra.security.crypto")
    assert hasattr(mod, "encrypt_bytes")
    assert hasattr(mod, "decrypt_bytes")


@pytest.mark.skipif(
    importlib.util.find_spec("kivy") is None,
    reason="kivy not installed in this environment",
)
def test_src_app_importable() -> None:
    """src.app must expose PersonalFinanceApp when Kivy is available."""
    mod = importlib.import_module("src.app")
    assert hasattr(mod, "PersonalFinanceApp")
