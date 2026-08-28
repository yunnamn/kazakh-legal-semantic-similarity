from __future__ import annotations

from src.dapt import deterministic_mask_record


class TinyTokenizer:
    all_special_ids = [0, 1, 2, 3]
    vocab_size = 50
    mask_token_id = 3

    def __call__(
        self,
        text,
        truncation=True,
        max_length=10,
        padding="max_length",
        return_attention_mask=True,
        add_special_tokens=True,
    ):
        pieces = text.split()
        ids = [1] + [10 + i for i, _ in enumerate(pieces[: max_length - 2])] + [2]
        ids = ids[:max_length]
        mask = [1] * len(ids)
        while len(ids) < max_length:
            ids.append(0)
            mask.append(0)
        return {"input_ids": ids, "attention_mask": mask}


def test_deterministic_mlm_masking():
    tokenizer = TinyTokenizer()
    first = deterministic_mask_record("сот қаулы заң құқық", "s1", tokenizer, "mbert", 42, 10, 0.5)
    second = deterministic_mask_record("сот қаулы заң құқық", "s1", tokenizer, "mbert", 42, 10, 0.5)
    assert first == second
    assert any(label != -100 for label in first["labels"])


def test_identical_evaluation_masks_for_base_and_dapt_within_family():
    tokenizer = TinyTokenizer()
    base_masks = deterministic_mask_record("сот қаулы заң құқық", "s1", tokenizer, "mbert", 42, 10, 0.5)
    dapt_masks = deterministic_mask_record("сот қаулы заң құқық", "s1", tokenizer, "mbert", 42, 10, 0.5)
    assert base_masks["labels"] == dapt_masks["labels"]
    assert base_masks["input_ids"] == dapt_masks["input_ids"]

