from __future__ import annotations

from pathlib import Path
from typing import Literal

from .utils import get_path, load_config


Variant = Literal["base", "dapt"]


def model_specs(config: dict | None = None) -> dict:
    config = config or load_config()
    models_dir = get_path(config, "models_dir")
    specs = {}
    for key, item in config["models"].items():
        specs[key] = {
            "display_name": item["display_name"],
            "base_id": item["base_id"],
            "adapted_dir": models_dir / item["adapted_dir"],
            "supports_mlm": bool(item["supports_mlm"]),
        }
    return specs


def resolve_checkpoint(
    model_key: str,
    variant: Variant,
    require_exists: bool = True,
    config: dict | None = None,
) -> str:
    specs = model_specs(config)
    if model_key not in specs:
        raise KeyError(f"Unknown model key: {model_key}")
    if variant not in {"base", "dapt"}:
        raise ValueError(f"Unknown checkpoint variant: {variant}")

    spec = specs[model_key]
    if variant == "base":
        return str(spec["base_id"])

    if model_key == "labse":
        raise ValueError(
            "LaBSE remains frozen in the core experiment. Optional adaptation is not MLM DAPT."
        )
    if not spec["supports_mlm"]:
        raise ValueError(f"{model_key} does not support MLM DAPT.")

    path = Path(spec["adapted_dir"])
    if require_exists and not (path / "config.json").exists():
        raise FileNotFoundError(
            f"Adapted checkpoint not found: {path}. Run DAPT first. "
            "No automatic fallback to the base model is allowed."
        )
    return str(path)


def load_mlm_model_and_tokenizer(model_key: str, variant: Variant, config: dict | None = None):
    from transformers import AutoModelForMaskedLM, AutoTokenizer

    specs = model_specs(config)
    source = resolve_checkpoint(model_key, variant, require_exists=(variant == "dapt"), config=config)
    tokenizer = AutoTokenizer.from_pretrained(specs[model_key]["base_id"])
    model = AutoModelForMaskedLM.from_pretrained(source)
    return model, tokenizer

