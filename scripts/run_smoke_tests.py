from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.annotation import jaccard_similarity, reject_pseudo_label_columns, validate_score
from src.corpus import legal_filter, make_splits, normalize_text
from src.dapt import deterministic_mask_record
from src.models import resolve_checkpoint


class TinyTokenizer:
    all_special_ids = [0, 1, 2, 3]
    vocab_size = 50
    mask_token_id = 3

    def __call__(self, text, truncation=True, max_length=8, padding="max_length", return_attention_mask=True, add_special_tokens=True):
        ids = [1] + [10 + (ord(token[0]) % 20) for token in text.split()[: max_length - 2]] + [2]
        ids = ids[:max_length]
        mask = [1] * len(ids)
        while len(ids) < max_length:
            ids.append(0)
            mask.append(0)
        return {"input_ids": ids, "attention_mask": mask}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lightweight synthetic smoke checks without downloading large models.")
    parser.parse_args()
    assert normalize_text("  заң   және   құқық ") == "заң және құқық"
    assert legal_filter("Шарты: бос торкөздерге жоқ сандарды қою.")[0] is False
    assert legal_filter("Сот қылмыстық іс бойынша жаңа қаулы шығарды.")[0] is True
    assert jaccard_similarity("заң сот", "заң қаулы") == 1 / 3
    validate_score("5")
    try:
        validate_score("6")
        raise AssertionError("score validation failed")
    except ValueError:
        pass
    try:
        reject_pseudo_label_columns(pd.DataFrame({"pseudo_label": [1]}))
        raise AssertionError("pseudo-label guard failed")
    except ValueError:
        pass
    record_a = deterministic_mask_record("сот қаулы заң", "s1", TinyTokenizer(), "mbert", 42, 8, 0.5)
    record_b = deterministic_mask_record("сот қаулы заң", "s1", TinyTokenizer(), "mbert", 42, 8, 0.5)
    assert record_a == record_b
    assert resolve_checkpoint("mbert", "base") == "bert-base-multilingual-cased"
    try:
        resolve_checkpoint("mbert", "dapt")
        raise AssertionError("DAPT missing-checkpoint guard failed")
    except FileNotFoundError:
        pass
    print("Synthetic smoke tests passed.")


if __name__ == "__main__":
    main()
