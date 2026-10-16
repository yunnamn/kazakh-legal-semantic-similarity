"""Read immutable, QA-approved corpus-pipeline exports without resplitting them."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .corpus import SPLITS, dedup_hash, legal_filter
from .utils import project_path


def load_training_view(name: str, directory: str | Path) -> pd.DataFrame:
    """Keep provenance and identities; accept JSONL research exports only.

    Hashes detect accidental edits, not source authenticity or a forged approval.
    Source review and human QA remain responsibilities of the export workflow.
    """
    from kazlegal_corpus.integrity import verify_artifacts
    from kazlegal_corpus.io import iter_jsonl, read_json

    root = project_path(str(directory))
    manifest = verify_artifacts(root)
    if (manifest.get("schema_version") != 1
            or manifest.get("stage") != "training_view_not_new_similarity_evaluation"
            or manifest.get("format") != "jsonl"):
        raise ValueError("Use a JSONL training view from kazlegal-corpus export, not intermediate splits.")
    required = {"validation.json", "attributions_and_rights.json"}
    required.update(f"{role}{suffix}" for role in SPLITS for suffix in (".jsonl", ".provenance.jsonl"))
    if not required <= manifest.get("files", {}).keys():
        raise ValueError("Training view is missing required manifest entries.")
    if (set(manifest.get("roles", {})) != set(SPLITS)
            or not manifest.get("experiment_id") or not manifest.get("qa_review_sha256")):
        raise ValueError("Training view lacks experiment, role or human-QA provenance.")
    validation = read_json(root / "validation.json")
    if (validation.get("training_view_ready") is not True
            or validation.get("structural_checks") != "passed"
            or validation.get("independent_overlap_checks") != "passed"
            or validation.get("original_experiment_verified") is not True
            or validation.get("release_blockers_before_human_qa") != []
            or validation.get("derived_build_id") != manifest.get("derived_build_id")
            or validation.get("human_qa", {}).get("reviewed_source_document_samples", 0) <= 0):
        raise ValueError("Training view has not passed experiment, overlap and human-QA validation.")

    selected = []
    sentence_ids: set[str] = set()
    assignments: dict[tuple[str, str], str] = {}
    for role in SPLITS:
        rows = list(iter_jsonl(root / f"{role}.jsonl"))
        lineage = list(iter_jsonl(root / f"{role}.provenance.jsonl"))
        if len(rows) != len(lineage) or not rows:
            raise ValueError(f"Empty split or misaligned provenance: {role}")
        for line, (row, provenance) in enumerate(zip(rows, lineage), 1):
            text = row.get("text")
            identity = row.get("sentence_id")
            if not isinstance(text, str) or not text.strip() or not isinstance(identity, str) or not identity:
                raise ValueError(f"Invalid sentence in {role}, line {line}.")
            if (row.get("test_only") is not False or "TEST_ONLY" in text
                    or row.get("split") != role or row.get("quarantine_reasons") != []
                    or row.get("language") != "kk" or not row.get("provenance")):
                raise ValueError(f"Non-research, quarantined or misplaced sentence: {identity}")
            expected = {"export_line": line, **{k: v for k, v in row.items() if k != "text"}}
            if provenance != expected:
                raise ValueError(f"Line-aligned provenance differs for {identity}.")
            if identity in sentence_ids:
                raise ValueError(f"Duplicate sentence identity: {identity}")
            sentence_ids.add(identity)
            keys = [(field, row.get(field)) for field in ("family_id", "component_id")]
            if any(not isinstance(value, str) or not value for _, value in keys):
                raise ValueError(f"Missing family/component identity: {identity}")
            keys += [("family_id", family) for family in row.get("source_family_ids", [])]
            keys.append(("text", dedup_hash(text)))
            for key in keys:
                if key in assignments and assignments[key] != role:
                    raise ValueError(f"Cross-split corpus leakage: {key[0]}")
                assignments[key] = role
            if role == name:
                # Keywords support existing pair sampling; they never filter official text.
                _, keywords, _ = legal_filter(text)
                selected.append({**row, "matched_keywords": sorted(keywords)})
    frame = pd.DataFrame(selected)
    frame.attrs["corpus_build_id"] = manifest["build_id"]
    frame.attrs["experiment_id"] = manifest["experiment_id"]
    return frame
