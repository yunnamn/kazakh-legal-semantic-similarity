"""Independent structural and split-overlap checks. Exit failures must block training."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path

from .config import SPLITS
from .errors import CorpusError
from .experiment import evaluation_units, verify_experiment
from .integrity import verify_artifacts
from .io import digest, iter_jsonl, read_json, text_sha
from .normalize import guard_text, normalize
from .overlap import SimilarityIndex, SpanIndex
from .process import code_fingerprint
from .raw import RawStore, check_review
from .split import eligible_runs


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise CorpusError(message)


def validate_corpus(store: RawStore, processed: Path, derived: Path, *,
                    repository_root: Path | None = None, recheck_overlap: bool = True) -> dict:
    pm = verify_artifacts(processed)
    dm = verify_artifacts(derived)
    _assert(pm["stage"] == "processed" and dm["stage"] == "derived_splits", "Incorrect artifact stages")
    _assert(dm["processed_build_id"] == pm["build_id"], "Derived corpus refers to a different processed snapshot")
    _assert(pm["code_sha256"] == dm["code_sha256"] == code_fingerprint(),
            "Pipeline source changed after the build; use the recorded code version or rebuild")
    config = read_json(processed / "pipeline.config.json")
    _assert(config == read_json(derived / "pipeline.config.json"), "Processed and derived policies differ")
    receipts = store.load_lock(processed / "raw.lock.json", test_mode=pm["test_only"])
    by_receipt = {r["receipt_id"]: r for r in receipts}
    for receipt in receipts:
        if receipt["role"] == "content":
            check_review(receipt.get("source_review", {}), receipt["source"], test_only=receipt["test_only"])
    split_lock = read_json(derived / "split.lock.json")
    _assert(digest({k: v for k, v in split_lock.items() if k != "lock_id"}) == split_lock["lock_id"], "Split lock integrity failed")
    assignments = {a["family_id"]: a for a in split_lock["assignments"]}
    _assert(len(assignments) == len(split_lock["assignments"]), "Duplicate family assignments")
    _assert(split_lock["processed_build_id"] == pm["build_id"], "Split lock refers to another processed corpus")
    _assert(split_lock["experiment_id"] == dm["experiment_id"], "Split lock experiment mismatch")
    _assert(split_lock["weights"] == config["split"]["weights"] and split_lock["seed"] == config["split"]["seed"], "Split policy mismatch")
    component_roles = {}
    for a in assignments.values():
        _assert(a["split"] in (*SPLITS, "quarantine"), "Invalid family split")
        _assert(component_roles.setdefault(a["component_id"], a["split"]) == a["split"], "A leakage component crosses splits")
    experiment = None
    if dm["experiment_id"]:
        _assert(repository_root is not None, "Repository is needed to verify evaluation integrity")
        experiment = verify_experiment(repository_root, derived / "experiment.lock.json")
        _assert(experiment["experiment_id"] == dm["experiment_id"], "Experiment identity mismatch")
        _assert(experiment["corpus_config_sha256"] == digest(config), "Unreviewed corpus configuration")
    with tempfile.TemporaryDirectory(prefix="kazlegal-validation-") as tmp:
        db = sqlite3.connect(Path(tmp) / "validation.sqlite")
        db.executescript("""
            CREATE TABLE docs (id TEXT PRIMARY KEY,payload TEXT);
            CREATE TABLE blocks (id TEXT PRIMARY KEY,doc TEXT,idx INTEGER,payload TEXT);
            CREATE TABLE source_sentences (id TEXT PRIMARY KEY,payload TEXT);
            CREATE TABLE membership (id TEXT PRIMARY KEY,payload TEXT,seen INTEGER DEFAULT 0);
            CREATE TABLE corpus (id TEXT PRIMARY KEY,family TEXT,doc TEXT,block_index INTEGER,
                                 sentence_index INTEGER,payload TEXT,retained INTEGER);
        """)
        try:
            n_docs = n_blocks = n_sentences = 0
            for doc in iter_jsonl(processed / "documents.jsonl"):
                _assert(doc["text_sha256"] == text_sha(doc["text"]), "Document content checksum failed")
                _assert(bool(doc.get("provenance")), "Document lacks provenance")
                _assert(doc["family_id"] in assignments, "Document family missing from split lock")
                for p in doc["provenance"]:
                    _assert(p["receipt_id"] in by_receipt, "Document references an acquisition outside the raw lock")
                    r = by_receipt[p["receipt_id"]]
                    _assert(r["role"] == "content", "Corpus text came from evidence rather than a content artifact")
                    _assert(p["raw_sha256"] == r["sha256"] and p["acquisition_url"] == r["source_url"], "Provenance differs from immutable receipt")
                    _assert(p["retrieved_at"] == r["retrieved_at"], "Retrieval date was fabricated or modified")
                    _assert(p["source_review"] == r.get("source_review"), "Source license/review was modified")
                db.execute("INSERT INTO docs VALUES (?,?)", (doc["document_id"], json.dumps(doc)))
                n_docs += 1
            for b in iter_jsonl(processed / "blocks.jsonl"):
                original = db.execute("SELECT payload FROM docs WHERE id=?", (b["document_id"],)).fetchone()
                _assert(original is not None, "Orphan text block")
                doc = json.loads(original[0])
                _assert(normalize(b["text"])[0] == b["text"], "Unnormalized block text")
                _assert(doc["text"][b["document_start"]:b["document_end"]] == b["text"], "Block offsets do not reconstruct the source document")
                _assert(b["block_id"] == digest([b["document_id"], b["block_index"], b["text"]]), "Block ID changed")
                _assert(bool(b["source_locators"]), "Block has no source locator")
                db.execute("INSERT INTO blocks VALUES (?,?,?,?)", (b["block_id"], b["document_id"], b["block_index"], json.dumps(b)))
                n_blocks += 1
            for doc_id, payload in db.execute("SELECT id,payload FROM docs ORDER BY id"):
                doc = json.loads(payload)
                blocks = [json.loads(x[0]) for x in db.execute("SELECT payload FROM blocks WHERE doc=? ORDER BY idx", (doc_id,))]
                _assert("\n\n".join(b["text"] for b in blocks) == doc["text"], "Block reconstruction lost or duplicated text")
                layout = [{k: b.get(k) for k in ("text", "kind", "article", "article_occurrence", "section_path")} for b in blocks]
                expected = digest({"family_id": doc["family_id"], "language": doc["language"], "unit_kind": doc["unit_kind"],
                                   "unit": doc["upstream_unit_id"], "source_version": doc["source_version"], "layout": layout})
                _assert(expected == doc_id, "Document identity/structure changed")
            for row in iter_jsonl(processed / "sentences.jsonl"):
                block_row = db.execute("SELECT payload FROM blocks WHERE id=?", (row["block_id"],)).fetchone()
                _assert(block_row is not None, "Orphan sentence")
                block = json.loads(block_row[0])
                doc = json.loads(db.execute("SELECT payload FROM docs WHERE id=?", (row["document_id"],)).fetchone()[0])
                _assert(block["document_id"] == row["document_id"], "Sentence references an unrelated document")
                _assert(block["text"][row["block_start"]:row["block_end"]] == row["text"], "Sentence block offsets mismatch")
                _assert(doc["text"][row["document_start"]:row["document_end"]] == row["text"], "Sentence document offsets mismatch")
                _assert(row["sentence_id"] == digest([row["block_id"], row["block_start"], row["block_end"], row["text"]]), "Sentence ID mismatch")
                _assert(row["text_sha256"] == text_sha(row["text"]) and row["guard_sha256"] == text_sha(guard_text(row["text"])), "Sentence fingerprint mismatch")
                for key in ("family_id", "source_url", "source_document_id", "title", "language", "upstream_section_title", "provenance"):
                    _assert(row[key] == doc[key], f"Sentence {key} differs from parent provenance")
                for key in ("article", "article_occurrence", "section_path"):
                    _assert(row[key] == block[key], f"Sentence {key} lost structural provenance")
                _assert(bool(row["eligible"]) == (not row["quarantine_reasons"]), "Eligibility and exclusion reasons disagree")
                if "TEST_ONLY" in row["text"]:
                    _assert(pm["test_only"] and row["test_only"], "Fixture text contaminated production output")
                db.execute("INSERT INTO source_sentences VALUES (?,?)", (row["sentence_id"], json.dumps(row)))
                n_sentences += 1
            for row in iter_jsonl(derived / "memberships.jsonl"):
                _assert(db.execute("SELECT 1 FROM source_sentences WHERE id=?", (row["sentence_id"],)).fetchone() is not None, "Membership refers to nonexistent sentence")
                _assert(row["split"] in (*SPLITS, "quarantine"), "Invalid split role")
                a = assignments[row["family_id"]]
                _assert(a["component_id"] == row["component_id"], "Component identity mismatch")
                if row["split"] != "quarantine":
                    _assert(a["split"] == row["split"], "Family assigned to multiple splits")
                db.execute("INSERT INTO membership(id,payload) VALUES (?,?)", (row["sentence_id"], json.dumps(row)))
            _assert(db.execute("SELECT COUNT(*) FROM membership").fetchone()[0] == n_sentences, "Every processed occurrence must have exactly one disposition")
            counts: Counter = Counter()
            family_roles = {}
            fingerprints = {}
            for role in (*SPLITS, "quarantine"):
                path = derived / ("excluded.jsonl" if role == "quarantine" else f"splits/{role}.jsonl")
                for row in iter_jsonl(path):
                    member = db.execute("SELECT payload,seen FROM membership WHERE id=?", (row["sentence_id"],)).fetchone()
                    _assert(member is not None and member[1] == 0, "Repeated or unknown derived occurrence")
                    member_payload = json.loads(member[0])
                    _assert(row["split"] == role == member_payload["split"], "Derived role differs from membership")
                    source = json.loads(db.execute("SELECT payload FROM source_sentences WHERE id=?", (row["sentence_id"],)).fetchone()[0])
                    for key, value in source.items():
                        if key != "quarantine_reasons":
                            _assert(row.get(key) == value, f"Derived corpus changed original sentence field {key}")
                    _assert(set(source["quarantine_reasons"]).issubset(row["quarantine_reasons"]), "Derived split removed a quarantine reason")
                    db.execute("UPDATE membership SET seen=1 WHERE id=?", (row["sentence_id"],))
                    counts[role] += 1
                    if role in SPLITS:
                        _assert(row["eligible"] and not row["quarantine_reasons"], "An ineligible sentence entered a research split")
                        family = row["family_id"]
                        _assert(family_roles.setdefault(family, role) == role, "Law family crosses splits")
                        _assert(fingerprints.setdefault(row["guard_sha256"], role) == role, "Exact normalized text crosses splits")
                    db.execute("INSERT INTO corpus VALUES (?,?,?,?,?,?,?)", (row["sentence_id"], row["family_id"], row["document_id"],
                               row["block_index"], row["sentence_index"], json.dumps(row), int(role in SPLITS)))
            _assert(db.execute("SELECT COUNT(*) FROM membership WHERE seen=0").fetchone()[0] == 0, "Unaccounted-for sentence disposition")
            comparisons = 0
            if recheck_overlap:
                d = config["dedup"]
                near = SimilarityIndex(db, threshold=d["near_jaccard"], width=d["shingle_words"],
                                       min_words=d["min_near_words"], max_candidates=d["max_candidates_per_unit"])
                spans = SpanIndex(db, width=d["overlap_words"], max_candidates=d["max_candidates_per_unit"])
                eval_nodes = set()
                identities = read_json(processed / "identity_links.json")
                if experiment:
                    for unit in evaluation_units(repository_root, experiment):
                        node = unit["unit_id"]
                        eval_nodes.add(node)
                        for family in unit["family_ids"]:
                            _assert(identities.get(family, family) not in family_roles, "An explicit evaluation source family leaked into the corpus")
                        near.add(node, node, unit["text"], kind=unit["kind"])
                        spans.add(node, node, unit["text"])

                def check_matches(family: str, matches: list[dict]) -> None:
                    for match in matches:
                        other = match["other_node"]
                        _assert(other not in eval_nodes, f"Corpus overlaps protected semantic evaluation: {match['reason']}")
                        _assert(family_roles[family] == family_roles[other], f"Cross-split leakage under {match['reason']}")

                for uid, family, payload in db.execute("SELECT id,family,payload FROM corpus WHERE retained=1 ORDER BY id"):
                    row = json.loads(payload)
                    check_matches(family, near.add(uid, family, row["text"]))
                for run in eligible_runs(db):
                    check_matches(run["family_id"], spans.add(run["unit_id"], run["family_id"], run["text"]))
                comparisons = near.comparisons
            statistics = read_json(derived / "statistics.json")
            measured_counts = {s: counts[s] for s in (*SPLITS, "quarantine")}
            _assert(statistics["sentences_by_split"] == measured_counts, "Reported sentence counts differ from the data")
            measured_families = {s: sum(role == s for role in family_roles.values()) for s in SPLITS}
            _assert(statistics["families_by_split"] == measured_families, "Reported family counts differ from the data")
            component_sizes = Counter(assignments[f]["component_id"] for f in family_roles)
            largest = max(component_sizes.values(), default=0)
            fraction = largest / len(family_roles) if family_roles else 0.0
            _assert(statistics["largest_retained_component_families"] == largest, "Component statistics mismatch")
            blockers = []
            if config["release"]["require_all_splits_nonempty"] and any(counts[s] == 0 for s in SPLITS):
                blockers.append("one_or_more_required_splits_are_empty")
            if fraction > config["release"]["max_component_fraction"]:
                blockers.append("oversized_leakage_component_requires_sampling_policy_review")
            if experiment is None:
                blockers.append("original_experiment_not_audited_or_frozen")
            if pm["test_only"]:
                blockers.append("test_only_data_never_exportable_for_research")
            _assert(statistics["release_blockers_before_human_qa"] == blockers, "Release blockers disagree with independently measured corpus state")
            if not recheck_overlap:
                blockers.append("independent_overlap_validation_not_run")
            return {"schema_version": 1, "processed_build_id": pm["build_id"], "derived_build_id": dm["build_id"],
                    "structural_checks": "passed", "independent_overlap_checks": "passed" if recheck_overlap else "not_run",
                    "documents": n_docs, "blocks": n_blocks, "processed_sentences": n_sentences,
                    "sentences_by_split": {s: counts[s] for s in (*SPLITS, "quarantine")},
                    "jaccard_candidate_comparisons": comparisons,
                    "release_blockers_before_human_qa": blockers,
                    "original_experiment_verified": experiment is not None,
                    "publication_ready": False,
                    "note": "Human source/boundary QA and source-specific redistribution review are separate requirements"}
        finally:
            db.close()
