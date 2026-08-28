from __future__ import annotations

from typing import Sequence

import numpy as np

from .models import Variant, model_specs, resolve_checkpoint
from .utils import load_config


def mean_pool(last_hidden_state, attention_mask):
    mask = attention_mask.unsqueeze(-1).to(last_hidden_state.dtype)
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


def l2_normalize_array(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return values / norms


class TransformerSentenceEncoder:
    def __init__(self, model_key: str, variant: Variant, device: str | None = None, config: dict | None = None):
        if model_key == "labse":
            raise ValueError("Use LaBSEEncoder for LaBSE.")
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.config = config or load_config()
        specs = model_specs(self.config)
        self.model_key = model_key
        self.variant = variant
        self.source = resolve_checkpoint(model_key, variant, require_exists=(variant == "dapt"), config=self.config)
        self.tokenizer = AutoTokenizer.from_pretrained(specs[model_key]["base_id"])
        self.model = AutoModel.from_pretrained(self.source)
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model.to(self.device).eval()

    def encode(self, texts: Sequence[str], batch_size: int = 32) -> np.ndarray:
        import torch

        vectors = []
        for i in range(0, len(texts), batch_size):
            batch_texts = list(texts[i : i + batch_size])
            enc = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=int(self.config["mlm"]["max_sequence_length"]),
                return_tensors="pt",
            ).to(self.device)
            with torch.no_grad():
                out = self.model(**enc)
                pooled = mean_pool(out.last_hidden_state, enc["attention_mask"])
                pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            vectors.append(pooled.cpu().numpy())
        return np.vstack(vectors)


class LaBSEEncoder:
    def __init__(self, device: str | None = None, config: dict | None = None):
        from sentence_transformers import SentenceTransformer

        self.config = config or load_config()
        self.source = model_specs(self.config)["labse"]["base_id"]
        self.device = device
        self.model = SentenceTransformer(self.source, device=device)

    def encode(self, texts: Sequence[str], batch_size: int = 32) -> np.ndarray:
        return self.model.encode(
            list(texts),
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
            convert_to_numpy=True,
        )


def cosine_for_paired_embeddings(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if a.shape != b.shape:
        raise ValueError(f"Shape mismatch: {a.shape} vs {b.shape}")
    return np.sum(a * b, axis=1)

