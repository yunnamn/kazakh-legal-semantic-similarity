"""Document-family/component splits with external evaluation guards and immutable locks."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path
from typing import Iterator

from .config import SPLITS
from .errors import CorpusError
from .experiment import evaluation_units, verify_experiment
from .integrity import verify_artifacts
from .io import canonical, digest, file_sha, iter_jsonl, read_json, write_json
from .normalize import words
from .overlap import SimilarityIndex, SpanIndex, UnionFind
from .process import code_fingerprint


def hash_split(component_id: str, seed: str, weights: dict) -> str:
    # Integer arithmetic and named ordered splits; no Python hash() or RNG state.
    bucket = int(digest([seed, component_id]), 16) % 10000
    cumulative = 0
    for split in SPLITS:
        cumulative += weights[split]
        if bucket < cumulative:
            return split
    raise CorpusError("Invalid split weights")


def eligible_runs(db: sqlite3.Connection) -> Iterator[dict]:
    """Runs of consecutive retained sentences. Excluded text cannot bridge windows."""
    last_doc = None
    last_block = None
    run: list[dict] = []

    def record() -> dict | None:
        if not run:
            return None
        return {"unit_id": "run:" + digest([r["sentence_id"] for r in run]),
                "family_id": run[0]["family_id"], "text": " ".join(r["text"] for r in run)}

    for payload, eligible in db.execute("SELECT payload, retained FROM corpus ORDER BY doc, block_index, sentence_index, id"):
        row = json.loads(payload)
        if row["document_id"] != last_doc or not eligible:
            if item := record():
                yield item
            run = []
        if eligible:
            run.append(row)
        last_doc, last_block = row["document_id"], row["block_index"]
    if item := record():
        yield item


def build_splits(processed: Path, output: Path, *, experiment_lock: Path | None = None,
                 repository_root: Path | None = None, prior_lock: Path | None = None) -> dict:
    pmanifest = verify_artifacts(processed)
    if pmanifest["stage"] != "processed":
        raise CorpusError("Splitting requires a processed snapshot")
    config = read_json(processed / "pipeline.config.json")
    experiment = None
    if experiment_lock:
        if repository_root is None:
            raise CorpusError("repository_root is required to verify the frozen evaluation")
        experiment = verify_experiment(repository_root, experiment_lock)
        if experiment["corpus_config_sha256"] != digest(config):
            raise CorpusError("Corpus configuration differs from the reviewed experiment policy")
    if output.exists():
        raise CorpusError("Split output exists; never overwrite a release")
    output.parent.mkdir(parents=True, exist_ok=True)
    previous = {}
    if prior_lock:
        prior = read_json(prior_lock)
        if digest({k: v for k, v in prior.items() if k != "lock_id"}) != prior.get("lock_id"):
            raise CorpusError("Previous split lock is corrupt")
        if prior["seed"] != config["split"]["seed"] or prior["weights"] != config["split"]["weights"]:
            raise CorpusError("Prior split seed/weights differ; use an explicitly versioned new experiment")
        previous = {item["family_id"]: item["split"] for item in prior["assignments"]}
    dedup = config["dedup"]
    with tempfile.TemporaryDirectory(prefix=".splitting-", dir=output.parent) as tmp:
        staging = Path(tmp) / "release"
        (staging / "splits").mkdir(parents=True)
        db = sqlite3.connect(Path(tmp) / "joins.sqlite")
        db.executescript("""
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            CREATE TABLE corpus (id TEXT PRIMARY KEY, family TEXT, doc TEXT, block_index INTEGER,
                sentence_index INTEGER, guard TEXT, nwords INTEGER, base_eligible INTEGER,
                retained INTEGER, removal TEXT, payload TEXT);
            CREATE INDEX corpus_guard ON corpus(guard);
            CREATE INDEX corpus_family ON corpus(family);
        """)
        try:
            families = set()
            for doc in iter_jsonl(processed / "documents.jsonl"):
                families.add(doc["family_id"])
            uf = UnionFind(families)
            for row in iter_jsonl(processed / "sentences.jsonl"):
                db.execute("INSERT INTO corpus VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                    row["sentence_id"], row["family_id"], row["document_id"], row["block_index"],
                    row["sentence_index"], row["guard_sha256"], len(words(row["text"])),
                    int(row["eligible"]), int(row["eligible"]), None, canonical(row).decode()))
            edges = (staging / "leakage_edges.jsonl").open("xb")
            edge_counts: Counter = Counter()

            def connect(node: str, uid: str, matches: list[dict]) -> None:
                for match in matches:
                    other = match["other_node"]
                    if node == other:
                        continue
                    uf.union(node, other)
                    edge = {"node": node, "unit_id": uid, **match}
                    edges.write(canonical(edge) + b"\n")
                    edge_counts[match["reason"]] += 1

            exact_shared = list(db.execute("SELECT guard,COUNT(DISTINCT family),MIN(nwords) FROM corpus WHERE retained=1 GROUP BY guard HAVING COUNT(DISTINCT family)>1"))
            common_hashes = 0
            for guard, family_count, word_count in exact_shared:
                if word_count < dedup["min_informative_shared_words"] or family_count > dedup["max_shared_families"]:
                    reason = "shared_low_information_text" if word_count < dedup["min_informative_shared_words"] else "ubiquitous_exact_legal_text"
                    db.execute("UPDATE corpus SET retained=0,removal=? WHERE guard=? AND retained=1", (reason, guard))
                    common_hashes += 1
                # Informative exact overlaps are joined by SimilarityIndex below.
            index = SimilarityIndex(db, threshold=dedup["near_jaccard"], width=dedup["shingle_words"],
                                    min_words=dedup["min_near_words"], max_candidates=dedup["max_candidates_per_unit"])
            spans = SpanIndex(db, width=dedup["overlap_words"], max_candidates=dedup["max_candidates_per_unit"])
            eval_nodes = set()
            identity_links = read_json(processed / "identity_links.json")
            if experiment:
                for unit in evaluation_units(repository_root, experiment):
                    node = unit["unit_id"]
                    uf.find(node)
                    eval_nodes.add(node)
                    for original_family in unit["family_ids"]:
                        family = identity_links.get(original_family, original_family)
                        if family in families:
                            connect(node, node, [{"other_node": family, "other_unit": None,
                                                 "reason": "explicit_evaluation_source_family"}])
                    connect(node, node, index.add(node, node, unit["text"], kind=unit["kind"]))
                    connect(node, node, spans.add(node, node, unit["text"]))
            for uid, family, payload, retained in db.execute("SELECT id,family,payload,retained FROM corpus WHERE base_eligible=1 ORDER BY id"):
                row = json.loads(payload)
                if retained:
                    connect(family, uid, index.add(uid, family, row["text"]))
                elif experiment:
                    # Even excluded common sentences can establish a held-out law identity.
                    connect(family, uid, index.exact(row["text"], node=family, evaluation_only=True))
            for run in eligible_runs(db):
                connect(run["family_id"], run["unit_id"], spans.add(run["unit_id"], run["family_id"], run["text"]))
            edges.close()
            assignments = {}
            components = []
            active_families = {r[0] for r in db.execute("SELECT DISTINCT family FROM corpus WHERE retained=1")}
            for nodes in uf.components():
                real = sorted(set(nodes) & families)
                if not real:
                    continue
                component_id = digest(nodes)
                old_splits = {previous[n] for n in real if n in previous}
                reason = None
                if set(nodes) & eval_nodes:
                    role, reason = "quarantine", "external_semantic_evaluation_overlap"
                elif "quarantine" in old_splits:
                    role, reason = "quarantine", "previously_quarantined_family"
                elif len(old_splits) > 1:
                    role, reason = "quarantine", "prior_split_conflict_after_component_merge"
                elif old_splits:
                    role = next(iter(old_splits))
                else:
                    role = hash_split(component_id, config["split"]["seed"], config["split"]["weights"])
                for family in real:
                    assignments[family] = {"family_id": family, "component_id": component_id,
                                           "split": role, "quarantine_reason": reason}
                components.append({"component_id": component_id, "families": real, "split": role,
                                   "active_family_count": len(set(real) & active_families),
                                   "quarantine_reason": reason,
                                   "evaluation_node_count": len(set(nodes) & eval_nodes)})
            split_lock = {"schema_version": 1, "processed_build_id": pmanifest["build_id"],
                          "experiment_id": experiment["experiment_id"] if experiment else None,
                          "seed": config["split"]["seed"], "weights": config["split"]["weights"],
                          "prior_lock_id": read_json(prior_lock)["lock_id"] if prior_lock else None,
                          "assignments": [assignments[f] for f in sorted(assignments)],
                          "components": sorted(components, key=lambda c: c["component_id"])}
            split_lock["lock_id"] = digest(split_lock)
            write_json(staging / "split.lock.json", split_lock)
            outputs = {name: (staging / "splits" / (name + ".jsonl")).open("xb") for name in SPLITS}
            excluded = (staging / "excluded.jsonl").open("xb")
            membership = (staging / "memberships.jsonl").open("xb")
            counts: Counter = Counter()
            reason_counts: Counter = Counter()
            words_by_split: Counter = Counter()
            documents_by_split = {name: set() for name in (*SPLITS, "quarantine")}
            split_families = {name: set() for name in SPLITS}
            for uid, family, payload, retained, removal in db.execute("SELECT id,family,payload,retained,removal FROM corpus ORDER BY id"):
                row = json.loads(payload)
                a = assignments[family]
                reasons = list(row["quarantine_reasons"])
                if removal:
                    reasons.append(removal)
                if a["quarantine_reason"]:
                    reasons.append(a["quarantine_reason"])
                role = a["split"] if retained and not reasons else "quarantine"
                record = {**row, "split": role, "component_id": a["component_id"],
                          "quarantine_reasons": sorted(set(reasons))}
                membership.write(canonical({"sentence_id": uid, "document_id": row["document_id"],
                                             "family_id": family, "component_id": a["component_id"],
                                             "split": role, "reasons": record["quarantine_reasons"]}) + b"\n")
                counts[role] += 1
                words_by_split[role] += len(words(row["text"]))
                documents_by_split[role].add(row["document_id"])
                if role in outputs:
                    outputs[role].write(canonical(record) + b"\n")
                    split_families[role].add(family)
                else:
                    excluded.write(canonical(record) + b"\n")
                    reason_counts.update(reasons)
            for handle in list(outputs.values()) + [excluded, membership]:
                handle.close()
            retained_families = set().union(*split_families.values())
            largest = max((len(set(c["families"]) & retained_families) for c in components if c["split"] in SPLITS), default=0)
            fraction = largest / len(retained_families) if retained_families else 0.0
            blockers = []
            if config["release"]["require_all_splits_nonempty"] and any(counts[name] == 0 for name in SPLITS):
                blockers.append("one_or_more_required_splits_are_empty")
            if fraction > config["release"]["max_component_fraction"]:
                blockers.append("oversized_leakage_component_requires_sampling_policy_review")
            if not experiment:
                blockers.append("original_experiment_not_audited_or_frozen")
            if pmanifest["test_only"]:
                blockers.append("test_only_data_never_exportable_for_research")
            stats = {"sentences_by_split": {name: counts[name] for name in (*SPLITS, "quarantine")},
                     "families_by_split": {name: len(split_families[name]) for name in SPLITS},
                     "document_units_by_split": {name: len(documents_by_split[name]) for name in (*SPLITS, "quarantine")},
                     "regex_words_not_model_tokens_by_split": {name: words_by_split[name] for name in (*SPLITS, "quarantine")},
                     "exclusion_reasons": dict(sorted(reason_counts.items())),
                     "common_exact_fingerprints_excluded": common_hashes,
                     "leakage_edges_by_relation": dict(sorted(edge_counts.items())),
                     "exact_jaccard_candidate_comparisons": index.comparisons,
                     "components": len(components), "largest_retained_component_families": largest,
                     "largest_retained_component_fraction": round(fraction, 8),
                     "release_blockers_before_human_qa": blockers,
                     "coverage": "Observed source families, exact guard matches, thresholded sentence shingle Jaccard and contiguous windows; not semantic equivalence or base-model pretraining decontamination"}
            write_json(staging / "statistics.json", stats)
            write_json(staging / "pipeline.config.json", config)
            if experiment:
                write_json(staging / "experiment.lock.json", experiment)
            manifest = {"schema_version": 1, "stage": "derived_splits", "code_sha256": code_fingerprint(),
                        "processed_build_id": pmanifest["build_id"], "test_only": pmanifest["test_only"],
                        "experiment_id": experiment["experiment_id"] if experiment else None,
                        "files": {p.relative_to(staging).as_posix(): file_sha(p) for p in sorted(staging.rglob("*")) if p.is_file()}}
            manifest["build_id"] = digest(manifest)
            write_json(staging / "manifest.json", manifest)
            os.replace(staging, output)
            return manifest
        finally:
            db.close()
