"""Optional evaluation helpers, not a replacement for an uninspected model pipeline."""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Iterable, Sequence

from .errors import CorpusError
from .io import digest


def _number(seed: str, example_id: str, position: int, purpose: str) -> int:
    return int(digest([seed, example_id, position, purpose]), 16)


@lru_cache(maxsize=4)
def _replacement_vocabulary(vocabulary_size: int, special_ids: tuple[int, ...]) -> tuple[int, ...]:
    special = set(special_ids)
    return tuple(i for i in range(vocabulary_size) if i not in special)


def fixed_mlm_mask(input_ids: Sequence[int], attention_mask: Sequence[int], special_tokens_mask: Sequence[int], *,
                   example_id: str, seed: str, mask_token_id: int, vocabulary_size: int,
                   special_token_ids: Sequence[int], probability: float = 0.15,
                   ensure_one: bool = False) -> dict[str, list[int]]:
    """Batch-order-independent masking; do not use an MLM test set for model selection.

    No corpus text is generated. These are model input corruptions plus ORIGINAL
    token labels. For parity, different checkpoints of one tokenizer must reuse
    the exact same feature/tokenizer/mask manifest. Across tokenizers use the
    same held-out documents, but do not directly compare incompatible token NLLs.
    """
    if not 0 < probability <= 1:
        raise CorpusError("Mask probability must be in (0,1]")
    if not len(input_ids) == len(attention_mask) == len(special_tokens_mask):
        raise CorpusError("Token, attention and special-mask lengths differ")
    if not 0 <= mask_token_id < vocabulary_size or any(not 0 <= t < vocabulary_size for t in input_ids):
        raise CorpusError("Token IDs outside vocabulary")
    special = set(special_token_ids)
    eligible = [i for i, token in enumerate(input_ids) if attention_mask[i] and not special_tokens_mask[i] and token not in special]
    selected = [i for i in eligible if _number(seed, example_id, i, "select") < int(probability * 2**256)]
    if ensure_one and eligible and not selected:
        selected = [min(eligible, key=lambda i: _number(seed, example_id, i, "fallback"))]
    replacements = _replacement_vocabulary(vocabulary_size, tuple(sorted(special)))
    if selected and not replacements:
        raise CorpusError("No nonspecial vocabulary for random replacements")
    masked = list(input_ids)
    labels = [-100] * len(masked)
    for i in selected:
        labels[i] = input_ids[i]
        action = _number(seed, example_id, i, "action") % 10
        if action < 8:
            masked[i] = mask_token_id
        elif action == 8:
            masked[i] = replacements[_number(seed, example_id, i, "random_token") % len(replacements)]
    return {"input_ids": masked, "attention_mask": list(attention_mask), "labels": labels}


def aggregate_masked_losses(batches: Iterable[tuple[float, int]]) -> dict:
    """Each pair is (SUM of token negative log likelihoods, NUMBER of masked tokens)."""
    loss_sum = 0.0
    tokens = 0
    for summed_nll, count in batches:
        if count < 0 or not math.isfinite(summed_nll) or summed_nll < 0:
            raise CorpusError("Invalid masked-token loss contribution")
        if count == 0 and summed_nll != 0:
            raise CorpusError("A zero-token batch cannot contribute loss")
        loss_sum += summed_nll
        tokens += count
    if tokens == 0:
        raise CorpusError("No masked tokens were evaluated")
    average = loss_sum / tokens
    return {"masked_token_cross_entropy": average, "masked_tokens": tokens,
            "exp_masked_token_cross_entropy_not_autoregressive_perplexity": math.exp(average) if average < 709 else None}
