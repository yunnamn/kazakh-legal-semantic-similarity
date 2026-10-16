"""Immutable raw bytes and acquisition receipts. Raw != normalized != training data."""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .errors import CorpusError
from .io import digest, file_sha, read_json, safe_relative, timestamp, utc_now, write_json

DATASET_ADAPTERS = {
    "Arailym-tleubayeva/KazakhLawCorpus-clean": "catalog_clean",
    "Arailym-tleubayeva/KazakhLawCorpus": "catalog_original",
    "Arailym-tleubayeva/LegalRAG": "legalrag",
    "kurumikz/kazakhstan_legal_corpus": "kurumikz",
}
ADAPTERS = set(DATASET_ADAPTERS.values()) | {"adilet_html", "adilet_text"}
NON_CONTENT_ROLES = {"license_evidence", "access_evidence", "discovery_evidence"}


def adilet_identity(url: str, *, require_kazakh: bool = False) -> tuple[str, str]:
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname != "adilet.zan.kz" or parts.port
            or parts.username or parts.password):
        raise CorpusError(f"Not an approved Adilet HTTPS URL: {url!r}")
    match = re.fullmatch(r"/(kaz|rus|eng)/docs/([A-Za-z0-9_]+)/?", parts.path)
    if not match:
        raise CorpusError("Expected an Adilet document URL, not a search/info/compare page")
    lang, document_id = match.groups()
    if require_kazakh and lang != "kaz":
        raise CorpusError("The corpus requires the Kazakh document endpoint")
    return document_id, lang


def canonical_adilet(document_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]{6,40}", document_id):
        raise CorpusError(f"Invalid Adilet identifier: {document_id!r}")
    return f"https://adilet.zan.kz/kaz/docs/{document_id}"


def check_review(review: dict, source: str, *, test_only: bool = False) -> dict:
    if test_only:
        return review
    required = ("source", "license", "license_url", "attribution", "reviewer",
                "reviewed_at", "access_basis", "authenticity_assessment", "redistribution")
    for key in required:
        if not isinstance(review.get(key), str) or not review[key].strip():
            raise CorpusError(f"Source review missing {key!r}; see configs/source-review.example.json")
        if review[key].startswith("REPLACE_"):
            raise CorpusError("Example source reviews are not approvals")
    if review["source"] != source or review.get("research_use_approved") is not True:
        raise CorpusError(f"Research use has not been explicitly reviewed for source {source}")
    timestamp(review["reviewed_at"])
    if review["redistribution"] not in {"permitted", "not_permitted", "pending_review"}:
        raise CorpusError("Unknown redistribution status")
    return review


def receipt_references(value) -> set[str]:
    """Collect explicit acquisition/evidence links, including nested discovery lineage."""
    result = set()
    if isinstance(value, dict):
        for key, val in value.items():
            if key.endswith("receipt_ids") and isinstance(val, list):
                result.update(v for v in val if isinstance(v, str))
            elif key.endswith("receipt_id") and isinstance(val, str):
                result.add(val)
            else:
                result.update(receipt_references(val))
    elif isinstance(value, list):
        for val in value:
            result.update(receipt_references(val))
    return result


class RawStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def blob(self, sha256: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{64}", sha256):
            raise CorpusError("Invalid SHA-256")
        return self.root / "blobs" / "sha256" / sha256[:2] / sha256

    def receipt_path(self, receipt_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{64}", receipt_id):
            raise CorpusError("Invalid receipt identifier")
        return self.root / "receipts" / f"{receipt_id}.json"

    def register(self, path: Path, metadata: dict) -> dict:
        if not Path(path).is_file():
            raise CorpusError(f"Input file not found: {path}")
        meta = dict(metadata)
        for forbidden in ("receipt_id", "byte_size", "blob_path"):
            if forbidden in meta:
                raise CorpusError(f"Acquisition sidecar must not supply generated field {forbidden}")
        expected_sha = meta.pop("expected_sha256", None)
        if "sha256" in meta:
            raise CorpusError("Use expected_sha256, not sha256, in acquisition sidecars")
        meta.setdefault("schema_version", 1)
        meta.setdefault("role", "content")
        meta.setdefault("test_only", False)
        meta.setdefault("original_filename", Path(path).name)
        meta.setdefault("imported_at", utc_now())
        meta["retrieved_at"] = timestamp(meta.get("retrieved_at"))
        meta["imported_at"] = timestamp(meta["imported_at"])
        if meta.get("source_retrieved_at") is not None:
            meta["source_retrieved_at"] = timestamp(meta["source_retrieved_at"])
        if not meta.get("acquisition_method") or not meta.get("source"):
            raise CorpusError("A receipt needs source and acquisition_method")
        if not meta.get("source_url"):
            raise CorpusError("A receipt needs the actual acquisition URL")
        if meta["role"] == "content":
            adapter = meta.get("adapter")
            if adapter not in ADAPTERS:
                raise CorpusError("Unapproved adapter: arbitrary text, generated QA and C4 are not accepted")
            check_review(meta.get("source_review", {}), meta["source"], test_only=meta["test_only"])
            if adapter.startswith("adilet_") and not meta["test_only"]:
                url = meta.get("canonical_url") or meta["source_url"]
                doc_id, _ = adilet_identity(url, require_kazakh=True)
                if meta.get("source_document_id") != doc_id:
                    raise CorpusError("Document ID and canonical Adilet URL disagree")
                if urlsplit(meta["source_url"]).hostname != "adilet.zan.kz":
                    raise CorpusError("An official snapshot must have an actual official-source acquisition URL")
                if meta["source"] != "adilet":
                    raise CorpusError("Official adapters must identify Adilet as their source")
                if meta.get("language") not in {"kk", "kaz"}:
                    raise CorpusError("Official input must declare Kazakh")
            elif adapter in DATASET_ADAPTERS.values() and not meta["test_only"]:
                if DATASET_ADAPTERS.get(meta["source"]) != adapter:
                    raise CorpusError("Dataset/adapter mismatch; do not repurpose a QA or unknown dataset")
                if not re.fullmatch(r"[a-f0-9]{40}", meta.get("source_revision", "")):
                    raise CorpusError("Reusable datasets require a full pinned Hub commit hash")
                if not meta.get("upstream_path"):
                    raise CorpusError("Reusable inputs need the exact filename at the pinned revision")
            if meta["acquisition_method"] == "manual" and not meta.get("acquisition_note"):
                raise CorpusError("Manual acquisitions need an explanation of how authentic bytes were saved")
        elif meta["role"] not in NON_CONTENT_ROLES:
            raise CorpusError("Unknown raw artifact role")
        sha = file_sha(path)
        if expected_sha and expected_sha != sha:
            raise CorpusError("Downloaded/manual file does not match expected_sha256")
        target = self.blob(sha)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if file_sha(target) != sha:
                raise CorpusError("Existing raw blob is corrupt")
        else:
            fd, temporary = tempfile.mkstemp(prefix=".raw-", dir=target.parent)
            try:
                copied = hashlib.sha256()
                with Path(path).open("rb") as source, os.fdopen(fd, "wb") as dest:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        copied.update(chunk)
                        dest.write(chunk)
                    dest.flush()
                    os.fsync(dest.fileno())
                if copied.hexdigest() != sha:
                    raise CorpusError("Input file changed while being registered")
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
        meta.update({"sha256": sha, "byte_size": target.stat().st_size,
                     "blob_path": target.relative_to(self.root).as_posix()})
        receipt_id = digest(meta)
        receipt = {**meta, "receipt_id": receipt_id}
        write_json(self.receipt_path(receipt_id), receipt)
        return receipt

    def load(self, receipt_id: str, *, verify_blob: bool = True) -> dict:
        receipt = read_json(self.receipt_path(receipt_id))
        payload = {k: v for k, v in receipt.items() if k != "receipt_id"}
        if digest(payload) != receipt_id or receipt.get("receipt_id") != receipt_id:
            raise CorpusError("Receipt integrity check failed")
        blob_path = safe_relative(self.root, receipt["blob_path"])
        if blob_path != self.blob(receipt["sha256"]).resolve():
            raise CorpusError("Receipt points to a noncanonical raw blob path")
        if verify_blob and (file_sha(blob_path) != receipt["sha256"]
                            or blob_path.stat().st_size != receipt["byte_size"]):
            raise CorpusError("Raw blob integrity check failed")
        return receipt

    def freeze(self, output: Path, receipt_ids: list[str] | None = None) -> dict:
        ids = receipt_ids or [p.stem for p in (self.root / "receipts").glob("*.json")]
        # Freeze transitive evidence, not only text receipts.
        pending = list(ids)
        closure = set()
        while pending:
            current = pending.pop()
            if current in closure:
                continue
            r = self.load(current)
            closure.add(current)
            pending.extend(receipt_references(r) - {current})
        records = []
        for receipt_id in sorted(closure):
            r = self.load(receipt_id)
            records.append({"receipt_id": receipt_id, "sha256": r["sha256"], "role": r["role"],
                            "test_only": r["test_only"]})
        if not any(r["role"] == "content" for r in records):
            raise CorpusError("No content acquisitions to freeze")
        lock = {"schema_version": 1, "receipts": records}
        lock["lock_id"] = digest(lock)
        write_json(output, lock)
        return lock

    def load_lock(self, path: Path, *, test_mode: bool = False) -> list[dict]:
        lock = read_json(path)
        if digest({k: v for k, v in lock.items() if k != "lock_id"}) != lock.get("lock_id"):
            raise CorpusError("Raw lock integrity check failed")
        result = []
        ids = {item["receipt_id"] for item in lock["receipts"]}
        if len(ids) != len(lock["receipts"]):
            raise CorpusError("Raw lock contains duplicate receipts")
        for item in lock["receipts"]:
            r = self.load(item["receipt_id"])
            if any(r[key] != item.get(key) for key in ("sha256", "role", "test_only")):
                raise CorpusError("Raw lock and receipt disagree")
            if r["test_only"] and not test_mode:
                raise CorpusError("TEST_ONLY data cannot enter a production corpus")
            if not receipt_references(r).issubset(ids):
                raise CorpusError("Raw lock is missing transitive provenance/evidence receipts")
            result.append(r)
        return result
