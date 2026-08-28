from __future__ import annotations

import numpy as np
import pytest

from src.embeddings import l2_normalize_array

torch = pytest.importorskip("torch")
from src.embeddings import mean_pool


def test_mean_pooling_ignores_padding():
    hidden = torch.tensor([[[1.0, 0.0], [3.0, 2.0], [999.0, 999.0]]])
    mask = torch.tensor([[1, 1, 0]])
    assert torch.allclose(mean_pool(hidden, mask), torch.tensor([[2.0, 1.0]]))


def test_embedding_normalization():
    vectors = l2_normalize_array(np.array([[3.0, 4.0], [0.0, 0.0]]))
    assert np.allclose(vectors[0], [0.6, 0.8])
    assert np.allclose(np.linalg.norm(vectors[0]), 1.0)
    assert np.allclose(vectors[1], [0.0, 0.0])

