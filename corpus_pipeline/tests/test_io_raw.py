import gzip
import json
import pytest
from kazlegal_corpus.errors import CorpusError
from kazlegal_corpus.io import source_rows, timestamp, write_json
from kazlegal_corpus.raw import RawStore, adilet_identity
from conftest import STAMP, make_receipt, fixture_review, unique_sentence


@pytest.mark.parametrize("value", [None, "2026-09-07", "not a timestamp"])
def test_retrieval_timestamp_not_guessed(value):
    with pytest.raises(CorpusError):
        timestamp(value)


def test_jsonl_corruption_is_explicit(tmp_path):
    p = tmp_path / "fixture.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as handle:
        handle.write('{"text":"TEST_ONLY good"}\n{"text":"BROKEN\n{"text":"TEST_ONLY second"}\n')
    with pytest.raises(CorpusError):
        list(source_rows(p, "jsonl.gz"))
    errors = []
    rows = list(source_rows(p, "jsonl.gz", quarantine=errors))
    assert len(rows) == 2 and errors[0]["line"] == 2
    assert len(errors[0]["decoded_line_sha256"]) == 64


@pytest.mark.parametrize("data", ['[{"x":"TEST_ONLY"},]', '[{"x":"TEST_ONLY"}', '[1]', '[{"x":"TEST_ONLY"}] trailing'])
def test_json_array_does_not_repair(data, tmp_path):
    p = tmp_path / "x.json"; p.write_text(data)
    with pytest.raises(CorpusError):
        list(source_rows(p, "json"))


def test_stream_json_array_large_record(tmp_path):
    p = tmp_path / "x.json"
    records = [{"text": "TEST_ONLY " + "x" * 80000}, {"text": "TEST_ONLY second"}]
    p.write_text(json.dumps(records))
    assert [r for r, _ in source_rows(p, "json")] == records


def test_duplicate_csv_header_refused(tmp_path):
    p = tmp_path / "x.csv"; p.write_text("text,text\nTEST_ONLY,TEST_ONLY\n")
    with pytest.raises(CorpusError):
        list(source_rows(p, "csv"))


def test_raw_mutation_detected(tmp_path, raw_store):
    receipt = make_receipt(tmp_path, raw_store, "TEST000001", [unique_sentence(1)])
    raw_store.load(receipt["receipt_id"])
    raw_store.blob(receipt["sha256"]).write_bytes(b"MUTATED_TEST_ONLY")
    with pytest.raises(CorpusError, match="integrity"):
        raw_store.load(receipt["receipt_id"])


def test_test_only_lock_cannot_be_processed_normally(tmp_path, raw_store):
    make_receipt(tmp_path, raw_store, "TEST000001", [unique_sentence(1)])
    lock = tmp_path / "raw.lock.json"; raw_store.freeze(lock)
    with pytest.raises(CorpusError, match="TEST_ONLY"):
        raw_store.load_lock(lock)


def test_raw_evidence_dependencies_are_frozen(tmp_path, raw_store):
    evidence = tmp_path / "card.md"; evidence.write_text("TEST_ONLY source card")
    card = raw_store.register(evidence, {"role": "license_evidence", "source": "TEST_ONLY",
        "source_url": "https://example.invalid/card", "retrieved_at": STAMP, "imported_at": STAMP,
        "acquisition_method": "manual", "test_only": True})
    r = make_receipt(tmp_path, raw_store, "TEST000001", [unique_sentence(1)])
    meta = {k: v for k, v in r.items() if k not in {"receipt_id", "sha256", "byte_size", "blob_path"}}
    meta["license_evidence_receipt_ids"] = [card["receipt_id"]]
    enriched = raw_store.register(raw_store.blob(r["sha256"]), meta)
    lock = raw_store.freeze(tmp_path / "raw.lock.json", [enriched["receipt_id"]])
    assert {x["receipt_id"] for x in lock["receipts"]} == {card["receipt_id"], enriched["receipt_id"]}


@pytest.mark.parametrize("url", ["http://adilet.zan.kz/kaz/docs/K950001000_", "https://evil.invalid/kaz/docs/K950001000_",
                                "https://adilet.zan.kz/kaz/docs/K950001000_/compare", "https://adilet.zan.kz/rus/docs/K950001000_"])
def test_wrong_or_mixed_language_endpoint_rejected(url):
    with pytest.raises(CorpusError):
        adilet_identity(url, require_kazakh=True)
