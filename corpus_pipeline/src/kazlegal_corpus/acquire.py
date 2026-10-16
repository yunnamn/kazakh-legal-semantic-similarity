"""Publisher-friendly acquisition. No proxy rotation, CAPTCHA solving, or stealth."""
from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from .errors import CorpusError
from .io import canonical, iter_jsonl, read_json, utc_now, write_json, write_jsonl
from .raw import DATASET_ADAPTERS, RawStore, adilet_identity, check_review

CHALLENGE = re.compile(r"cf-chl-|challenge-platform|g-recaptcha|hcaptcha|verify\s+(?:that\s+)?you\s+are\s+human|checking\s+your\s+browser|just\s+a\s+moment", re.I)


class _SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        if (new.scheme != "https" or new.hostname != old.hostname or new.port
                or new.username or new.password):
            raise CorpusError("Cross-host/insecure redirect refused; review acquisition manually")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PoliteAdiletClient:
    def __init__(self, contact: str, *, delay_seconds: float = 3.0, timeout: float = 30.0):
        if not contact.strip() or "REPLACE_" in contact:
            raise CorpusError("Supply a real research contact in the User-Agent")
        self.user_agent = f"KazLegalCorpus/0.1 (+{contact})"
        self.delay = max(2.0, delay_seconds)
        self.timeout = timeout
        self.last_request: float | None = None
        self.opener = build_opener(_SameHostRedirect())

    def fetch(self, url: str, *, maximum_bytes: int = 100_000_000) -> tuple[bytes, dict]:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname != "adilet.zan.kz":
            raise CorpusError("This client only retrieves HTTPS content from Adilet")
        if self.last_request is not None:
            time.sleep(max(0.0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "text/html,text/plain;q=0.9"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                chunks = []
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > maximum_bytes:
                        raise CorpusError("Response exceeds configured byte limit")
                    chunks.append(chunk)
                return b"".join(chunks), {
                    "final_url": response.url, "http_status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "retrieved_at": utc_now(),
                }
        except HTTPError as exc:
            detail = f"HTTP {exc.code}; Retry-After={exc.headers.get('Retry-After')}"
            raise CorpusError(f"{detail}. Acquisition stopped; do not bypass access controls.") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise CorpusError(f"Acquisition unavailable: {exc}. Use the documented lawful manual import.") from exc


def _register_bytes(store: RawStore, data: bytes, metadata: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "response.bin"
        path.write_bytes(data)
        return store.register(path, metadata)


def acquire_adilet(manifest: Path, store: RawStore, review: dict, *, contact: str,
                   report_path: Path, selector: str | None = None,
                   client: PoliteAdiletClient | None = None) -> dict:
    check_review(review, "adilet")
    rows = list(iter_jsonl(manifest))
    if not rows:
        raise CorpusError("Empty acquisition manifest")
    for row in rows:
        doc_id, _ = adilet_identity(row["url"], require_kazakh=True)
        if doc_id != row["source_document_id"]:
            raise CorpusError("Manifest URL/document ID mismatch")
    client = client or PoliteAdiletClient(contact)
    report: dict = {"schema_version": 1, "attempted_at": utc_now(), "acquisitions": [], "status": "running"}
    try:
        robots_url = "https://adilet.zan.kz/robots.txt"
        robots_bytes, robots_headers = client.fetch(robots_url, maximum_bytes=1_000_000)
        if CHALLENGE.search(robots_bytes.decode("utf-8", errors="replace")):
            raise CorpusError("robots.txt returned a bot challenge; automated acquisition is not authorized")
        robots_text = robots_bytes.decode("utf-8-sig", errors="strict")
        # A successful HTML page in place of robots is not a usable access policy.
        if re.search(r"<\s*(?:html|!doctype)", robots_text, re.I):
            raise CorpusError("robots.txt is HTML rather than a usable robots policy")
        robots_receipt = _register_bytes(store, robots_bytes, {
            "role": "access_evidence", "source": "adilet", "source_url": robots_url,
            "acquisition_method": "http", "original_filename": "robots.txt", **robots_headers,
        })
        robot = RobotFileParser(robots_url)
        robot.parse(robots_text.splitlines())
        crawl_delay = robot.crawl_delay(client.user_agent) or robot.crawl_delay("*")
        if crawl_delay:
            client.delay = max(client.delay, crawl_delay)
        for row in sorted(rows, key=lambda r: r["source_document_id"]):
            if not robot.can_fetch(client.user_agent, row["url"]):
                raise CorpusError(f"robots.txt disallows {row['url']}; seek a permitted export")
            body, headers = client.fetch(row["url"])
            final_id, _ = adilet_identity(headers["final_url"], require_kazakh=True)
            if final_id != row["source_document_id"]:
                raise CorpusError("Redirect changed the requested legal act")
            meta = {
                "source": "adilet", "source_url": row["url"], "canonical_url": row["url"],
                "source_document_id": row["source_document_id"], "language": "kk",
                "title": row.get("title"), "upstream_metadata": row.get("metadata", {}),
                "discovery_provenance": row.get("discovery_provenance"),
                "source_review": review, "acquisition_method": "http", "adapter": "adilet_html",
                "format": "html", "selector": selector, "robots_receipt_id": robots_receipt["receipt_id"],
                "original_filename": row["source_document_id"] + ".html", **headers,
            }
            if CHALLENGE.search(body[:1_000_000].decode("utf-8", errors="replace")):
                rejected = _register_bytes(store, body, {**meta, "role": "access_evidence"})
                report["acquisitions"].append({"document_id": final_id, "status": "challenge",
                                               "receipt_id": rejected["receipt_id"]})
                raise CorpusError("An HTTP-200 bot challenge was saved as access evidence, NOT corpus text")
            content_type = headers.get("content_type") or ""
            if "html" not in content_type.lower():
                raise CorpusError(f"Expected HTML, got {content_type!r}; use an explicit export adapter")
            receipt = _register_bytes(store, body, meta)
            report["acquisitions"].append({"document_id": final_id, "status": "acquired",
                                           "receipt_id": receipt["receipt_id"]})
        report["status"] = "completed"
    except Exception as exc:
        report.update({"status": "stopped", "error": str(exc)})
        write_json(report_path, report)
        raise
    write_json(report_path, report)
    return report


def inspect_hub(repo_id: str) -> dict:
    if repo_id not in DATASET_ADAPTERS:
        raise CorpusError("Source is not in the reviewed candidate registry")
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise CorpusError("Install kazlegal-corpus[hub] for Hub acquisition") from exc
    api = HfApi()
    info = api.dataset_info(repo_id)
    files = api.list_repo_files(repo_id, repo_type="dataset", revision=info.sha)
    return {"repo_id": repo_id, "revision": info.sha, "files": sorted(files),
            "adapter": DATASET_ADAPTERS[repo_id],
            "warning": "Discovery only. Read the pinned dataset card/license; no reuse approval is implied."}


def acquire_hub(store: RawStore, *, repo_id: str, revision: str, filenames: list[str],
                format_name: str, review: dict, output: Path,
                expected_hashes: dict[str, str] | None = None,
                local_files_only: bool = False) -> dict:
    if repo_id not in DATASET_ADAPTERS:
        raise CorpusError("Unsupported dataset. Generated legal QA is deliberately not ingestible.")
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise CorpusError("A full immutable 40-character Hub revision is required, not 'main'")
    check_review(review, repo_id)
    if not filenames or any(Path(p).is_absolute() or ".." in Path(p).parts for p in filenames):
        raise CorpusError("Supply exact safe upstream filenames, not globs")
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise CorpusError("Install the optional hub dependency or use manual file import") from exc
    # The card is a compulsory frozen part of the provenance chain.
    files = sorted(set(filenames) | {"README.md"})
    results = []
    license_receipt_ids = []
    # Download the card first and keep it unchanged. Its declarations are not a legal opinion.
    files.sort(key=lambda f: (f != "README.md", f))
    for name in files:
        try:
            path = Path(hf_hub_download(repo_id=repo_id, repo_type="dataset", revision=revision,
                                        filename=name, local_files_only=local_files_only))
        except Exception as exc:
            raise CorpusError(f"Pinned Hub acquisition failed for {name}: {exc}") from exc
        evidence = Path(name).name.upper() in {"README.MD", "LICENSE", "LICENSE.TXT", "NOTICE"}
        metadata = {
            "role": "license_evidence" if evidence else "content",
            "source": repo_id,
            "source_url": f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{name}",
            "source_revision": revision, "upstream_path": name, "source_review": review,
            "adapter": DATASET_ADAPTERS[repo_id], "format": format_name,
            "retrieved_at": utc_now(), "source_retrieved_at": None,
            "acquisition_method": "hub_pinned_download", "original_filename": name,
            "license_evidence_receipt_ids": list(license_receipt_ids),
        }
        if expected_hashes and name in expected_hashes:
            metadata["expected_sha256"] = expected_hashes[name]
        receipt = store.register(path, metadata)
        if evidence:
            license_receipt_ids.append(receipt["receipt_id"])
        results.append({"filename": name, "sha256": receipt["sha256"], "receipt_id": receipt["receipt_id"]})
    lock = {"repo_id": repo_id, "revision": revision, "files": results,
            "upstream_scrape_time": "unknown unless supplied by the publisher; not the Hub download time"}
    write_json(output, lock)
    return lock
