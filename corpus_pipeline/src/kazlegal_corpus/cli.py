from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .acquire import acquire_adilet, acquire_hub, inspect_hub
from .audit import audit_repository
from .config import load_config
from .discover import catalog_manifest
from .errors import CorpusError
from .experiment import make_review_template, freeze_experiment
from .export import export_training_view
from .integrity import verify_artifacts
from .io import digest, iter_jsonl, read_json, write_json
from .process import build_processed
from .qa import make_qa_template, validate_qa
from .raw import RawStore
from .split import build_splits
from .validate import validate_corpus


def _path(parser, name: str, *, required: bool = True, **kwargs):
    parser.add_argument(name, type=Path, required=required, **kwargs)


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description="Authentic-source Kazakh legislation corpus pipeline; no generated legal text")
    sub = top.add_subparsers(dest="command", required=True)
    p = sub.add_parser("import-raw", help="Register a lawful manual download with an explicit acquisition sidecar")
    for name in ("--raw-dir", "--file", "--sidecar"):
        _path(p, name)
    _path(p, "--review", required=False)
    p = sub.add_parser("freeze-raw", help="Freeze content receipts and their transitive evidence dependencies")
    _path(p, "--raw-dir"); _path(p, "--output")
    p.add_argument("--receipt", action="append", default=None)
    p = sub.add_parser("inspect-hub", help="Resolve a candidate dataset revision and list files, without approving reuse")
    p.add_argument("--repo", required=True)
    p = sub.add_parser("acquire-hub", help="Download exact files at a full pinned commit, plus the dataset card")
    for name in ("--raw-dir", "--review", "--output"):
        _path(p, name)
    p.add_argument("--repo", required=True); p.add_argument("--revision", required=True)
    p.add_argument("--file", action="append", required=True)
    p.add_argument("--format", choices=("csv", "jsonl", "jsonl.gz", "json", "parquet"), required=True)
    _path(p, "--expected-hashes", required=False)
    p.add_argument("--local-files-only", action="store_true")
    p = sub.add_parser("discover-catalog", help="Derive a Kazakh Adilet acquisition manifest from reusable metadata")
    for name in ("--raw-dir", "--output"):
        _path(p, name)
    p.add_argument("--receipt", required=True); p.add_argument("--limit", type=int, required=True)
    p.add_argument("--seed", default="kazlegal-discovery-v1")
    p.add_argument("--status", choices=("all", "not_marked_repealed"), default="all")
    p = sub.add_parser("acquire-adilet", help="Rate-limited, robots-aware retrieval; stops on access restrictions")
    for name in ("--raw-dir", "--manifest", "--review", "--report"):
        _path(p, name)
    p.add_argument("--contact", required=True); p.add_argument("--selector")
    p = sub.add_parser("process", help="Create an immutable normalized snapshot, preserving all document occurrences")
    for name in ("--raw-dir", "--raw-lock", "--config", "--output"):
        _path(p, name)
    _path(p, "--identity-links", required=False); _path(p, "--language-reviews", required=False)
    p.add_argument("--quarantine-malformed", action="store_true", help="Record malformed JSONL rows; never repair them")
    p.add_argument("--test-mode", action="store_true", help="Fixture-only artifacts, permanently ineligible for research export")
    p = sub.add_parser("split", help="Assign document-family leakage components to the four required roles")
    _path(p, "--processed"); _path(p, "--output")
    _path(p, "--experiment-lock", required=False); _path(p, "--repo-root", required=False)
    _path(p, "--prior-lock", required=False)
    p = sub.add_parser("audit-repo", help="Read every tracked local file and emit review candidates; does not claim a scientific audit")
    _path(p, "--repo-root"); _path(p, "--output")
    p = sub.add_parser("experiment-review-template", help="Create an unapproved review form from a local inventory")
    for name in ("--inventory", "--config", "--output"):
        _path(p, name)
    p = sub.add_parser("freeze-experiment", help="Bind a human-reviewed reconstruction to original evaluation files")
    for name in ("--repo-root", "--inventory", "--review", "--config", "--output"):
        _path(p, name)
    p = sub.add_parser("config-hash", help="Print the exact corpus policy hash for an experiment review")
    _path(p, "--config")
    p = sub.add_parser("validate", help="Check raw integrity, provenance, offsets, disposition and independent leakage scans")
    for name in ("--raw-dir", "--processed", "--derived", "--report"):
        _path(p, name)
    _path(p, "--repo-root", required=False); _path(p, "--qa-review", required=False)
    p.add_argument("--skip-overlap", action="store_true", help="Structural diagnostics only; not research-export validation")
    p.add_argument("--require-ready", action="store_true")
    p = sub.add_parser("qa-template", help="Select deterministic source documents; all human responses remain blank")
    for name in ("--processed", "--derived", "--output"):
        _path(p, name)
    p.add_argument("--per-source", type=int)
    p = sub.add_parser("export", help="Create explicit training views only after the audit, validation and human QA gates")
    for name in ("--raw-dir", "--processed", "--derived", "--repo-root", "--qa-review", "--output"):
        _path(p, name)
    p.add_argument("--format", choices=("jsonl", "text"), default="jsonl")
    p = sub.add_parser("statistics", help="Print measured statistics for an existing immutable build")
    _path(p, "--directory")
    p = sub.add_parser("show-document", help="Display the full retained document and all structural provenance for human QA")
    _path(p, "--processed"); p.add_argument("--document-id", required=True)
    return top


