from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .corpus import load_split
from .models import model_specs, resolve_checkpoint
from .utils import get_path, load_config


def seed_from_parts(*parts: object) -> int:
    raw = "|".join(map(str, parts))
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], 16) % (2**31 - 1)


def deterministic_mask_record(
    text: str,
    sentence_id: str,
    tokenizer,
    model_key: str,
    seed: int,
    max_length: int,
    mlm_probability: float,
) -> dict:
    encoded = tokenizer(
        text,
        truncation=True,
        max_length=max_length,
        padding="max_length",
        return_attention_mask=True,
        add_special_tokens=True,
    )
    input_ids = np.array(encoded["input_ids"], dtype=np.int64)
    attention_mask = np.array(encoded["attention_mask"], dtype=np.int64)
    labels = np.full_like(input_ids, -100)
    special_ids = set(tokenizer.all_special_ids)
    positions = [
        i
        for i, (tok_id, attn) in enumerate(zip(input_ids, attention_mask))
        if attn == 1 and int(tok_id) not in special_ids
    ]
    if not positions:
        raise ValueError("No maskable tokens produced.")
    rng = np.random.default_rng(seed_from_parts(seed, model_key, sentence_id))
    n_mask = max(1, int(round(len(positions) * mlm_probability)))
    n_mask = min(n_mask, len(positions))
    chosen = rng.choice(positions, size=n_mask, replace=False)
    labels[chosen] = input_ids[chosen]
    vocab_size = int(tokenizer.vocab_size)
    for pos in chosen:
        r = rng.random()
        if r < 0.80:
            if tokenizer.mask_token_id is None:
                raise ValueError(f"{model_key} tokenizer has no mask token.")
            input_ids[pos] = tokenizer.mask_token_id
        elif r < 0.90:
            input_ids[pos] = int(rng.integers(0, vocab_size))
    return {
        "sentence_id": sentence_id,
        "input_ids": input_ids.tolist(),
        "attention_mask": attention_mask.tolist(),
        "labels": labels.tolist(),
    }


def build_deterministic_masked_dataset(
    df: pd.DataFrame,
    tokenizer,
    model_key: str,
    config: dict | None = None,
):
    from datasets import Dataset

    config = config or load_config()
    records = []
    for row in df.itertuples(index=False):
        try:
            records.append(
                deterministic_mask_record(
                    row.text,
                    row.sentence_id,
                    tokenizer,
                    model_key,
                    int(config["seed"]),
                    int(config["mlm"]["max_sequence_length"]),
                    float(config["mlm"]["probability"]),
                )
            )
        except ValueError:
            continue
    if not records:
        raise RuntimeError("No maskable held-out examples produced.")
    return Dataset.from_list(records)


def fixed_batch_collator(features: list[dict]):
    import torch

    return {
        "input_ids": torch.tensor([f["input_ids"] for f in features], dtype=torch.long),
        "attention_mask": torch.tensor([f["attention_mask"] for f in features], dtype=torch.long),
        "labels": torch.tensor([f["labels"] for f in features], dtype=torch.long),
    }


def tokenize_unmasked_dataset(df: pd.DataFrame, tokenizer, config: dict | None = None):
    from datasets import Dataset

    config = config or load_config()
    ds = Dataset.from_pandas(df[["text"]], preserve_index=False)

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=int(config["mlm"]["max_sequence_length"]),
            return_special_tokens_mask=True,
        )

    return ds.map(tokenize, batched=True, remove_columns=["text"])


