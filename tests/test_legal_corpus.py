"""Synthetic export-contract fixtures live only in tmp_path, never research data."""
from __future__ import annotations

import json

import pytest

from src.annotation import generate_annotation_candidates
from src.corpus import SPLITS, build_corpus_from_c4, load_corpus, load_split, make_splits


def mock_export(root, *, change=None, manifest_change=None, validation_change=None):
    """Mock the exporter boundary, not a real acquisition, review or release."""
    from kazlegal_corpus.io import digest, file_sha, write_json, write_jsonl

    root.mkdir()
    for role in SPLITS:
        rows = [
            {"sentence_id": f"{role}-{i}", "text": f"Сот заң туралы {role} қаулы шығарды {i}.",
             "split": role, "language": "kk", "test_only": False, "quarantine_reasons": [],
             "family_id": f"adilet:mock-{role}-{i}", "component_id": f"mock-{role}-{i}",
             "provenance": [{"receipt_id": "mock-only-not-a-real-receipt"}]}
            for i in range(24 if role == "annotation_pool" else 2)
        ]
        if change:
            change(role, rows)
        write_jsonl(root / f"{role}.jsonl", rows)
        write_jsonl(root / f"{role}.provenance.jsonl", [
            {"export_line": n, **{k: v for k, v in row.items() if k != "text"}}
            for n, row in enumerate(rows, 1)
        ])
    validation = {"training_view_ready": True, "structural_checks": "passed",
                  "independent_overlap_checks": "passed", "original_experiment_verified": True,
                  "release_blockers_before_human_qa": [], "derived_build_id": "mock-derived",
                  "human_qa": {"reviewed_source_document_samples": 1}}
    validation.update(validation_change or {})
    write_json(root / "validation.json", validation)
    write_json(root / "attributions_and_rights.json", [])
    manifest = {"schema_version": 1, "stage": "training_view_not_new_similarity_evaluation",
                "format": "jsonl", "derived_build_id": "mock-derived", "experiment_id": "mock-experiment",
                "qa_review_sha256": "mock-qa", "roles": {role: role for role in SPLITS},
                "files": {p.name: file_sha(p) for p in root.iterdir()}}
    manifest.update(manifest_change or {})
    manifest["build_id"] = digest(manifest)
    write_json(root / "manifest.json", manifest)
    return {"corpus_input": {"kind": "training_view", "directory": str(root)}}


def test_export_integrates_with_annotation_sampling_and_preserves_ids(tmp_path):
    config = mock_export(tmp_path / "mock-export")
    config.update(seed=42, annotation={"candidate_count": 8},
                  paths={"annotation_candidates": str(tmp_path / "candidates.csv")})
    pool = load_split("annotation_pool", config)
    assert pool.iloc[0]["sentence_id"] == "annotation_pool-0"
    assert pool.iloc[0]["provenance"] == [{"receipt_id": "mock-only-not-a-real-receipt"}]
    assert pool.attrs["experiment_id"] == "mock-experiment"
    candidates = generate_annotation_candidates(config)
    assert len(candidates) == 8
    assert candidates["similarity_score"].isna().all()
    assert set(candidates["sentence_1_id"]) <= set(pool["sentence_id"])
    assert set(candidates["sentence_2_id"]) <= set(pool["sentence_id"])
    assert set(load_split("train", config)["sentence_id"]) == {"train-0", "train-1"}


def test_modified_export_is_rejected(tmp_path):
    from kazlegal_corpus.errors import CorpusError

    root = tmp_path / "mock-export"
    config = mock_export(root)
    with (root / "train.jsonl").open("a") as handle:
        handle.write('{}\n')
    with pytest.raises(CorpusError, match="modified"):
        load_split("train", config)


@pytest.mark.parametrize("override", [
    {"training_view_ready": False}, {"original_experiment_verified": False},
    {"independent_overlap_checks": "not_run"}, {"human_qa": {}},
    {"release_blockers_before_human_qa": ["unreviewed"]},
])
def test_unapproved_exports_are_rejected(tmp_path, override):
    config = mock_export(tmp_path / "mock-export", validation_change=override)
    with pytest.raises(ValueError, match="validation"):
        load_split("train", config)


@pytest.mark.parametrize("override", [{"stage": "derived_splits"}, {"format": "text"}, {"files": {}}])
def test_intermediate_or_incomplete_export_is_rejected(tmp_path, override):
    config = mock_export(tmp_path / "mock-export", manifest_change=override)
    with pytest.raises(ValueError):
        load_split("train", config)


@pytest.mark.parametrize("field,value", [
    ("family_id", "adilet:mock-train-0"), ("component_id", "mock-train-0"),
    ("sentence_id", "train-0"), ("text", "Сот заң туралы train қаулы шығарды 0."),
    ("test_only", True), ("text", "TEST_ONLY fixture"),
    ("quarantine_reasons", ["unreviewed"]), ("split", "train"),
])
def test_leakage_and_nonresearch_records_are_rejected_even_in_other_roles(tmp_path, field, value):
    def change(role, rows):
        if role == "validation":
            rows[0][field] = value
    config = mock_export(tmp_path / "mock-export", change=change)
    with pytest.raises(ValueError):
        load_split("train", config)


def test_c4_path_is_preserved_and_export_config_cannot_build_c4(tmp_path):
    path = tmp_path / "train.jsonl"
    path.write_text(json.dumps({"sentence_id": "old", "text": "existing C4 input"}) + '\n')
    assert load_split("train", {"paths": {"train_jsonl": str(path)}}).iloc[0]["sentence_id"] == "old"
    with pytest.raises(ValueError, match="corpus_pipeline"):
        build_corpus_from_c4({"corpus_input": {"kind": "training_view"}})
    with pytest.raises(ValueError, match="load_split"):
        load_corpus({"corpus_input": {"kind": "training_view"}})
    with pytest.raises(ValueError, match="resplit"):
        make_splits(None, {"corpus_input": {"kind": "training_view"}})
    with pytest.raises(ValueError, match="Unknown corpus input"):
        load_split("train", {"corpus_input": {"kind": "misspelled"}})


def test_new_annotation_outputs_do_not_overwrite_original_benchmark(tmp_path, monkeypatch):
    import pandas as pd
    from src.annotation import annotate_pairs_cli

    original = tmp_path / "original"
    original.mkdir()
    benchmark = original / "annotations_reviewer.csv"
    benchmark.write_text("original human benchmark, preserve verbatim\n")
    candidates = tmp_path / "candidates.csv"
    pd.DataFrame([{"pair_id": "pair-0001", "sentence_1": "сот", "sentence_2": "заң",
                   "sampling_strategy": "random_pair", "similarity_score": float("nan")}]).to_csv(candidates, index=False)
    config = {"paths": {"annotations_dir": str(original), "annotation_output_dir": str(tmp_path / "new"),
                        "annotation_candidates": str(candidates)}}
    monkeypatch.setattr("builtins.input", lambda _: "q")
    annotate_pairs_cli("reviewer", config)
    assert benchmark.read_text() == "original human benchmark, preserve verbatim\n"
    assert (tmp_path / "new" / "annotations_reviewer.csv").is_file()