def run(args) -> dict:
    command = args.command
    if command == "import-raw":
        metadata = read_json(args.sidecar)
        if args.review:
            metadata["source_review"] = read_json(args.review)
        receipt = RawStore(args.raw_dir).register(args.file, metadata)
        return {"receipt_id": receipt["receipt_id"], "sha256": receipt["sha256"], "role": receipt["role"]}
    if command == "freeze-raw":
        return RawStore(args.raw_dir).freeze(args.output, args.receipt)
    if command == "inspect-hub":
        return inspect_hub(args.repo)
    if command == "acquire-hub":
        return acquire_hub(RawStore(args.raw_dir), repo_id=args.repo, revision=args.revision, filenames=args.file,
                           format_name=args.format, review=read_json(args.review), output=args.output,
                           expected_hashes=read_json(args.expected_hashes) if args.expected_hashes else None,
                           local_files_only=args.local_files_only)
    if command == "discover-catalog":
        return catalog_manifest(RawStore(args.raw_dir), args.receipt, args.output, limit=args.limit, seed=args.seed, status=args.status)
    if command == "acquire-adilet":
        return acquire_adilet(args.manifest, RawStore(args.raw_dir), read_json(args.review), contact=args.contact,
                              report_path=args.report, selector=args.selector)
    if command == "process":
        return build_processed(RawStore(args.raw_dir), args.raw_lock, args.config, args.output,
                               identity_links=args.identity_links, language_reviews=args.language_reviews,
                               quarantine_malformed=args.quarantine_malformed, test_mode=args.test_mode)
    if command == "split":
        return build_splits(args.processed, args.output, experiment_lock=args.experiment_lock,
                            repository_root=args.repo_root, prior_lock=args.prior_lock)
    if command == "audit-repo":
        report = audit_repository(args.repo_root, args.output)
        return {"repository_commit": report["repository_commit"], "tracked_files": report["tracked_files"],
                "scientific_audit_complete": False, "review_directory": str(args.output)}
    if command == "experiment-review-template":
        return make_review_template(args.inventory, args.config, args.output)
    if command == "freeze-experiment":
        return freeze_experiment(args.repo_root, args.inventory, args.review, args.config, args.output)
    if command == "config-hash":
        return {"corpus_config_sha256": digest(load_config(args.config))}
    if command == "validate":
        report = validate_corpus(RawStore(args.raw_dir), args.processed, args.derived,
                                 repository_root=args.repo_root, recheck_overlap=not args.skip_overlap)
        if args.require_ready:
            if report["release_blockers_before_human_qa"]:
                raise CorpusError("Research release blocked: " + "; ".join(report["release_blockers_before_human_qa"]))
            if not args.qa_review:
                raise CorpusError("--require-ready also requires --qa-review")
            config = read_json(args.derived / "pipeline.config.json")
            report["human_qa"] = validate_qa(args.derived, args.qa_review,
                                            count_per_source=config["release"]["minimum_reviewed_documents_per_source"])
            report["training_view_ready"] = True
        write_json(args.report, report)
        return report
    if command == "qa-template":
        config = read_json(args.derived / "pipeline.config.json")
        count = args.per_source or config["release"]["minimum_reviewed_documents_per_source"]
        if count <= 0:
            raise CorpusError("QA sample size must be positive")
        return {"blank_review_samples": make_qa_template(args.processed, args.derived, args.output, count_per_source=count)}
    if command == "export":
        return export_training_view(RawStore(args.raw_dir), args.processed, args.derived, args.output,
                                     repository_root=args.repo_root, qa_review=args.qa_review, format_name=args.format)
    if command == "statistics":
        verify_artifacts(args.directory)
        return read_json(args.directory / "statistics.json")
    if command == "show-document":
        verify_artifacts(args.processed)
        for doc in iter_jsonl(args.processed / "documents.jsonl"):
            if doc["document_id"] == args.document_id:
                doc["blocks"] = [b for b in iter_jsonl(args.processed / "blocks.jsonl") if b["document_id"] == args.document_id]
                return doc
        raise CorpusError("Document ID is not in this processed snapshot")
    raise CorpusError("Unknown command")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = run(args)
    except (CorpusError, OSError, KeyError, ValueError) as exc:
        if getattr(args, "report", None) and not args.report.exists():
            write_json(args.report, {"status": "failed", "error": str(exc)})
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
