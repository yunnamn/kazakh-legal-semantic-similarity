from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.annotation import jaccard_similarity, reject_pseudo_label_columns, validate_score


def test_annotation_candidate_scores_remain_blank():
    candidates = pd.DataFrame(
        {
            "pair_id": ["pair-0001"],
            "sentence_1_id": ["s1"],
            "sentence_2_id": ["s2"],
            "sentence_1": ["Сот қаулы шығарды."],
            "sentence_2": ["Заң күшіне енді."],
            "sampling_strategy": ["random_pair"],
            "similarity_score": [np.nan],
        }
    )
    assert candidates["similarity_score"].isna().all()
    reject_pseudo_label_columns(candidates)


def test_annotation_score_validation():
    assert validate_score("4.5") == 4.5
    with pytest.raises(ValueError):
        validate_score("-1")
    with pytest.raises(ValueError):
        validate_score("6")


def test_jaccard():
    assert jaccard_similarity("заң сот", "заң қаулы") == pytest.approx(1 / 3)
    assert jaccard_similarity("", "") == 1.0
    assert jaccard_similarity("заң", "") == 0.0


def test_pseudo_label_columns_rejected():
    with pytest.raises(ValueError):
        reject_pseudo_label_columns(pd.DataFrame({"pair_id": ["p1"], "pseudo_label": [1]}))

