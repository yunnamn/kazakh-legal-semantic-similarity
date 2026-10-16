"""Adapters consume published text fields only; no generic QA-to-corpus conversion."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from .errors import CorpusError
from .io import source_rows
from .parse import parse_html, parse_text, structure_blocks
from .raw import RawStore, adilet_identity, canonical_adilet


def provenance(receipt: dict, locator: dict) -> dict:
    return {
        "receipt_id": receipt["receipt_id"], "raw_sha256": receipt["sha256"],
        "source": receipt["source"], "acquisition_url": receipt["source_url"],
        "retrieved_at": receipt["retrieved_at"],
        "source_retrieved_at": receipt.get("source_retrieved_at"),
        "source_revision": receipt.get("source_revision"),
        "upstream_path": receipt.get("upstream_path"), "record_locator": locator,
        "acquisition_method": receipt["acquisition_method"],
        "source_review": receipt.get("source_review"),
        "license_evidence_receipt_ids": receipt.get("license_evidence_receipt_ids", []),
        "discovery_provenance": receipt.get("discovery_provenance"),
    }


def candidates(store: RawStore, receipt: dict, *, quarantine: list[dict] | None = None) -> Iterator[dict]:
    adapter = receipt["adapter"]
    path = store.blob(receipt["sha256"])
    if adapter in {"catalog_original", "catalog_clean"}:
        return  # metadata is NEVER misrepresented as statutory body text
    if adapter in {"adilet_html", "adilet_text"}:
        data = path.read_bytes()
        if adapter == "adilet_html":
            blocks, extraction = parse_html(data, selector=receipt.get("selector"), encoding=receipt.get("encoding", "utf-8"))
        else:
            blocks, extraction = parse_text(data, encoding=receipt.get("encoding", "utf-8"))
        yield {
            "family_id": "adilet:" + receipt["source_document_id"],
            "source_document_id": receipt["source_document_id"],
            "source_url": receipt.get("canonical_url", receipt["source_url"]),
            "title": extraction.get("extracted_title") or receipt.get("title"),
            "language": "kk", "source_version": receipt.get("source_version"),
            "unit_kind": "full_document", "upstream_unit_id": "full_document",
            "source_fidelity": "official_publisher_snapshot",
            "blocks": structure_blocks(blocks), "extraction": extraction,
            "provenance": [provenance(receipt, {"document": receipt["source_document_id"]})],
            "upstream_metadata": receipt.get("upstream_metadata", {}),
            "test_only": receipt["test_only"],
        }
        return
    errors = quarantine
    for row, locator in source_rows(path, receipt["format"], quarantine=errors):
        try:
            if adapter == "legalrag":
                # In this publisher's schema `doc_id` is often a TITLE, not an act ID.
                url = row.get("source")
                if not isinstance(url, str):
                    raise CorpusError("LegalRAG row is missing its document source URL")
                doc_id, locale = adilet_identity(url, require_kazakh=True)
                text = row.get("text")
                chunk_id = row.get("chunk_id")
                if chunk_id is None or not isinstance(chunk_id, (int, str)):
                    raise CorpusError("LegalRAG chunk lacks a stable chunk_id")
                family = "adilet:" + doc_id
                title = row.get("doc_id") or None
                unit_kind, unit_id = "upstream_chunk", "chunk:" + str(chunk_id)
                locator = {**locator, "upstream_chunk_id": chunk_id}
                upstream = {k: row.get(k) for k in ("doc_id", "date", "section_title", "words", "char_len", "word_len")}
            elif adapter == "kurumikz":
                if row.get("src") not in {"zan.gov.kz", "https://zan.gov.kz", "https://zan.gov.kz/"}:
                    raise CorpusError("Unexpected source registry; do not invent a document URL")
                doc_id = row.get("id")
                if not isinstance(doc_id, (str, int)) or str(doc_id).strip() == "":
                    raise CorpusError("Registry row lacks its source ID")
                doc_id = str(doc_id)
                family = "zan:" + doc_id
                text = row.get("kk")
                url = None  # The card supplies a DOMAIN and ID, not a verified per-act URL.
                title = None
                unit_kind, unit_id = "full_document", "full_document"
                upstream = {k: row.get(k) for k in ("id", "src", "ckk", "cru", "hkk", "hru", "kk_r", "qs")}
            else:
                raise CorpusError(f"Unsupported adapter {adapter}")
            if not isinstance(text, str) or not text.strip():
                raise CorpusError("Source body text is absent; titles/descriptions are not substitutes")
            blocks, extraction = parse_text(text.encode("utf-8"))
            yield {
                "family_id": family, "source_document_id": doc_id, "source_url": url,
                "source_registry": "zan.gov.kz" if adapter == "kurumikz" else "adilet.zan.kz",
                "title": title, "language": "kk", "source_version": None,
                "unit_kind": unit_kind, "upstream_unit_id": unit_id,
                "source_fidelity": "publisher_processed_text_not_original_html",
                "blocks": structure_blocks(blocks), "extraction": extraction,
                "upstream_metadata": upstream,
                "provenance": [provenance(receipt, locator)], "test_only": receipt["test_only"],
            }
        except (CorpusError, TypeError, ValueError) as exc:
            if errors is None:
                raise CorpusError(f"Bad source record {locator}: {exc}") from exc
            errors.append({"receipt_id": receipt["receipt_id"], "record_locator": locator,
                           "reason": "invalid_source_record", "detail": str(exc)[:500]})
