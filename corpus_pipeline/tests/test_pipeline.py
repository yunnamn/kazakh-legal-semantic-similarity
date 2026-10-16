"""Pipeline regressions use marked nonlegal fixtures, never publishable corpus text."""
from __future__ import annotations
import json
import pytest
from kazlegal_corpus.config import SPLITS
from kazlegal_corpus.errors import CorpusError
from kazlegal_corpus.experiment import verify_experiment
from kazlegal_corpus.export import export_training_view
from kazlegal_corpus.io import digest, file_sha, iter_jsonl, read_json, write_json, write_jsonl
from kazlegal_corpus.process import build_processed
from kazlegal_corpus.qa import make_qa_template, validate_qa
from kazlegal_corpus.split import build_splits
from kazlegal_corpus.validate import validate_corpus
from conftest import STAMP, make_experiment, make_receipt, unique_sentence


def build(tmp_path, raw_store, config_path, *, stem="release", experiment=None, prior=None):
    raw_lock = tmp_path / (stem + ".raw.lock.json")
    raw_store.freeze(raw_lock)
    processed = tmp_path / (stem + ".processed")
    derived = tmp_path / (stem + ".derived")
    build_processed(raw_store, raw_lock, config_path, processed, test_mode=True)
    root, lock = experiment if experiment else (None, None)
    build_splits(processed, derived, experiment_lock=lock, repository_root=root, prior_lock=prior)
    return processed, derived


def test_duplicate_harvest_keeps_all_provenance_and_repeated_provisions(tmp_path, raw_store, config_path):
    para = unique_sentence(1)
    paragraphs = ["1-\u0431\u0430\u043f", para, "2-\u0431\u0430\u043f", para]
    make_receipt(tmp_path, raw_store, "TEST000001", paragraphs)
    make_receipt(tmp_path, raw_store, "TEST000001", paragraphs, wrapper="<nav>TEST_ONLY navigation</nav>", timestamp="2026-09-07T01:00:00Z")
    processed, derived = build(tmp_path, raw_store, config_path)
    docs = list(iter_jsonl(processed / "documents.jsonl"))
    prose = [s for s in iter_jsonl(processed / "sentences.jsonl") if s["kind"] == "paragraph"]
    assert len(docs) == 1 and len(docs[0]["provenance"]) == 2
    assert len(prose) == 2 and prose[0]["sentence_id"] != prose[1]["sentence_id"]
    assert {p["article"] for p in prose} == {"1", "2"}
    assert read_json(processed / "statistics.json")["duplicate_harvest_units_merged_with_provenance"] == 1
    report = validate_corpus(raw_store, processed, derived)
    assert report["structural_checks"] == "passed"
    assert "test_only_data_never_exportable_for_research" in report["release_blockers_before_human_qa"]


def test_identical_frozen_inputs_reproduce_bytes(tmp_path, raw_store, config_path):
    for i in range(12):
        make_receipt(tmp_path, raw_store, f"TEST{i:06d}", [unique_sentence(i)])
    p1, d1 = build(tmp_path, raw_store, config_path, stem="one")
    p2, d2 = build(tmp_path, raw_store, config_path, stem="two")
    assert read_json(p1 / "manifest.json") == read_json(p2 / "manifest.json")
    assert read_json(d1 / "manifest.json") == read_json(d2 / "manifest.json")
    assert file_sha(d1 / "split.lock.json") == file_sha(d2 / "split.lock.json")


def test_versions_of_a_law_never_cross_splits(tmp_path, raw_store, config_path):
    make_receipt(tmp_path, raw_store, "TEST000001", [unique_sentence(1)], version="TEST_ONLY-version-a")
    make_receipt(tmp_path, raw_store, "TEST000001", [unique_sentence(999)], version="TEST_ONLY-version-b")
    processed, derived = build(tmp_path, raw_store, config_path)
    assert len(list(iter_jsonl(processed / "documents.jsonl"))) == 2
    roles = {r["split"] for r in iter_jsonl(derived / "memberships.jsonl")}
    assert len(roles) == 1


