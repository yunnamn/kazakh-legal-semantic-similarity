"""Keep the original semantic-similarity evaluation immutable and contamination-protected."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from .audit import git
from .config import load_config
from .errors import CorpusError
from .io import digest, file_sha, read_json, safe_relative, source_rows, timestamp, write_json
from .normalize import normalize, sentence_spans

REQUIRED_DESIGN = ("research_question", "model_conditions", "training_and_token_budget", "seeds",
                   "similarity_function_and_pooling", "metrics", "annotation_scheme",
                   "pair_sampling", "checkpoint_selection", "evaluation_roles")


def freeze_experiment(root: Path, inventory_path: Path, review_path: Path,
                      config_path: Path, output: Path) -> dict:
    inventory = read_json(inventory_path)
    review = read_json(review_path)
    if review.get("audit_inventory_sha256") != file_sha(inventory_path):
        raise CorpusError("Review must identify the exact local repository inventory")
    if not review.get("reviewer") or "REPLACE_" in review["reviewer"]:
        raise CorpusError("A real reviewer is required")
    timestamp(review["reviewed_at"])
    if review.get("preserve_original_semantic_evaluation") is not True:
        raise CorpusError("Original semantic-similarity design must be explicitly preserved")
    design = review.get("reconstructed_design", {})
    for name in REQUIRED_DESIGN:
        if not design.get(name) or "REPLACE_" in str(design[name]):
            raise CorpusError(f"The inspected experiment has not been reconstructed: missing {name}")
    if review.get("accepted_corpus_config_sha256") != digest(load_config(config_path)):
        raise CorpusError("Corpus policy is provisional until a reviewer accepts its exact configuration")
    statuses = review.get("file_reviews", {})
    for entry in inventory["files"]:
        item = statuses.get(entry["path"], {})
        if item.get("status") not in {"reviewed", "out_of_scope_with_reason"} or not item.get("note"):
            raise CorpusError(f"Unreviewed repository file: {entry['path']}")
        if not entry.get("sha256"):
            raise CorpusError("Resolve missing files, symlinks and submodules before freezing the experiment")
        if file_sha(safe_relative(root, entry["path"])) != entry["sha256"]:
            raise CorpusError("Repository changed after inventory; audit the new state")
        if entry.get("kind") == "git_lfs_pointer":
            raise CorpusError("Acquire actual Git LFS objects before claiming an audited experiment")
    if git(root, "rev-parse", "HEAD") != inventory["repository_commit"]:
        raise CorpusError("Repository commit changed after the audit")
    protected = review.get("protected_evaluation", [])
    if not protected:
        raise CorpusError("Declare the original semantic-evaluation artifacts; an empty guard is unsafe")
    for spec in protected:
        if spec.get("role") not in {"semantic_test", "semantic_validation", "annotation_holdout"}:
            raise CorpusError("Only explicit held-out semantic roles are accepted")
        if not isinstance(spec.get("text_fields"), list) or len(spec["text_fields"]) < 2:
            raise CorpusError("Protect both endpoints of each semantic-similarity pair")
        if not spec.get("id_field") or spec.get("format") not in {"csv", "jsonl", "json", "parquet"}:
            raise CorpusError("Declare existing pair IDs, text columns and file format; no automatic relabelling")
        path = safe_relative(root, spec["path"])
        spec["sha256"] = file_sha(path)
        seen = set()
        count = 0
        for row, _ in source_rows(path, spec["format"]):
            pair_id = row.get(spec["id_field"])
            if pair_id is None or str(pair_id) in seen:
                raise CorpusError("Original evaluation has missing/duplicate pair IDs; review without silently changing labels")
            seen.add(str(pair_id))
            for field in spec["text_fields"]:
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise CorpusError("Missing evaluation endpoint text")
            count += 1
        if count == 0:
            raise CorpusError("Protected evaluation artifact is empty")
        spec["pairs"] = count
    lock = {"schema_version": 1, "repository_commit": inventory["repository_commit"],
            "inventory_sha256": file_sha(inventory_path), "review": review,
            "repository_files": [{"path": f["path"], "sha256": f["sha256"]} for f in inventory["files"]],
            "corpus_config_sha256": digest(load_config(config_path)), "protected_evaluation": protected}
    lock["experiment_id"] = digest(lock)
    write_json(output, lock)
    return lock


def verify_experiment(root: Path, path: Path) -> dict:
    lock = read_json(path)
    if digest({k: v for k, v in lock.items() if k != "experiment_id"}) != lock.get("experiment_id"):
        raise CorpusError("Experiment lock was modified")
    if git(root, "rev-parse", "HEAD") != lock["repository_commit"]:
        raise CorpusError("Repository commit differs from the audited experiment")
    tracked = {p for p in git(root, "ls-files", "-z").split("\0") if p}
    if tracked != {item["path"] for item in lock["repository_files"]}:
        raise CorpusError("Tracked repository file set changed after the audit")
    for item in lock["repository_files"] + lock["protected_evaluation"]:
        current = safe_relative(root, item["path"])
        if not current.is_file() or file_sha(current) != item["sha256"]:
            raise CorpusError(f"Protected repository/evaluation artifact changed: {item['path']}")
    return lock


def evaluation_units(root: Path, lock: dict) -> Iterator[dict]:
    """Labels are never read/used. Only original IDs, endpoint text and source families."""
    for spec in lock["protected_evaluation"]:
        path = safe_relative(root, spec["path"])
        if file_sha(path) != spec["sha256"]:
            raise CorpusError("Evaluation changed while constructing its contamination guard")
        for row, locator in source_rows(path, spec["format"]):
            pair_id = str(row[spec["id_field"]])
            families = []
            for field in spec.get("family_fields", []):
                value = row.get(field)
                if not value:
                    continue
                values = value if isinstance(value, list) else [value]
                for v in values:
                    if not isinstance(v, str) or not re.match(r"^(adilet|zan):", v):
                        raise CorpusError("family_fields must contain explicit adilet:<ID> or zan:<ID>, not titles")
                    families.append(v)
            for side in spec["text_fields"]:
                text, _ = normalize(row[side])
                parent_id = digest([spec["sha256"], pair_id, side])
                yield {"unit_id": "eval:" + parent_id, "text": text, "family_ids": sorted(set(families)),
                       "kind": "evaluation_endpoint", "artifact_sha256": spec["sha256"], "pair_id": pair_id}
                for index, (start, end) in enumerate(sentence_spans(text)):
                    sentence = text[start:end]
                    if sentence != text:
                        yield {"unit_id": "eval:" + digest([parent_id, index]), "text": sentence,
                               "family_ids": sorted(set(families)), "kind": "evaluation_sentence",
                               "artifact_sha256": spec["sha256"], "pair_id": pair_id}


def make_review_template(inventory_path: Path, config_path: Path, output: Path) -> dict:
    """Populate inventory references only; no inspection, judgement or approval is invented."""
    inventory = read_json(inventory_path)
    review = {
        "audit_inventory_sha256": file_sha(inventory_path),
        "reviewer": None, "reviewed_at": None,
        "preserve_original_semantic_evaluation": False,
        "accepted_corpus_config_sha256": None,
        "proposed_corpus_config_sha256_for_review_only": digest(load_config(config_path)),
        "reconstructed_design": {key: None for key in REQUIRED_DESIGN},
        "file_reviews": {item["path"]: {"status": "not_reviewed", "note": None} for item in inventory["files"]},
        "protected_evaluation": [],
        "instructions": "Read every relevant file and dependency/data artifact; reconstruct the actual experiment. "
                        "Declare original held-out pair files with path, format, role, id_field, text_fields and optional family_fields. "
                        "Do not treat this automatically populated template as a completed scientific audit.",
    }
    write_json(output, review)
    return review
