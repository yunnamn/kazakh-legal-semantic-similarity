"""Export only after an audited experiment, independent validation and real human QA."""
from __future__ import annotations
import os
import tempfile
from pathlib import Path
from .config import SPLITS
from .errors import CorpusError
from .io import canonical, digest, file_sha, iter_jsonl, read_json, write_json
from .qa import validate_qa
from .raw import RawStore
from .validate import validate_corpus


def export_training_view(store: RawStore, processed: Path, derived: Path, output: Path, *,
                         repository_root: Path, qa_review: Path, format_name: str = "jsonl") -> dict:
    if format_name not in {"jsonl", "text"}:
        raise CorpusError("Export format must be jsonl or text")
    validation = validate_corpus(store, processed, derived, repository_root=repository_root, recheck_overlap=True)
    if validation["release_blockers_before_human_qa"]:
        raise CorpusError("Research export blocked: " + "; ".join(validation["release_blockers_before_human_qa"]))
    config = read_json(derived / "pipeline.config.json")
    qa = validate_qa(derived, qa_review, count_per_source=config["release"]["minimum_reviewed_documents_per_source"])
    if output.exists():
        raise CorpusError("Training export already exists; do not overwrite or silently replace an experiment input")
    output.parent.mkdir(parents=True, exist_ok=True)
    attributions = {}
    with tempfile.TemporaryDirectory(prefix=".export-", dir=output.parent) as temporary:
        staging = Path(temporary) / "view"
        staging.mkdir()
        for split in SPLITS:
            path = staging / (split + (".jsonl" if format_name == "jsonl" else ".txt"))
            lineage = staging / (split + ".provenance.jsonl")
            with path.open("xb") as dest, lineage.open("xb") as sidecar:
                for line_no, row in enumerate(iter_jsonl(derived / "splits" / (split + ".jsonl")), 1):
                    if row["test_only"] or "TEST_ONLY" in row["text"]:
                        raise CorpusError("Fixture data is never a research corpus")
                    if format_name == "jsonl":
                        dest.write(canonical(row) + b"\n")
                    else:
                        dest.write(row["text"].encode("utf-8") + b"\n")
                    sidecar.write(canonical({"export_line": line_no, **{k: v for k, v in row.items() if k != "text"}}) + b"\n")
                    for p in row["provenance"]:
                        review = p["source_review"]
                        attributions[digest(review)] = review
        write_json(staging / "attributions_and_rights.json", sorted(attributions.values(), key=digest))
        write_json(staging / "validation.json", {**validation, "human_qa": qa, "training_view_ready": True})
        manifest = {"schema_version": 1, "stage": "training_view_not_new_similarity_evaluation",
                    "derived_build_id": validation["derived_build_id"], "format": format_name,
                    "qa_review_sha256": file_sha(qa_review),
                    "experiment_id": read_json(derived / "experiment.lock.json")["experiment_id"],
                    "roles": {"train": "MLM adaptation only", "validation": "MLM checkpoint selection only",
                              "mlm_test": "final held-out MLM diagnostic, not checkpoint selection",
                              "annotation_pool": "existing human semantic-similarity annotation workflow only; never MLM input"},
                    "files": {p.name: file_sha(p) for p in sorted(staging.iterdir())}}
        manifest["build_id"] = digest(manifest)
        write_json(staging / "manifest.json", manifest)
        os.replace(staging, output)
        return manifest
