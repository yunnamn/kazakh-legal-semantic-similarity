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


def test_project_dapt_trains_saves_and_evaluates_local_checkpoint(tmp_path, monkeypatch):
    """Exercise the pinned Transformers API without downloading or training a large model."""
    import math
    import pandas as pd
    import torch
    from transformers import BertConfig, BertForMaskedLM, BertTokenizer

    from src.dapt import evaluate_mlm_checkpoint, train_dapt
    from src.utils import load_config

    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mpl"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    base = tmp_path / "base"
    base.mkdir()
    (base / "vocab.txt").write_text('[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\nсот\nзаң\nқаулы\nқұқық\n', encoding="utf-8")
    tokenizer = BertTokenizer(vocab=str(base / "vocab.txt"))
    tokenizer.save_pretrained(base)
    model = BertForMaskedLM(BertConfig(vocab_size=len(tokenizer), hidden_size=16,
                                     num_hidden_layers=1, num_attention_heads=2, intermediate_size=32))
    model.save_pretrained(base)
    config = load_config()
    config["models"]["mbert"]["base_id"] = str(base)
    for key, path in config["paths"].items():
        config["paths"][key] = str(tmp_path / path)
    config["training"].update(max_steps=2, eval_steps=1, checkpoint_steps=1, train_batch_size=2, eval_batch_size=2)
    config["mlm"]["max_sequence_length"] = 8
    for name in ("train", "validation"):
        path = tmp_path / f"{name}.jsonl"
        pd.DataFrame([{"sentence_id": f"{name}-1", "text": "сот заң қаулы құқық"},
                      {"sentence_id": f"{name}-2", "text": "заң сот құқық қаулы"}]).to_json(path, orient="records", lines=True, force_ascii=False)
        config["paths"][f"{name}_jsonl"] = str(path)
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(2)
    try:
        metadata = train_dapt("mbert", config)
        held_out = pd.DataFrame([{"sentence_id": "held-out", "text": "сот заң құқық қаулы"}])
        result = evaluate_mlm_checkpoint("mbert", "dapt", held_out, config)
    finally:
        torch.set_num_threads(previous_threads)
    assert math.isfinite(metadata["best_metric"])
    assert math.isfinite(result["mlm_loss"])
    assert result["n_examples"] == 1 and result["n_masked_tokens"] > 0
    assert (tmp_path / "models" / "mbert-dapt" / "config.json").is_file()

