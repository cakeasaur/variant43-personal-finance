"""Smoke tests: verify entrypoint and critical modules import without error."""
import importlib
import importlib.util
from pathlib import Path

import pytest


@pytest.mark.skipif(
    importlib.util.find_spec("flet") is None,
    reason="flet not installed in this environment",
)
def test_entrypoint_importable() -> None:
    """main_flet.py must load without ImportError."""
    spec = importlib.util.spec_from_file_location(
        "main_flet", Path(__file__).resolve().parents[1] / "main_flet.py"
    )
    assert spec is not None, "main_flet.py not found"
    module = importlib.util.module_from_spec(spec)
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
    importlib.util.find_spec("flet") is None,
    reason="flet not installed in this environment",
)
def test_flet_ui_importable() -> None:
    """src.ui_flet must expose all screen builders when flet is available."""
    from src.ui_flet.screens.goals import build_goals
    from src.ui_flet.screens.operations import build_operations
    from src.ui_flet.screens.overview import build_overview
    from src.ui_flet.screens.reminders import build_reminders
    from src.ui_flet.screens.reports import build_reports
    assert all([build_overview, build_operations, build_goals, build_reminders, build_reports])
