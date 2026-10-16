"""Reuse catalog metadata before making any requests to a legislative portal."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from .adapters import provenance
from .errors import CorpusError
from .io import digest, source_rows, write_json, write_jsonl
from .raw import RawStore, adilet_identity, canonical_adilet


def catalog_manifest(store: RawStore, receipt_id: str, output: Path, *, limit: int,
                     seed: str = "kazlegal-discovery-v1", status: str = "all") -> dict:
    """Hash-ranked document sample. This is not a representative-law claim.

    For a census, set limit larger than the catalog. Original metadata including
    date, act form, region and status is kept for coverage/stratification audits.
    No title, description or catalog field is treated as legislative body text.
    """
    if limit <= 0 or status not in {"all", "not_marked_repealed"}:
        raise CorpusError("Invalid discovery limit/status")
    receipt = store.load(receipt_id)
    if receipt.get("adapter") not in {"catalog_clean", "catalog_original"}:
        raise CorpusError("Discovery needs a reviewed metadata catalog, not arbitrary text")
    by_id: dict[str, dict] = {}
    rejected = []
    seen = 0
    for row, locator in source_rows(store.blob(receipt["sha256"]), receipt["format"]):
        seen += 1
        doc_id = row.get("law_id")
        if not isinstance(doc_id, str) or not doc_id:
            rejected.append({"locator": locator, "reason": "missing_law_id"})
            continue
        try:
            url = canonical_adilet(doc_id)
            original = row.get("adilet_url")
            if original:
                original_id, _ = adilet_identity(original)
                if original_id != doc_id:
                    raise CorpusError("Catalog ID/URL mismatch")
        except CorpusError as exc:
            rejected.append({"locator": locator, "reason": str(exc)})
            continue
        if status == "not_marked_repealed" and str(row.get("is_repealed", "")).lower() in {"true", "t", "1"}:
            continue
        title = row.get("title_kk") or row.get("title") or None
        item = {"source_document_id": doc_id, "url": url, "title": title,
                "metadata": {**row, "original_adilet_url": original,
                             "requested_language_endpoint": "kaz"},
                "discovery_provenance": [provenance(receipt, locator)]}
        if doc_id in by_id:
            # Retain metadata variants rather than allowing file order to pick a legal version.
            old = by_id[doc_id]
            variants = old.setdefault("metadata_variants", [old["metadata"]])
            variants.append(item["metadata"])
            variants.sort(key=digest)
            old["discovery_provenance"].extend(item["discovery_provenance"])
            old["discovery_provenance"].sort(key=digest)
            old["metadata"] = variants[0]
            titles = [x for x in (old["title"], title) if x]
            old["title"] = sorted(titles)[0] if titles else None
        else:
            by_id[doc_id] = item
    chosen = sorted(by_id.values(), key=lambda r: (digest([seed, r["source_document_id"]]), r["source_document_id"]))[:limit]
    chosen.sort(key=lambda r: r["source_document_id"])
    write_jsonl(output, chosen)
    summary = {"schema_version": 1, "catalog_receipt_id": receipt_id,
               "input_rows": seen, "eligible_unique_acts": len(by_id), "selected_acts": len(chosen),
               "limit": limit, "seed": seed, "status_policy": status,
               "sampling": "document-ID hash ranking, not relevance or model-score sampling",
               "selected_act_form": dict(sorted(Counter(str(r["metadata"].get("act_form", "unknown")) for r in chosen).items())),
               "rejections": rejected,
               "warning": "not_marked_repealed is publisher metadata, not a legal opinion on current validity"}
    write_json(output.with_suffix(output.suffix + ".report.json"), summary)
    return summary
