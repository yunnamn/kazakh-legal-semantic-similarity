"""Negative controls against accidental scientific approval or mutable inputs."""
from __future__ import annotations
import subprocess
import pytest
from kazlegal_corpus.config import load_config
from kazlegal_corpus.errors import CorpusError
from kazlegal_corpus.experiment import make_review_template, verify_experiment
from kazlegal_corpus.io import digest, file_sha, iter_jsonl, read_json, write_json, write_jsonl
from kazlegal_corpus.qa import make_qa_template, validate_qa
from kazlegal_corpus.validate import validate_corpus
from conftest import make_experiment, make_receipt, unique_sentence, STAMP
from test_pipeline import build


@pytest.mark.parametrize('old,new', [
    ('max_candidates_per_unit = 100000', 'max_candidates_per_unit = 0'),
    ('near_jaccard = 0.90', 'near_jaccard = nan'),
    ('minimum_reviewed_documents_per_source = 10', 'minimum_reviewed_documents_per_source = 0'),
    ('allow_reused_text = false', 'allow_reused_text = "false"'),
    ('overlap_words = 32', 'overlap_words = 7'),
    ('schema_version = 1', 'schema_version = 2'),
    ('max_shared_families = 100', 'max_shared_familes = 100'),
    ('seed = "kazlegal-corpus-v1"', 'seed = ""'),
])
def test_invalid_policy_fails_closed(config_path, old, new):
    config_path.write_text(config_path.read_text().replace(old, new))
    with pytest.raises(CorpusError):
        load_config(config_path)


def test_new_tracked_files_in_original_snapshot_require_reaudit(tmp_path, config_path):
    root, lock = make_experiment(tmp_path, config_path, [{'id': 'TEST_ONLY', 'a': unique_sentence(1), 'b': unique_sentence(2)}])
    (root / 'new_config.py').write_text('# TEST_ONLY newly introduced evaluation setting\n')
    subprocess.run(['git', '-C', str(root), 'add', 'new_config.py'], check=True, capture_output=True)
    with pytest.raises(CorpusError, match='file set changed'):
        verify_experiment(root, lock)


def test_review_template_contains_no_approvals(tmp_path, config_path):
    root, lock = make_experiment(tmp_path, config_path, [{'id': 'TEST_ONLY', 'a': unique_sentence(1), 'b': unique_sentence(2)}])
    form = make_review_template(tmp_path / 'audit_TEST_ONLY/repository_inventory.json', config_path, tmp_path / 'blank.json')
    assert form['reviewer'] is None and form['protected_evaluation'] == []
    assert not form['preserve_original_semantic_evaluation']
    assert all(value is None for value in form['reconstructed_design'].values())
    assert all(v['status'] == 'not_reviewed' for v in form['file_reviews'].values())


def reseal_manifest(directory):
    manifest = read_json(directory / 'manifest.json')
    manifest['files'] = {name: file_sha(directory / name) for name in manifest['files']}
    manifest['build_id'] = digest({k: v for k, v in manifest.items() if k != 'build_id'})
    # Direct write is deliberately adversarial; normal outputs cannot be overwritten.
    import json
    (directory / 'manifest.json').write_text(json.dumps(manifest))


def test_independent_validation_does_not_trust_reported_counts(tmp_path, raw_store, config_path):
    make_receipt(tmp_path, raw_store, 'TEST000001', [unique_sentence(1)])
    processed, derived = build(tmp_path, raw_store, config_path)
    stats = read_json(derived / 'statistics.json')
    stats['sentences_by_split']['train'] += 999
    import json
    (derived / 'statistics.json').write_text(json.dumps(stats))
    reseal_manifest(derived)
    with pytest.raises(CorpusError, match='counts differ'):
        validate_corpus(raw_store, processed, derived)


def test_independent_validation_does_not_trust_erased_release_blockers(tmp_path, raw_store, config_path):
    make_receipt(tmp_path, raw_store, 'TEST000001', [unique_sentence(1)])
    processed, derived = build(tmp_path, raw_store, config_path)
    stats = read_json(derived / 'statistics.json')
    stats['release_blockers_before_human_qa'] = []
    import json
    (derived / 'statistics.json').write_text(json.dumps(stats))
    reseal_manifest(derived)
    with pytest.raises(CorpusError, match='Release blockers disagree'):
        validate_corpus(raw_store, processed, derived)


@pytest.mark.parametrize('mutation', ['partial', 'rejected', 'stale', 'unchecked'])
def test_qa_partial_rejected_stale_and_unchecked_responses_block(tmp_path, raw_store, config_path, mutation):
    for i in range(4):
        make_receipt(tmp_path, raw_store, f'TEST{i:06d}', [unique_sentence(i)])
    processed, derived = build(tmp_path, raw_store, config_path)
    path = tmp_path / 'qa-template.jsonl'
    make_qa_template(processed, derived, path, count_per_source=10)
    rows = list(iter_jsonl(path))
    for row in rows:
        row.update({'decision': 'accept', 'reviewer': 'TEST_ONLY fixture, not actual human QA',
                    'reviewed_at': STAMP, 'evidence_and_notes': 'TEST_ONLY verification fixture',
                    'authentic_source_verified': True, 'language_ok': True,
                    'structure_and_boundaries_ok': True, 'normalization_and_notes_ok': True})
    if mutation == 'partial':
        rows.pop()
    elif mutation == 'rejected':
        rows[0]['decision'] = 'reject'
    elif mutation == 'stale':
        rows[0]['derived_build_id'] = 'TEST_ONLY wrong snapshot'
    else:
        rows[0]['normalization_and_notes_ok'] = None
    answers = tmp_path / 'qa-responses.jsonl'
    write_jsonl(answers, rows)
    with pytest.raises(CorpusError):
        validate_qa(derived, answers, count_per_source=10)