def test_near_duplicate_numeric_differences_are_retained_but_colocated(tmp_path, raw_store, config_path):
    base = "TEST_ONLY " + " ".join(f"token{i}" for i in range(60))
    make_receipt(tmp_path, raw_store, "TEST000001", [base + " 12."])
    make_receipt(tmp_path, raw_store, "TEST000002", [base + " 13."])
    processed, derived = build(tmp_path, raw_store, config_path)
    sentences = list(iter_jsonl(processed / "sentences.jsonl"))
    assert len(sentences) == 2 and len({s["text"] for s in sentences}) == 2
    memberships = list(iter_jsonl(derived / "memberships.jsonl"))
    assert len({s["split"] for s in memberships}) == 1
    assert len({s["component_id"] for s in memberships}) == 1
    assert read_json(derived / "statistics.json")["leakage_edges_by_relation"]["near_word_shingle_jaccard"] >= 1
    validate_corpus(raw_store, processed, derived)


def test_short_shared_text_is_retained_in_processed_not_training(tmp_path, raw_store, config_path):
    for i in range(3):
        make_receipt(tmp_path, raw_store, f"TEST{i:06d}", ["TEST_ONLY shared.", unique_sentence(i)])
    processed, derived = build(tmp_path, raw_store, config_path)
    shared = [r for r in iter_jsonl(processed / "sentences.jsonl") if r["text"] == "TEST_ONLY shared."]
    assert len(shared) == 3
    excluded = [r for r in iter_jsonl(derived / "excluded.jsonl") if r["text"] == "TEST_ONLY shared."]
    assert len(excluded) == 3
    assert all("shared_low_information_text" in r["quarantine_reasons"] for r in excluded)
    validate_corpus(raw_store, processed, derived)


def test_evaluation_both_endpoints_and_whole_laws_protected(tmp_path, raw_store, config_path):
    protected_a, protected_b = unique_sentence(1), unique_sentence(2)
    make_receipt(tmp_path, raw_store, "TEST000001", [protected_a, unique_sentence(101)])
    make_receipt(tmp_path, raw_store, "TEST000002", [protected_b, unique_sentence(102)])
    make_receipt(tmp_path, raw_store, "TEST000003", [unique_sentence(3)])
    experiment = make_experiment(tmp_path, config_path, [{"id": "pair1", "a": protected_a, "b": protected_b}])
    before = file_sha(experiment[0] / "pairs.csv")
    processed, derived = build(tmp_path, raw_store, config_path, experiment=experiment)
    for r in iter_jsonl(derived / "memberships.jsonl"):
        if r["family_id"] in {"adilet:TEST000001", "adilet:TEST000002"}:
            assert r["split"] == "quarantine"
            assert "external_semantic_evaluation_overlap" in r["reasons"]
    assert file_sha(experiment[0] / "pairs.csv") == before
    assert validate_corpus(raw_store, processed, derived, repository_root=experiment[0])["original_experiment_verified"]


def test_substring_guard_and_cross_paragraph_window(tmp_path, raw_store, config_path):
    tokens = [f"word{i}" for i in range(80)]
    paragraph1 = "TEST_ONLY " + " ".join(tokens[:40]) + "."
    paragraph2 = "TEST_ONLY " + " ".join(tokens[40:]) + "."
    make_receipt(tmp_path, raw_store, "TEST000001", [paragraph1, paragraph2])
    # Endpoint crosses two paragraphs and is not an exact/full-sentence match.
    gold = " ".join(tokens[25:40]) + " TEST_ONLY " + " ".join(tokens[40:65])
    experiment = make_experiment(tmp_path, config_path, [{"id": "pair1", "a": gold, "b": unique_sentence(999)}])
    processed, derived = build(tmp_path, raw_store, config_path, experiment=experiment)
    assert all(r["split"] == "quarantine" for r in iter_jsonl(derived / "memberships.jsonl"))
    assert read_json(derived / "statistics.json")["leakage_edges_by_relation"]["contiguous_word_overlap"] > 0


