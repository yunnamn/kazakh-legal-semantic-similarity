from __future__ import annotations

import pandas as pd
import pytest

from src.corpus import (
    assign_split,
    canonical_dedup_text,
    check_no_split_overlap,
    dedup_hash,
    legal_filter,
    make_splits,
    normalize_text,
)


def _config(tmp_path):
    return {
        "seed": 42,
        "source": {"dataset": "allenai/c4", "configuration": "kk", "split": "train"},
        "splits": {"train": 0.80, "validation": 0.10, "mlm_test": 0.05, "annotation_pool": 0.05},
        "paths": {
            "train_jsonl": str(tmp_path / "train.jsonl"),
            "validation_jsonl": str(tmp_path / "validation.jsonl"),
            "mlm_test_jsonl": str(tmp_path / "mlm_test.jsonl"),
            "annotation_pool_jsonl": str(tmp_path / "annotation_pool.jsonl"),
            "split_metadata": str(tmp_path / "split_metadata.json"),
            "corpus_jsonl": str(tmp_path / "corpus.jsonl"),
            "corpus_statistics": str(tmp_path / "stats.json"),
        },
    }


def test_text_normalization():
    assert normalize_text("  <p>заң</p>\u00a0  және   құқық ") == "заң және құқық"


def test_legal_filter_accepts_high_precision_signal():
    accepted, hits, confidence = legal_filter("Сот қылмыстық іс бойынша жаңа қаулы шығарды.")
    assert accepted is True
    assert confidence == "high"
    assert {"сот", "қылмыс", "қаулы"} <= hits


def test_sharty_false_positive_rejected():
    assert legal_filter("Шарты: бос торкөздерге жоқ сандарды қою.")[0] is False


def test_conservative_deduplication_preserves_numbers():
    left = "Сот 2024 жылы қаулы шығарды."
    right = "Сот 2025 жылы қаулы шығарды."
    assert canonical_dedup_text(left) != canonical_dedup_text(right)
    assert dedup_hash(left) != dedup_hash(right)


def test_conservative_deduplication_ignores_case_spacing_and_punctuation():
    left = "Сот 2024 жылы қаулы шығарды!"
    right = "  сот   2024 жылы қаулы шығарды. "
    assert canonical_dedup_text(left) == canonical_dedup_text(right)
    assert dedup_hash(left) == dedup_hash(right)


def test_deterministic_splitting():
    assert assign_split("same-id") == assign_split("same-id")


def test_no_split_overlap_guard_detects_leakage():
    df = pd.DataFrame(
        [
            {"split": "train", "dedup_hash": "same"},
            {"split": "validation", "dedup_hash": "same"},
        ]
    )
    with pytest.raises(AssertionError):
        check_no_split_overlap(df)


def test_make_splits_writes_nonoverlapping_splits(tmp_path):
    rows = []
    for i in range(60):
        rows.append(
            {
                "sentence_id": f"s{i}",
                "text": f"Сот қаулы шығарды {i}",
                "text_hash": f"text-{i}",
                "dedup_hash": f"dedup-{i}",
                "matched_keywords": ["сот"],
                "filter_confidence": "high",
            }
        )
    split_df = make_splits(pd.DataFrame(rows), _config(tmp_path))
    assert set(split_df["split"]) <= {"train", "validation", "mlm_test", "annotation_pool"}
    check_no_split_overlap(split_df)
