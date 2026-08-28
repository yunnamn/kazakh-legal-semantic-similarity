from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .utils import ensure_parent, get_path, load_config, write_json


HIGH_PRECISION_LEGAL_ROOTS = {
    "заң",
    "сот",
    "қылмыс",
    "жаза",
    "кодекс",
    "құқық",
    "прокурор",
    "адвокат",
    "соттал",
    "айыппұл",
    "қаулы",
    "жауапкершілік",
    "тергеу",
    "күдікті",
    "қамау",
}

AMBIGUOUS_LEGAL_ROOTS = {"шарт", "міндет", "неке", "мүлік", "айып", "іс"}

WORD_RE = re.compile(
    r"[A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]+"
    r"(?:[-'][A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]+)*"
)
DEDUP_TOKEN_RE = re.compile(
    r"\d+(?:[.,]\d+)?|"
    r"[A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]+"
    r"(?:[-'][A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]+)*"
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
SPLITS = ("train", "validation", "mlm_test", "annotation_pool")


def normalize_text(text: str) -> str:
    text = "" if text is None else str(text)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]


def word_tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(normalize_text(text))]


def root_hits(tokens: Sequence[str], roots: set[str]) -> set[str]:
    hits: set[str] = set()
    for token in tokens:
        for root in roots:
            if token.startswith(root):
                hits.add(root)
    return hits


def legal_filter(sentence: str) -> tuple[bool, set[str], str]:
    tokens = word_tokens(sentence)
    high = root_hits(tokens, HIGH_PRECISION_LEGAL_ROOTS)
    ambiguous = root_hits(tokens, AMBIGUOUS_LEGAL_ROOTS)
    if high:
        return True, high | ambiguous, "high"
    if len(ambiguous) >= 2:
        return True, ambiguous, "weak"
    return False, high | ambiguous, "rejected"


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_dedup_text(text: str) -> str:
    text = normalize_text(text).lower()
    return " ".join(m.group(0) for m in DEDUP_TOKEN_RE.finditer(text))


def dedup_hash(text: str) -> str:
    return stable_hash(canonical_dedup_text(text))


def _iter_c4_rows(config: dict):
    from datasets import load_dataset

    return load_dataset(
        config["source"]["dataset"],
        config["source"]["configuration"],
        split=config["source"]["split"],
        streaming=True,
    )


def build_corpus_from_c4(config: dict | None = None) -> pd.DataFrame:
    config = config or load_config()
    save_path = get_path(config, "corpus_jsonl")
    rows: list[dict] = []
    seen: set[str] = set()
    max_sentences = int(config["corpus"]["max_candidate_sentences"])
    min_words = int(config["corpus"]["min_words"])
    max_words = int(config["corpus"]["max_words"])

    for row_index, row in enumerate(_iter_c4_rows(config)):
        raw = row.get("text", "")
        for sent_index, sentence in enumerate(split_sentences(raw)):
            tokens = word_tokens(sentence)
            if not (min_words <= len(tokens) <= max_words):
                continue
            accepted, hits, confidence = legal_filter(sentence)
            if not accepted:
                continue
            normalized = normalize_text(sentence)
            near_hash = dedup_hash(normalized)
            if near_hash in seen:
                continue
            seen.add(near_hash)
            rows.append(
                {
                    "sentence_id": f"c4kk-{near_hash[:16]}",
                    "text": normalized,
                    "text_hash": stable_hash(normalized.lower()),
                    "dedup_hash": near_hash,
                    "source_url": row.get("url"),
                    "source_row_index": row_index,
                    "source_sentence_index": sent_index,
                    "matched_keywords": sorted(hits),
                    "filter_confidence": confidence,
                }
            )
            if len(rows) >= max_sentences:
                break
        if len(rows) >= max_sentences:
            break

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No sentences collected. Check dataset and filtering settings.")
    write_jsonl(save_path, df.to_dict(orient="records"))
    write_json(get_path(config, "corpus_statistics"), corpus_statistics(df, config))
    return df


def corpus_statistics(df: pd.DataFrame, config: dict | None = None) -> dict:
    config = config or load_config()
    return {
        "n_sentences": int(len(df)),
        "n_unique_text_hashes": int(df["text_hash"].nunique()),
        "n_unique_dedup_hashes": int(df["dedup_hash"].nunique()),
        "mean_words": float(df["text"].map(lambda x: len(word_tokens(x))).mean()),
        "filter_confidence": df["filter_confidence"].value_counts().to_dict(),
        "keyword_counts": dict(Counter(k for ks in df["matched_keywords"] for k in ks)),
        "source_dataset": config["source"]["dataset"],
        "source_config": config["source"]["configuration"],
        "corpus_description": "weakly filtered Kazakh legal-domain candidate corpus",
    }


def write_jsonl(path: str | Path, records: list[dict]) -> None:
    path = ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_jsonl(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found.")
    return pd.read_json(path, lines=True)


def load_corpus(config: dict | None = None) -> pd.DataFrame:
    config = config or load_config()
    return load_jsonl(get_path(config, "corpus_jsonl"))


def split_bucket(sentence_id: str, seed: int = 42) -> float:
    digest = hashlib.sha256(f"{seed}|{sentence_id}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(16**16 - 1)


def assign_split(sentence_id: str, config: dict | None = None) -> str:
    config = config or load_config()
    ratios = config["splits"]
    x = split_bucket(sentence_id, int(config["seed"]))
    a = float(ratios["train"])
    b = a + float(ratios["validation"])
    c = b + float(ratios["mlm_test"])
    if x < a:
        return "train"
    if x < b:
        return "validation"
    if x < c:
        return "mlm_test"
    return "annotation_pool"


def validate_split_ratios(config: dict) -> None:
    total = sum(float(config["splits"][name]) for name in SPLITS)
    if not np.isclose(total, 1.0):
        raise ValueError(f"Split ratios must sum to 1.0, got {total}")


def check_no_split_overlap(df: pd.DataFrame) -> None:
    groups = {name: set(part["dedup_hash"]) for name, part in df.groupby("split")}
    names = list(groups)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            overlap = groups[left] & groups[right]
            if overlap:
                raise AssertionError(
                    f"Near-exact text leakage between {left} and {right}: {len(overlap)}"
                )


def make_splits(corpus_df: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    config = config or load_config()
    validate_split_ratios(config)
    df = corpus_df.copy()
    for col in ["sentence_id", "text_hash", "dedup_hash"]:
        if df[col].duplicated().any():
            raise ValueError(f"Duplicate {col} values found before splitting.")
    df["split"] = df["sentence_id"].map(lambda sid: assign_split(sid, config))
    check_no_split_overlap(df)
    for split_name in SPLITS:
        part = df[df["split"] == split_name].drop(columns=["split"])
        write_jsonl(get_path(config, f"{split_name}_jsonl"), part.to_dict(orient="records"))
    metadata = {
        "seed": int(config["seed"]),
        "ratios": {name: float(config["splits"][name]) for name in SPLITS},
        "counts": df["split"].value_counts().to_dict(),
        "corpus_hash": stable_hash("\n".join(sorted(df["dedup_hash"]))),
    }
    write_json(get_path(config, "split_metadata"), metadata)
    return df


def load_split(name: str, config: dict | None = None) -> pd.DataFrame:
    if name not in SPLITS:
        raise ValueError(f"Unknown split: {name}")
    config = config or load_config()
    return load_jsonl(get_path(config, f"{name}_jsonl"))
