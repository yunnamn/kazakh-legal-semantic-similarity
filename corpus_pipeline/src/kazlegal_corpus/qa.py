"""Deterministic source QA templates; never fabricated annotations or judgements."""
from __future__ import annotations
from pathlib import Path
from .config import SPLITS
from .errors import CorpusError
from .integrity import verify_artifacts
from .io import digest, iter_jsonl, timestamp, write_jsonl


def required_sample(derived: Path, count_per_source: int) -> list[tuple[str, str]]:
    groups: dict[str, set[str]] = {}
    for split in SPLITS:
        for row in iter_jsonl(derived / "splits" / (split + ".jsonl")):
            for p in row["provenance"]:
                groups.setdefault(p["source"], set()).add(row["document_id"])
    selected = []
    for source in sorted(groups):
        ids = sorted(groups[source], key=lambda d: (digest(["source-qa-v1", source, d]), d))[:count_per_source]
        selected.extend((source, d) for d in ids)
    return selected


def make_qa_template(processed: Path, derived: Path, output: Path, *, count_per_source: int) -> int:
    verify_artifacts(processed)
    dm = verify_artifacts(derived)
    sample = required_sample(derived, count_per_source)
    needed = {doc_id for _, doc_id in sample}
    docs = {d["document_id"]: d for d in iter_jsonl(processed / "documents.jsonl") if d["document_id"] in needed}
    rows = []
    for source, doc_id in sample:
        d = docs[doc_id]
        rows.append({"sample_id": digest([dm["build_id"], source, doc_id]), "derived_build_id": dm["build_id"],
                     "source": source, "document_id": doc_id, "source_document_id": d["source_document_id"],
                     "source_url": d["source_url"], "title": d["title"], "processed_text_sha256": d["text_sha256"],
                     "provenance": d["provenance"], "text_preview_not_full_review": d["text"][:2000],
                     "authentic_source_verified": None, "language_ok": None, "structure_and_boundaries_ok": None,
                     "normalization_and_notes_ok": None, "decision": None,
                     "reviewer": None, "reviewed_at": None, "evidence_and_notes": None})
    write_jsonl(output, rows)
    return len(rows)


def validate_qa(derived: Path, review_path: Path, *, count_per_source: int) -> dict:
    dm = verify_artifacts(derived)
    required = set(required_sample(derived, count_per_source))
    if not required:
        raise CorpusError("There are no retained documents to review")
    seen = set()
    for row in iter_jsonl(review_path):
        key = (row.get("source"), row.get("document_id"))
        if key not in required or key in seen:
            raise CorpusError("QA response includes an unexpected or duplicated sample")
        if row.get("derived_build_id") != dm["build_id"] or row.get("sample_id") != digest([dm["build_id"], *key]):
            raise CorpusError("QA response belongs to another corpus build")
        if row.get("decision") != "accept":
            raise CorpusError("A QA document was not accepted. Fix/quarantine the source and rebuild, do not discard the review")
        for check in ("authentic_source_verified", "language_ok", "structure_and_boundaries_ok", "normalization_and_notes_ok"):
            if row.get(check) is not True:
                raise CorpusError(f"Uncompleted or failed human QA: {check}")
        if not row.get("reviewer") or not row.get("evidence_and_notes"):
            raise CorpusError("QA requires an actual reviewer and evidence/notes")
        timestamp(row.get("reviewed_at"))
        seen.add(key)
    if seen != required:
        raise CorpusError("The complete deterministic QA sample has not been reviewed")
    return {"reviewed_source_document_samples": len(seen), "source_count": len({x[0] for x in seen})}
