from __future__ import annotations

import pandas as pd
import pytest

scipy = pytest.importorskip("scipy")

from src.evaluation import evaluate_score_column, safe_pearson, safe_spearman


def _config():
    return {"seed": 42, "evaluation": {"bootstrap_samples": 100}}


def test_correlation_calculations():
    assert safe_spearman([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert safe_pearson([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


def test_evaluate_score_column_returns_correlations():
    df = pd.DataFrame({"human_score": [0, 2, 5, 4], "system": [0.1, 0.3, 0.9, 0.8]})
    result = evaluate_score_column(df, "system", _config())
    assert result["system"] == "system"
    assert result["n_pairs"] == 4
    assert result["spearman"] > 0
    assert result["pearson"] > 0


def test_evaluation_rejects_pseudo_label_columns():
    df = pd.DataFrame({"human_score": [0, 1, 2], "system": [0.2, 0.3, 0.4], "pseudo_label": [0, 1, 1]})
    with pytest.raises(ValueError):
        evaluate_score_column(df, "system", _config())

