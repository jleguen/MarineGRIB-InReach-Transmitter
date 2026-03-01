import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _block_real_inreach_post(monkeypatch):
    from src import inreach_functions

    def _blocked_post(*_args, **_kwargs):
        raise AssertionError("Real network POST is disabled during tests")

    monkeypatch.setattr(inreach_functions.requests, "post", _blocked_post)
