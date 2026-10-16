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


@pytest.mark.parametrize("model_key,variant", [("mbert", "dapt"), ("labse", "base")])
def test_encoder_uses_selected_corpus_condition_config(monkeypatch, model_key, variant):
    import numpy as np
    import src.evaluation as evaluation

    config = {"paths": {"models_dir": "models/adilet"}}
    seen = []

    class Encoder:
        def __init__(self, *args, config=None):
            seen.append(config)

        def encode(self, texts):
            return np.array([[1.0, 0.0]] * len(texts))

    monkeypatch.setattr(evaluation, "LaBSEEncoder", Encoder)
    monkeypatch.setattr(evaluation, "TransformerSentenceEncoder", Encoder)
    pairs = pd.DataFrame({"pair_id": ["p1"], "sentence_1": ["сот"], "sentence_2": ["заң"]})
    scores = evaluation.score_pairs_with_encoder(pairs, model_key, variant, config=config)
    assert seen == [config]
    assert scores[f"{model_key}_{variant}"].tolist() == [1.0]

