"""All content constructed by these tests is TEST_ONLY, not authentic corpus text."""
from __future__ import annotations
import csv
import io
import subprocess
from pathlib import Path
import pytest
from kazlegal_corpus.audit import audit_repository
from kazlegal_corpus.config import load_config
from kazlegal_corpus.experiment import REQUIRED_DESIGN, freeze_experiment
from kazlegal_corpus.io import digest, file_sha, read_json, write_json
from kazlegal_corpus.raw import RawStore

STAMP = "2026-09-07T00:00:00Z"


def fixture_review(source="adilet"):
    return {"source": source, "research_use_approved": True, "license": "TEST_ONLY_NOT_A_DATA_LICENSE",
            "license_url": "https://example.invalid/TEST_ONLY", "attribution": "TEST_ONLY fixture",
            "reviewer": "TEST_ONLY unit test", "reviewed_at": STAMP,
            "access_basis": "TEST_ONLY mocked acquisition", "authenticity_assessment": "TEST_ONLY fixture",
            "redistribution": "not_permitted"}


def make_receipt(tmp_path: Path, store: RawStore, document_id: str, paragraphs: list[str], *,
                 version=None, wrapper="", timestamp=STAMP):
    assert all("TEST_ONLY" in text or text.endswith("-\u0431\u0430\u043f") for text in paragraphs)
    text = "<html><h1>TEST_ONLY title</h1>" + wrapper + '<div id="text">' + "".join(f"<p>{t}</p>" for t in paragraphs) + "</div></html>"
    path = tmp_path / (digest([document_id, paragraphs, version, wrapper, timestamp]) + ".html")
    path.write_text(text, encoding="utf-8")
    return store.register(path, {
        "source": "adilet", "adapter": "adilet_html", "format": "html", "test_only": True,
        "source_document_id": document_id, "source_url": f"https://adilet.zan.kz/kaz/docs/{document_id}",
        "canonical_url": f"https://adilet.zan.kz/kaz/docs/{document_id}", "language": "kk",
        "source_version": version, "retrieved_at": timestamp, "imported_at": timestamp,
        "acquisition_method": "manual", "acquisition_note": "TEST_ONLY constructed HTML wrapper, not a source snapshot",
        "source_review": fixture_review(),
    })


def unique_sentence(family: int, index: int = 0, length: int = 20) -> str:
    return "TEST_ONLY " + " ".join(f"unit{family}part{index}word{j}" for j in range(length)) + "."


@pytest.fixture
def config_path(tmp_path):
    original = Path(__file__).parents[1] / "configs" / "pipeline.toml"
    path = tmp_path / "config.toml"
    path.write_text(original.read_text(), encoding="utf-8")
    return path


@pytest.fixture
def raw_store(tmp_path):
    return RawStore(tmp_path / "raw")


def make_experiment(tmp_path: Path, config_path: Path, pairs: list[dict]):
    root = tmp_path / "original_repository_TEST_ONLY"
    root.mkdir()
    with (root / "pairs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "a", "b", "score", "family_a", "family_b"])
        writer.writeheader()
        for pair in pairs:
            writer.writerow({"family_a": "", "family_b": "", "score": "1", **pair})
    (root / "README.md").write_text("TEST_ONLY minimal repository, not the user's repository.\n")
    (root / "evaluate.py").write_text("# TEST_ONLY original evaluation, never executed\nMETRIC = 'spearman'\n")
    for args in (("init", "-q"), ("config", "user.email", "test@example.invalid"),
                 ("config", "user.name", "TEST_ONLY"), ("add", "."), ("commit", "-qm", "TEST_ONLY initial")):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    audit_dir = tmp_path / "audit_TEST_ONLY"
    inventory = audit_repository(root, audit_dir)
    review = {
        "audit_inventory_sha256": file_sha(audit_dir / "repository_inventory.json"),
        "reviewer": "TEST_ONLY automatic fixture, not a human review", "reviewed_at": STAMP,
        "preserve_original_semantic_evaluation": True,
        "accepted_corpus_config_sha256": digest(load_config(config_path)),
        "reconstructed_design": {key: "TEST_ONLY unchanged fixture design" for key in REQUIRED_DESIGN},
        "file_reviews": {f["path"]: {"status": "reviewed", "note": "TEST_ONLY fixture"} for f in inventory["files"]},
        "protected_evaluation": [{"path": "pairs.csv", "format": "csv", "role": "semantic_test", "id_field": "id",
                                  "text_fields": ["a", "b"], "family_fields": ["family_a", "family_b"]}],
    }
    review_path = tmp_path / "experiment-review_TEST_ONLY.json"
    write_json(review_path, review)
    lock_path = tmp_path / "experiment_TEST_ONLY.lock.json"
    freeze_experiment(root, audit_dir / "repository_inventory.json", review_path, config_path, lock_path)
    return root, lock_path