def train_dapt(model_key: str, config: dict | None = None) -> dict:
    import matplotlib.pyplot as plt
    import pandas as pd
    from torch.utils.data import DataLoader
    from transformers import AutoModelForMaskedLM, AutoTokenizer, DataCollatorForLanguageModeling
    from transformers import Trainer, TrainingArguments

    config = config or load_config()
    specs = model_specs(config)
    if model_key == "labse" or not specs[model_key]["supports_mlm"]:
        raise ValueError(f"{model_key} is not part of MLM DAPT.")

    train_df = load_split("train", config)
    val_df = load_split("validation", config)
    tokenizer = AutoTokenizer.from_pretrained(specs[model_key]["base_id"])
    model = AutoModelForMaskedLM.from_pretrained(specs[model_key]["base_id"])
    train_ds = tokenize_unmasked_dataset(train_df, tokenizer, config)
    val_masked_ds = build_deterministic_masked_dataset(val_df, tokenizer, model_key, config)
    train_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=True,
        mlm_probability=float(config["mlm"]["probability"]),
    )

    out_dir = Path(specs[model_key]["adapted_dir"])
    trainer_dir = out_dir.parent / f".{out_dir.name}-trainer"
    trainer_dir.mkdir(parents=True, exist_ok=True)
    train_cfg = config["training"]
    args = TrainingArguments(
        output_dir=str(trainer_dir),
        overwrite_output_dir=True,
        max_steps=int(train_cfg["max_steps"]),
        per_device_train_batch_size=int(train_cfg["train_batch_size"]),
        per_device_eval_batch_size=int(train_cfg["eval_batch_size"]),
        learning_rate=float(train_cfg["learning_rate"]),
        warmup_ratio=float(train_cfg["warmup_ratio"]),
        eval_strategy="steps",
        eval_steps=int(train_cfg["eval_steps"]),
        save_strategy="steps",
        save_steps=int(train_cfg["checkpoint_steps"]),
        logging_steps=max(10, int(train_cfg["eval_steps"]) // 2),
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        save_total_limit=2,
        report_to=[],
        seed=int(config["seed"]),
        data_seed=int(config["seed"]),
    )

    class DAPTTrainer(Trainer):
        def get_eval_dataloader(self, eval_dataset=None):
            dataset = eval_dataset if eval_dataset is not None else self.eval_dataset
            return DataLoader(
                dataset,
                batch_size=self.args.per_device_eval_batch_size,
                shuffle=False,
                collate_fn=fixed_batch_collator,
            )

    trainer = DAPTTrainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_masked_ds,
        data_collator=train_collator,
        processing_class=tokenizer,
    )
    train_output = trainer.train()
    out_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    history = pd.DataFrame(trainer.state.log_history)
    metrics_dir = get_path(config, "metrics_dir")
    figures_dir = get_path(config, "figures_dir")
    history.to_csv(metrics_dir / f"{model_key}_dapt_history.csv", index=False)
    metadata = {
        "model": model_key,
        "base_id": specs[model_key]["base_id"],
        "adapted_dir": str(out_dir),
        "best_model_checkpoint": trainer.state.best_model_checkpoint,
        "best_metric": trainer.state.best_metric,
        "train_runtime": getattr(train_output, "metrics", {}).get("train_runtime"),
        "max_steps": int(train_cfg["max_steps"]),
        "seed": int(config["seed"]),
    }
    (metrics_dir / f"{model_key}_dapt_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    if "loss" in history.columns or "eval_loss" in history.columns:
        plt.figure(figsize=(7, 4))
        if "loss" in history.columns:
            h = history.dropna(subset=["loss"])
            if not h.empty:
                plt.plot(h["step"], h["loss"], label="train loss")
        if "eval_loss" in history.columns:
            h = history.dropna(subset=["eval_loss"])
            if not h.empty:
                plt.plot(h["step"], h["eval_loss"], label="validation loss")
        plt.xlabel("Step")
        plt.ylabel("MLM loss")
        plt.title(f"{specs[model_key]['display_name']} DAPT training history")
        plt.legend()
        plt.tight_layout()
        plt.savefig(figures_dir / f"{model_key}_dapt_history.png", dpi=160)
    return metadata


def evaluate_mlm_checkpoint(model_key: str, variant: str, test_df: pd.DataFrame, config: dict | None = None) -> dict:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForMaskedLM, AutoTokenizer

    config = config or load_config()
    specs = model_specs(config)
    source = resolve_checkpoint(model_key, variant, require_exists=(variant == "dapt"), config=config)
    tokenizer = AutoTokenizer.from_pretrained(specs[model_key]["base_id"])
    masked_ds = build_deterministic_masked_dataset(test_df, tokenizer, model_key, config)
    model = AutoModelForMaskedLM.from_pretrained(source)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()
    loader = DataLoader(
        masked_ds,
        batch_size=int(config["training"]["eval_batch_size"]),
        shuffle=False,
        collate_fn=fixed_batch_collator,
    )
    weighted_loss = 0.0
    n_masked = 0
    with torch.no_grad():
        for batch in loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            output = model(**batch)
            masked = int((batch["labels"] != -100).sum().item())
            weighted_loss += float(output.loss.item()) * masked
            n_masked += masked
    return {
        "model": model_key,
        "display_name": specs[model_key]["display_name"],
        "variant": variant,
        "resolved_source": source,
        "mlm_loss": weighted_loss / max(n_masked, 1),
        "n_examples": len(masked_ds),
        "n_masked_tokens": n_masked,
        "mask_seed": int(config["seed"]),
    }

