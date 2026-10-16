import json
import pytest
from kazlegal_corpus.acquire import acquire_adilet
from kazlegal_corpus.adapters import candidates
from kazlegal_corpus.discover import catalog_manifest
from kazlegal_corpus.errors import CorpusError
from kazlegal_corpus.io import iter_jsonl, read_json, write_jsonl
from kazlegal_corpus.raw import RawStore
from conftest import STAMP, fixture_review


class MarkedFixtureStore(RawStore):
    def register(self, path, metadata):
        return super().register(path, {**metadata, "test_only": True})


class FixtureClient:
    user_agent = "TEST_ONLY"
    delay = 0
    def __init__(self, *, robots="User-agent: *\nAllow: /\n", html='<div id="text">TEST_ONLY content</div>', fail=False):
        self.robots = robots; self.html = html; self.fail = fail; self.calls = []
    def fetch(self, url, **kwargs):
        self.calls.append(url)
        if self.fail and not url.endswith("robots.txt"):
            raise CorpusError("TEST_ONLY HTTP 403 stop")
        data = self.robots if url.endswith("robots.txt") else self.html
        return data.encode(), {"retrieved_at": STAMP, "final_url": url, "http_status": 200,
                               "content_type": "text/plain" if url.endswith("robots.txt") else "text/html"}


def manifest(tmp_path):
    path = tmp_path / "manifest.jsonl"
    write_jsonl(path, [{"source_document_id": "TEST000001", "url": "https://adilet.zan.kz/kaz/docs/TEST000001"}])
    return path


def test_bot_challenge_cannot_become_corpus(tmp_path):
    store = MarkedFixtureStore(tmp_path / "raw")
    with pytest.raises(CorpusError, match="challenge"):
        acquire_adilet(manifest(tmp_path), store, fixture_review(), contact="test@example.invalid",
                       report_path=tmp_path / "report.json", client=FixtureClient(html="Just a moment... cf-chl-platform"))
    receipts = [read_json(p) for p in (store.root / "receipts").glob("*.json")]
    assert receipts and all(r["role"] == "access_evidence" for r in receipts)
    assert read_json(tmp_path / "report.json")["status"] == "stopped"


def test_robots_disallow_stops_before_document_request(tmp_path):
    client = FixtureClient(robots="User-agent: *\nDisallow: /kaz/docs/\n")
    with pytest.raises(CorpusError, match="disallows"):
        acquire_adilet(manifest(tmp_path), MarkedFixtureStore(tmp_path / "raw"), fixture_review(), contact="test@example.invalid",
                       report_path=tmp_path / "report.json", client=client)
    assert len(client.calls) == 1


def test_http_access_failure_preserves_failure_report(tmp_path):
    with pytest.raises(CorpusError, match="403"):
        acquire_adilet(manifest(tmp_path), MarkedFixtureStore(tmp_path / "raw"), fixture_review(), contact="test@example.invalid",
                       report_path=tmp_path / "report.json", client=FixtureClient(fail=True))
    assert read_json(tmp_path / "report.json")["status"] == "stopped"


def hub_fixture(tmp_path, store, source, adapter, rows, format_name="jsonl"):
    p = tmp_path / (adapter + ".jsonl")
    write_jsonl(p, rows)
    return store.register(p, {"source": source, "adapter": adapter, "format": format_name,
        "source_url": "https://example.invalid/TEST_ONLY", "source_revision": "a" * 40,
        "upstream_path": "TEST_ONLY.jsonl", "retrieved_at": STAMP, "imported_at": STAMP,
        "source_retrieved_at": None, "acquisition_method": "manual", "acquisition_note": "TEST_ONLY row fixture",
        "source_review": fixture_review(source), "test_only": True})


def test_metadata_catalog_never_becomes_statutory_body(tmp_path, raw_store):
    r = hub_fixture(tmp_path, raw_store, "Arailym-tleubayeva/KazakhLawCorpus-clean", "catalog_clean",
                    [{"law_id": "TEST000001", "title": "TEST_ONLY title", "description": "TEST_ONLY NOT A BODY",
                      "adilet_url": "https://adilet.zan.kz/rus/docs/TEST000001"}])
    assert list(candidates(raw_store, r)) == []
    target = tmp_path / "discovery.jsonl"
    report = catalog_manifest(raw_store, r["receipt_id"], target, limit=10)
    row = next(iter_jsonl(target))
    assert row["url"] == "https://adilet.zan.kz/kaz/docs/TEST000001"
    assert row["metadata"]["original_adilet_url"].find("/rus/") > 0
    assert "text" not in row and report["selected_acts"] == 1


def test_legalrag_title_not_mistaken_for_law_id(tmp_path, raw_store):
    r = hub_fixture(tmp_path, raw_store, "Arailym-tleubayeva/LegalRAG", "legalrag",
                    [{"doc_id": "TEST_ONLY This field is a title", "source": "https://adilet.zan.kz/kaz/docs/TEST000001",
                      "chunk_id": 9, "text": "TEST_ONLY unmodified publisher text."}])
    result = next(candidates(raw_store, r))
    assert result["source_document_id"] == "TEST000001"
    assert result["title"] == "TEST_ONLY This field is a title"
    assert result["unit_kind"] == "upstream_chunk"
    assert result["provenance"][0]["record_locator"]["upstream_chunk_id"] == 9


def test_kurumikz_missing_url_title_and_original_scrape_date_stay_unknown(tmp_path, raw_store):
    r = hub_fixture(tmp_path, raw_store, "kurumikz/kazakhstan_legal_corpus", "kurumikz",
                    [{"id": 42, "src": "zan.gov.kz", "kk": "TEST_ONLY publisher text.", "ru": "TEST_ONLY excluded language"}])
    result = next(candidates(raw_store, r))
    assert result["source_url"] is None and result["title"] is None
    assert result["family_id"] == "zan:42"
    assert result["provenance"][0]["source_retrieved_at"] is None
    assert "excluded language" not in result["blocks"][0]["text"]


def test_arbitrary_synthetic_qa_adapter_is_refused(tmp_path, raw_store):
    p = tmp_path / "qa.jsonl"; p.write_text('{"text":"TEST_ONLY synthetic QA"}\n')
    with pytest.raises(CorpusError, match="Unapproved"):
        raw_store.register(p, {"source": "unknown-generated-qa", "adapter": "qa_to_legal_text",
            "source_url": "https://example.invalid/TEST_ONLY", "retrieved_at": STAMP,
            "acquisition_method": "manual", "test_only": True})
