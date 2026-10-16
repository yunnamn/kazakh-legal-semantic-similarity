"""Build a normalized, provenance-rich snapshot without assigning experimental folds."""
from __future__ import annotations

import json
import os
import platform
import sqlite3
import tempfile
import unicodedata
from collections import Counter
from importlib.metadata import version
from pathlib import Path

from .adapters import candidates
from .config import load_config
from .errors import CorpusError
from .io import canonical, digest, file_sha, iter_jsonl, read_json, text_sha, timestamp, write_json, write_jsonl
from .normalize import guard_text, language_signals, sentence_spans, words
from .raw import RawStore, check_review


def code_fingerprint() -> str:
    root = Path(__file__).parent
    return digest({p.relative_to(root).as_posix(): file_sha(p) for p in sorted(root.glob("*.py"))})


def load_identity_links(path: Path | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if path is None:
        return mapping
    for row in iter_jsonl(path):
        for k in ("source_family_id", "canonical_family_id", "reviewer", "reviewed_at", "evidence"):
            if not isinstance(row.get(k), str) or not row[k].strip():
                raise CorpusError(f"Identity links require {k}; matching titles are not sufficient evidence")
        timestamp(row["reviewed_at"])
        source, target = row["source_family_id"], row["canonical_family_id"]
        if source in mapping and mapping[source] != target:
            raise CorpusError("Conflicting cross-source identity links")
        mapping[source] = target
    for source in mapping:
        seen = {source}
        target = mapping[source]
        while target in mapping:
            if target in seen:
                raise CorpusError("Cyclic identity links")
            seen.add(target)
            target = mapping[target]
        mapping[source] = target
    return mapping


def _reviews(path: Path | None) -> dict[str, dict]:
    result = {}
    if path is None:
        return result
    for row in iter_jsonl(path):
        key = row.get("sentence_id") or row.get("document_id")
        if not key or key in result or row.get("decision") not in {"accept_kazakh", "reject"}:
            raise CorpusError("Malformed/duplicate language review")
        if not row.get("reviewer") or not row.get("reason"):
            raise CorpusError("Language reviews require a reviewer and reason")
        timestamp(row["reviewed_at"])
        result[key] = row
    return result


def _summary_lengths(db: sqlite3.Connection, field: str) -> dict:
    if field not in {"chars", "words"}:
        raise CorpusError("Invalid length statistic")
    n, minimum, maximum, mean = db.execute(f"SELECT COUNT(*), MIN({field}), MAX({field}), AVG({field}) FROM sentences").fetchone()
    if not n:
        return {"count": 0}
    quantiles = {}
    for label, q in (("median", 0.50), ("p95", 0.95), ("p99", 0.99)):
        offset = round((n - 1) * q)
        quantiles[label] = db.execute(f"SELECT {field} FROM sentences ORDER BY {field} LIMIT 1 OFFSET ?", (offset,)).fetchone()[0]
    return {"count": n, "min": minimum, "max": maximum, "mean": round(mean, 4), **quantiles}


def build_processed(store: RawStore, raw_lock: Path, config_path: Path, output: Path, *,
                    identity_links: Path | None = None, language_reviews: Path | None = None,
                    quarantine_malformed: bool = False, test_mode: bool = False) -> dict:
    config = load_config(config_path)
    receipts = store.load_lock(raw_lock, test_mode=test_mode)
    identities = load_identity_links(identity_links)
    reviews = _reviews(language_reviews)
    used_reviews: set[str] = set()
    if output.exists():
        raise CorpusError("Processed release already exists; choose a new immutable output directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    errors: list[dict] = []
    harvested = 0
    source_counts: Counter = Counter()
    language_counts: Counter = Counter()
    missing: Counter = Counter()
    status_counts: Counter = Counter()
    fidelity_counts: Counter = Counter()
    unit_counts: Counter = Counter()
    metadata_coverage = {key: Counter() for key in ("adoption_year", "act_form", "region", "is_repealed")}
    sentence_kinds: Counter = Counter()
    sentence_missing: Counter = Counter()
    total_words = eligible_sentences = 0
    with tempfile.TemporaryDirectory(prefix=".processing-", dir=output.parent) as temporary:
        staging = Path(temporary) / "release"
        staging.mkdir()
        db_path = Path(temporary) / "processing.sqlite"
        db = sqlite3.connect(db_path)
        db.execute("CREATE TABLE documents (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("CREATE TABLE sentences (id TEXT PRIMARY KEY, payload TEXT NOT NULL, chars INTEGER, words INTEGER)")
        try:
            for receipt in sorted(receipts, key=lambda r: r["receipt_id"]):
                if receipt["role"] != "content" or receipt.get("adapter", "").startswith("catalog_"):
                    continue
                check_review(receipt.get("source_review", {}), receipt["source"], test_only=receipt["test_only"])
                local_errors: list[dict] | None = [] if quarantine_malformed else None
                try:
                    for candidate in candidates(store, receipt, quarantine=local_errors):
                        harvested += 1
                        if not candidate["blocks"]:
                            raise CorpusError("Empty legal text after normalization")
                        original_family = candidate["family_id"]
                        candidate["family_id"] = identities.get(original_family, original_family)
                        candidate["source_family_ids"] = [original_family]
                        content = "\n\n".join(b["text"] for b in candidate["blocks"])
                        if "TEST_ONLY" in content and not (test_mode and candidate["test_only"]):
                            raise CorpusError("TEST_ONLY text cannot enter a production corpus")
                        candidate["text"] = content
                        candidate["text_sha256"] = text_sha(content)
                        layout = [{k: b.get(k) for k in ("text", "kind", "article", "article_occurrence", "section_path")}
                                  for b in candidate["blocks"]]
                        doc_id = digest({"family_id": candidate["family_id"], "language": candidate["language"],
                                         "unit_kind": candidate["unit_kind"], "unit": candidate["upstream_unit_id"],
                                         "source_version": candidate["source_version"], "layout": layout})
                        candidate["document_id"] = doc_id
                        candidate["primary_receipt_id"] = receipt["receipt_id"]
                        candidate["source_descriptions"] = [{k: candidate.get(k) for k in (
                            "source_document_id", "source_url", "title", "source_version", "source_fidelity", "upstream_metadata", "extraction") } | {"receipt_id": receipt["receipt_id"]}]
                        for block in candidate["blocks"]:
                            block["source_locators"] = [{"receipt_id": receipt["receipt_id"],
                                                         "record_locator": candidate["provenance"][0]["record_locator"],
                                                         **block["source_locator"]}]
                            del block["source_locator"]
                        old = db.execute("SELECT payload FROM documents WHERE id=?", (doc_id,)).fetchone()
                        if old:
                            previous = json.loads(old[0])
                            previous["provenance"] = sorted({digest(p): p for p in previous["provenance"] + candidate["provenance"]}.values(), key=digest)
                            previous["source_descriptions"] = sorted({digest(p): p for p in previous["source_descriptions"] + candidate["source_descriptions"]}.values(), key=digest)
                            previous["source_family_ids"] = sorted(set(previous["source_family_ids"] + candidate["source_family_ids"]))
                            previous["test_only"] = previous["test_only"] or candidate["test_only"]
                            # Prefer official snapshot metadata, then use a stable lexical order.
                            best = sorted(previous["source_descriptions"], key=lambda d: (d["source_fidelity"] != "official_publisher_snapshot", digest(d)))[0]
                            previous["primary_receipt_id"] = best["receipt_id"]
                            for key in ("source_document_id", "source_url", "title", "source_fidelity", "upstream_metadata", "extraction"):
                                previous[key] = best[key]
                            for left, right in zip(previous["blocks"], candidate["blocks"], strict=True):
                                left["source_locators"] = sorted({digest(p): p for p in left["source_locators"] + right["source_locators"]}.values(), key=digest)
                            candidate = previous
                        db.execute("INSERT OR REPLACE INTO documents VALUES (?,?)", (doc_id, canonical(candidate).decode()))
                except (CorpusError, UnicodeError, ValueError) as exc:
                    if not quarantine_malformed:
                        raise
                    errors.append({"receipt_id": receipt["receipt_id"], "reason": "unparseable_source",
                                   "detail": str(exc)[:500]})
                if local_errors:
                    errors.extend({"receipt_id": receipt["receipt_id"], **e} for e in local_errors)
                db.commit()
            document_rows = db.execute("SELECT id, payload FROM documents ORDER BY id")
            block_output = (staging / "blocks.jsonl").open("xb")
            doc_output = (staging / "documents.jsonl").open("xb")
            unique_docs = 0
            for doc_id, payload in document_rows:
                doc = json.loads(payload)
                unique_docs += 1
                signal = language_signals(doc["text"], declared=doc["language"])
                doc["language_signals"] = signal
                doc["upstream_section_title"] = (doc.get("upstream_metadata") or {}).get("section_title")
                doc_reasons = []
                if signal["decision"] != "supported_by_locale_and_script":
                    doc_reasons.append("document_language_needs_review")
                if doc_id in reviews:
                    review = reviews[doc_id]
                    used_reviews.add(doc_id)
                    doc["language_review"] = review
                    if review["decision"] == "accept_kazakh":
                        doc_reasons = []
                    else:
                        doc_reasons = ["human_rejected_document"]
                if doc["test_only"] and test_mode:
                    doc_reasons = []
                if (doc["source_fidelity"] != "official_publisher_snapshot" and not config["allow_reused_text"]):
                    doc_reasons.append("reused_text_not_enabled_in_profile")
                if "\ufffd" in doc["text"]:
                    doc_reasons.append("replacement_character_requires_source_repair")
                doc["quarantine_reasons"] = sorted(set(doc_reasons))
                for p in {p["source"] for p in doc["provenance"]}:
                    source_counts[p] += 1
                language_counts[signal["decision"]] += 1
                fidelity_counts[doc["source_fidelity"]] += 1
                unit_counts[doc["unit_kind"]] += 1
                meta = doc.get("upstream_metadata") or {}
                # Coverage metadata may be absent; never infer an act date from crawl time.
                adopted = str(meta.get("date_adopted") or meta.get("date") or "")
                year = adopted[:4] if adopted[:4].isdigit() and len(adopted) >= 4 else "unknown"
                metadata_coverage["adoption_year"][year] += 1
                for key in ("act_form", "region", "is_repealed"):
                    value = meta.get(key)
                    metadata_coverage[key][str(value) if value not in (None, "") else "unknown"] += 1
                for key in ("title", "source_url", "source_version"):
                    if not doc.get(key):
                        missing[key] += 1
                block_start = 0
                sentence_objects = []
                for block_index, block in enumerate(doc["blocks"]):
                    block_id = digest([doc_id, block_index, block["text"]])
                    block_record = {**block, "block_id": block_id, "document_id": doc_id,
                                    "family_id": doc["family_id"], "block_index": block_index,
                                    "document_start": block_start, "document_end": block_start + len(block["text"])}
                    block_output.write(canonical(block_record) + b"\n")
                    for sentence_index, (start, end) in enumerate(sentence_spans(block["text"])):
                        text = block["text"][start:end]
                        sentence_id = digest([block_id, start, end, text])
                        reasons = list(doc_reasons)
                        if block["kind"] not in {"paragraph", "editorial_note"}:
                            reasons.append("nonprose_structure_retained_not_mlm_text")
                        if block["kind"] == "editorial_note" and not config["keep_editorial_notes"]:
                            reasons.append("editorial_notes_excluded_by_explicit_policy")
                        sent_signal = language_signals(text, declared="kk")
                        if sent_signal["decision"] not in {"supported_by_locale_and_script", "uncertain_short"}:
                            reasons.append("sentence_language_needs_review")
                        if doc["test_only"] and test_mode:
                            reasons = [r for r in reasons if "language" not in r]
                        if sentence_id in reviews:
                            review = reviews[sentence_id]
                            used_reviews.add(sentence_id)
                            if review["decision"] == "accept_kazakh":
                                reasons = [r for r in reasons if r == "human_rejected_document" or "language" not in r]
                            else:
                                reasons.append("human_rejected_sentence")
                        row = {
                            "sentence_id": sentence_id, "document_id": doc_id, "block_id": block_id,
                            "family_id": doc["family_id"], "source_family_ids": doc["source_family_ids"],
                            "text": text, "text_sha256": text_sha(text), "guard_sha256": text_sha(guard_text(text)),
                            "language": "kk", "language_signals": sent_signal,
                            "source_document_id": doc["source_document_id"], "source_url": doc["source_url"],
                            "title": doc["title"], "source_version": doc["source_version"],
                            "upstream_section_title": doc["upstream_section_title"],
                            "article": block["article"], "article_heading": block["article_heading"],
                            "article_occurrence": block["article_occurrence"], "section_path": block["section_path"],
                            "kind": block["kind"], "unit_kind": doc["unit_kind"],
                            "source_fidelity": doc["source_fidelity"], "block_index": block_index,
                            "sentence_index": sentence_index, "block_start": start, "block_end": end,
                            "document_start": block_start + start, "document_end": block_start + end,
                            "retrieved_at": next(p["retrieved_at"] for p in doc["provenance"] if p["receipt_id"] == doc["primary_receipt_id"]),
                            "provenance": doc["provenance"], "block_source_locators": block["source_locators"],
                            "test_only": doc["test_only"], "quarantine_reasons": sorted(set(reasons)),
                        }
                        if sentence_id in reviews:
                            row["language_review"] = reviews[sentence_id]
                        sentence_objects.append(row)
                    block_start += len(block["text"]) + 2
                if doc["unit_kind"] == "upstream_chunk" and config["quarantine_chunk_boundary_sentences"]:
                    prose = [s for s in sentence_objects if s["kind"] in {"paragraph", "editorial_note"}]
                    if prose:
                        for row in (prose[0], prose[-1]):
                            row["quarantine_reasons"] = sorted(set(row["quarantine_reasons"]) | {"upstream_chunk_boundary_uncertain"})
                for row in sentence_objects:
                    row["eligible"] = not row["quarantine_reasons"]
                    eligible_sentences += int(row["eligible"])
                    total_words += len(words(row["text"]))
                    sentence_kinds[row["kind"]] += 1
                    for key in ("source_url", "source_document_id", "title", "source_version", "article", "section_path"):
                        if not row.get(key):
                            sentence_missing[key] += 1
                    for reason in row["quarantine_reasons"]:
                        status_counts[reason] += 1
                    db.execute("INSERT INTO sentences VALUES (?,?,?,?)", (row["sentence_id"], canonical(row).decode(), len(row["text"]), len(words(row["text"]))))
                doc["block_count"] = len(doc["blocks"])
                doc["sentence_count"] = len(sentence_objects)
                del doc["blocks"]
                doc_output.write(canonical(doc) + b"\n")
            block_output.close()
            doc_output.close()
            db.commit()
            if set(reviews) - used_reviews:
                raise CorpusError("Language review contains unknown/stale document or sentence IDs")
            write_jsonl(staging / "sentences.jsonl", (json.loads(row[0]) for row in db.execute("SELECT payload FROM sentences ORDER BY id")))
            write_jsonl(staging / "quarantine.jsonl", sorted(errors, key=digest))
            stats = {
                "raw_content_receipts": sum(r["role"] == "content" for r in receipts),
                "harvested_document_units": harvested, "unique_document_units": unique_docs,
                "duplicate_harvest_units_merged_with_provenance": harvested - unique_docs,
                "documents_by_source": dict(sorted(source_counts.items())),
                "document_language_decisions": dict(sorted(language_counts.items())),
                "document_missing_fields": dict(sorted(missing.items())),
                "sentence_exclusion_reasons": dict(sorted(status_counts.items())),
                "source_parse_rejections": len(errors),
                "eligible_sentences_before_leakage_splitting": eligible_sentences,
                "total_sentence_regex_words_not_model_tokens": total_words,
                "document_units_by_fidelity": dict(sorted(fidelity_counts.items())),
                "document_units_by_kind": dict(sorted(unit_counts.items())),
                "metadata_coverage_document_units": {k: dict(sorted(v.items())) for k, v in metadata_coverage.items()},
                "metadata_coverage_caveat": "Publisher metadata, not independently verified legal status; chunk units are not unique laws",
                "sentences_by_kind": dict(sorted(sentence_kinds.items())),
                "sentence_missing_fields": dict(sorted(sentence_missing.items())),
                "sentence_characters": _summary_lengths(db, "chars"),
                "sentence_regex_words_not_model_tokens": _summary_lengths(db, "words"),
            }
            write_json(staging / "statistics.json", stats)
            write_json(staging / "raw.lock.json", read_json(raw_lock))
            write_json(staging / "pipeline.config.json", config)
            write_json(staging / "identity_links.json", identities)
            write_json(staging / "language_reviews.json", reviews)
            manifest = {
                "schema_version": 1, "stage": "processed", "code_sha256": code_fingerprint(),
                "runtime": {"python": platform.python_version(), "unicode": unicodedata.unidata_version,
                            "beautifulsoup4": version("beautifulsoup4")},
                "raw_lock_id": read_json(raw_lock)["lock_id"], "config_sha256": digest(config),
                "test_only": test_mode or any(r["test_only"] for r in receipts),
                "quarantine_malformed": quarantine_malformed,
                "files": {p.name: file_sha(p) for p in sorted(staging.iterdir()) if p.is_file()},
            }
            manifest["build_id"] = digest(manifest)
            write_json(staging / "manifest.json", manifest)
            os.replace(staging, output)
            return manifest
        finally:
            db.close()
