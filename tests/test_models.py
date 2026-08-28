from __future__ import annotations

import pytest

from src.models import resolve_checkpoint


def _config(tmp_path):
    return {
        "paths": {"models_dir": str(tmp_path / "models")},
        "models": {
            "mbert": {
                "display_name": "mBERT",
                "base_id": "bert-base-multilingual-cased",
                "adapted_dir": "mbert-dapt",
                "supports_mlm": True,
            },
            "labse": {
                "display_name": "LaBSE",
                "base_id": "sentence-transformers/LaBSE",
                "adapted_dir": "labse-adapted-optional",
                "supports_mlm": False,
            },
        },
    }


def test_base_checkpoint_resolution(tmp_path):
    assert resolve_checkpoint("mbert", "base", config=_config(tmp_path)) == "bert-base-multilingual-cased"


def test_dapt_checkpoint_resolution_when_present(tmp_path):
    config = _config(tmp_path)
    checkpoint = tmp_path / "models" / "mbert-dapt"
    checkpoint.mkdir(parents=True)
    (checkpoint / "config.json").write_text("{}", encoding="utf-8")
    assert resolve_checkpoint("mbert", "dapt", config=config) == str(checkpoint)


def test_dapt_missing_checkpoint_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_checkpoint("mbert", "dapt", config=_config(tmp_path))


def test_adapted_checkpoint_never_silently_loads_base(tmp_path):
    config = _config(tmp_path)
    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_checkpoint("mbert", "dapt", config=config)
    assert "No automatic fallback" in str(excinfo.value)
    assert resolve_checkpoint("mbert", "base", config=config) not in str(excinfo.value).split("Adapted checkpoint not found:")[1]


def test_labse_dapt_rejected(tmp_path):
    with pytest.raises(ValueError):
        resolve_checkpoint("labse", "dapt", config=_config(tmp_path))

