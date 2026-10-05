from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


@pytest.fixture
def examples() -> Path:
    return EXAMPLES


def valid_examples():
    return sorted(p for p in (EXAMPLES / "valid").iterdir() if p.is_dir())
