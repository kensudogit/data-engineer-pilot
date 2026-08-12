from __future__ import annotations

import pytest

from src.data.synth import SyntheticDataset, generate_dataset

SEED = 42


@pytest.fixture(scope="session")
def dataset() -> SyntheticDataset:
    """Session-scoped: generation + downstream model training is nontrivial
    work (~a few seconds total across all 5 services), and every test in
    this suite operates on the same seed=42 dataset anyway."""
    return generate_dataset(seed=SEED)