def test_explicit_evaluation_family_protects_nonmatching_version(tmp_path, raw_store, config_path):
    make_receipt(tmp_path, raw_store, "TEST000001", [unique_sentence(1)])
    experiment = make_experiment(tmp_path, config_path, [{"id": "pair1", "a": unique_sentence(101), "b": unique_sentence(102),
                                                         "family_a": "adilet:TEST000001"}])
    processed, derived = build(tmp_path, raw_store, config_path, experiment=experiment)
    assert next(iter_jsonl(derived / "memberships.jsonl"))["split"] == "quarantine"


def test_frozen_evaluation_labels_cannot_change(tmp_path, raw_store, config_path):
    experiment = make_experiment(tmp_path, config_path, [{"id": "pair1", "a": unique_sentence(1), "b": unique_sentence(2)}])
    path = experiment[0] / "pairs.csv"
    path.write_text(path.read_text().replace(",1,", ",2,"))
    with pytest.raises(CorpusError, match="changed"):
        verify_experiment(experiment[0], experiment[1])


def test_prior_conflicting_folds_quarantine_instead_of_moving_holdout(tmp_path, raw_store, config_path):
    common = unique_sentence(100, length=60)
    for i in (1, 2):
        make_receipt(tmp_path, raw_store, f"TEST{i:06d}", [common])
    prior = {"seed": "kazlegal-corpus-v1", "weights": {"train": 8000, "validation": 1000, "mlm_test": 500, "annotation_pool": 500},
             "assignments": [{"family_id": "adilet:TEST000001", "split": "train"},
                             {"family_id": "adilet:TEST000002", "split": "mlm_test"}]}
    prior["lock_id"] = digest(prior)
    path = tmp_path / "prior_TEST_ONLY.json"; write_json(path, prior)
    processed, derived = build(tmp_path, raw_store, config_path, prior=path)
    assert all("prior_split_conflict_after_component_merge" in r["reasons"] for r in iter_jsonl(derived / "memberships.jsonl"))


def test_all_four_roles_disjoint_on_fixture_cohort(tmp_path, raw_store, config_path):
    for i in range(160):
        make_receipt(tmp_path, raw_store, f"TEST{i:06d}", [unique_sentence(i)])
    processed, derived = build(tmp_path, raw_store, config_path)
    report = validate_corpus(raw_store, processed, derived)
    assert all(report["sentences_by_split"][s] > 0 for s in SPLITS)
    ids = [{r["sentence_id"] for r in iter_jsonl(derived / "splits" / (s + ".jsonl"))} for s in SPLITS]
    assert sum(map(len, ids)) == len(set.union(*ids)) == 160


def test_research_export_blocks_fixtures_and_unreviewed_design(tmp_path, raw_store, config_path):
    make_receipt(tmp_path, raw_store, "TEST000001", [unique_sentence(1)])
    processed, derived = build(tmp_path, raw_store, config_path)
    with pytest.raises(CorpusError, match="Research export blocked"):
        export_training_view(raw_store, processed, derived, tmp_path / "should_not_exist", repository_root=tmp_path,
                             qa_review=tmp_path / "not_completed.jsonl")
    assert not (tmp_path / "should_not_exist").exists()


def test_qa_templates_are_blank_not_generated_annotation(tmp_path, raw_store, config_path):
    for i in range(4):
        make_receipt(tmp_path, raw_store, f"TEST{i:06d}", [unique_sentence(i)])
    processed, derived = build(tmp_path, raw_store, config_path)
    template = tmp_path / "qa_TEST_ONLY.jsonl"
    assert make_qa_template(processed, derived, template, count_per_source=2) == 2
    rows = list(iter_jsonl(template))
    assert all(r["decision"] is None and r["reviewer"] is None for r in rows)
    with pytest.raises(CorpusError, match="not accepted"):
        validate_qa(derived, template, count_per_source=2)


def test_immutable_build_refuses_overwrite(tmp_path, raw_store, config_path):
    make_receipt(tmp_path, raw_store, "TEST000001", [unique_sentence(1)])
    processed, derived = build(tmp_path, raw_store, config_path)
    with pytest.raises(CorpusError, match="exists"):
        build_splits(processed, derived)
