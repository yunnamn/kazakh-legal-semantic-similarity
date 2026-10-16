import random
import sqlite3
import pytest
from kazlegal_corpus.errors import CorpusError
from kazlegal_corpus.mlm import aggregate_masked_losses, fixed_mlm_mask
from kazlegal_corpus.overlap import SimilarityIndex, SpanIndex, shingles


def test_exact_prefix_join_matches_bruteforce():
    rng = random.Random(111)
    base = [f"token{i}" for i in range(70)]
    texts = []
    for i in range(35):
        tokens = list(base)
        for index in rng.sample(range(len(tokens)), k=i % 7):
            tokens[index] = f"variant{i}_{index}"
        texts.append("TEST_ONLY " + " ".join(tokens))
    db = sqlite3.connect(":memory:")
    index = SimilarityIndex(db, threshold=0.9, width=5, min_words=12, max_candidates=10000)
    detected = set()
    for i, text in enumerate(texts):
        for match in index.add(str(i), str(i), text):
            detected.add((int(match["other_node"]), i))
    expected = set()
    sets = [shingles(t, 5) for t in texts]
    for i in range(len(texts)):
        for j in range(i):
            intersection = len(sets[i] & sets[j]); union = len(sets[i] | sets[j])
            if intersection * 10 >= union * 9:
                expected.add((j, i))
    assert detected == expected


def test_budget_exhaustion_is_failure_not_silent_lsh_miss():
    db = sqlite3.connect(":memory:")
    index = SimilarityIndex(db, threshold=0.9, width=5, min_words=12, max_candidates=0)
    base = "TEST_ONLY " + " ".join(f"token{i}" for i in range(100))
    index.add("a", "a", base + " first")
    with pytest.raises(CorpusError, match="budget"):
        index.add("b", "b", base + " second")


def test_substring_windows_have_stride_one():
    db = sqlite3.connect(":memory:")
    spans = SpanIndex(db, width=8, max_candidates=100)
    tokens = [f"t{i}" for i in range(40)]
    spans.add("a", "family_a", " ".join(tokens))
    assert spans.add("b", "family_b", " ".join(tokens[3:16]))[0]["other_node"] == "family_a"


def test_mlm_is_order_independent_and_never_masks_special_or_padding():
    kwargs = dict(seed="TEST_ONLY", mask_token_id=99, vocabulary_size=120,
                  special_token_ids=[0, 1, 2, 99], probability=1)
    args = ([1, 10, 11, 2, 0], [1, 1, 1, 1, 0], [1, 0, 0, 1, 1])
    first = fixed_mlm_mask(*args, example_id="a", **kwargs)
    fixed_mlm_mask(*args, example_id="b", **kwargs)
    again = fixed_mlm_mask(*args, example_id="a", **kwargs)
    assert first == again
    assert first["labels"] == [-100, 10, 11, -100, -100]
    assert first["input_ids"][0] == 1 and first["input_ids"][-1] == 0


def test_mlm_aggregate_is_token_weighted():
    report = aggregate_masked_losses([(4.0, 2), (6.0, 1), (0, 0)])
    assert report["masked_tokens"] == 3
    assert report["masked_token_cross_entropy"] == pytest.approx(10 / 3)


def test_mlm_no_masked_tokens_is_not_false_perfect_loss():
    with pytest.raises(CorpusError, match="No masked"):
        aggregate_masked_losses([(0, 0)])


@pytest.mark.parametrize("probability", [0, -0.1, 1.1])
def test_mlm_invalid_probability(probability):
    with pytest.raises(CorpusError):
        fixed_mlm_mask([1], [1], [0], example_id="a", seed="x", mask_token_id=2,
                       vocabulary_size=5, special_token_ids=[2], probability=probability)
