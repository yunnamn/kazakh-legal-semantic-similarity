"""Strict configuration parsing: reject misspelled or unsupported corpus policies."""
from __future__ import annotations
import math
import tomllib
from pathlib import Path
from .errors import CorpusError

SPLITS = ("train", "validation", "mlm_test", "annotation_pool")


def load_config(path: Path) -> dict:
    with Path(path).open("rb") as handle:
        value = tomllib.load(handle)
    schema = {
        "": {"schema_version", "profile", "allow_reused_text", "keep_editorial_notes",
             "quarantine_chunk_boundary_sentences", "split", "dedup", "release"},
        "split": {"seed", "weights"},
        "dedup": {"near_jaccard", "shingle_words", "min_near_words", "min_informative_shared_words",
                  "max_shared_families", "overlap_words", "max_candidates_per_unit"},
        "release": {"require_all_splits_nonempty", "max_component_fraction", "minimum_reviewed_documents_per_source"},
    }
    for key, expected in schema.items():
        section = value if not key else value.get(key)
        if not isinstance(section, dict) or set(section) != expected:
            raise CorpusError(f"Missing or unknown configuration keys in {key or 'root'}; see configs/pipeline.toml")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise CorpusError("Unsupported corpus configuration schema")
    if not isinstance(value["profile"], str) or not value["profile"].strip():
        raise CorpusError("A named corpus profile is required")
    for key in ("allow_reused_text", "keep_editorial_notes", "quarantine_chunk_boundary_sentences"):
        if type(value[key]) is not bool:
            raise CorpusError(f"{key} must be a Boolean")
    if type(value["release"]["require_all_splits_nonempty"]) is not bool:
        raise CorpusError("require_all_splits_nonempty must be a Boolean")
    if not isinstance(value["split"]["seed"], str) or not value["split"]["seed"].strip():
        raise CorpusError("A nonempty deterministic split seed is required")
    weights = value["split"]["weights"]
    if not isinstance(weights, dict) or set(weights) != set(SPLITS) or any(type(v) is not int or v <= 0 for v in weights.values()):
        raise CorpusError("Exactly four positive integer split weights are required")
    if sum(weights.values()) != 10000:
        raise CorpusError("Split weights must sum to 10000")
    dedup = value["dedup"]
    threshold = dedup["near_jaccard"]
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0.5 <= threshold <= 1:
        raise CorpusError("near_jaccard must be in [0.5, 1]")
    for key in set(dedup) - {"near_jaccard"}:
        if type(dedup[key]) is not int or dedup[key] <= 0:
            raise CorpusError(f"{key} must be a positive integer")
    if dedup["min_near_words"] < dedup["shingle_words"]:
        raise CorpusError("Invalid shingle/minimum word lengths")
    if dedup["overlap_words"] < 8:
        raise CorpusError("Contiguous overlap windows must contain at least 8 words")
    fraction = value["release"]["max_component_fraction"]
    if type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0 < fraction <= 1:
        raise CorpusError("Invalid component-size limit")
    qa_count = value["release"]["minimum_reviewed_documents_per_source"]
    if type(qa_count) is not int or qa_count <= 0:
        raise CorpusError("Human QA sample size must be a positive integer")
    return value
