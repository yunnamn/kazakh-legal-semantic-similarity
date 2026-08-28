# Data

This project builds a weakly filtered Kazakh legal-domain candidate corpus from Kazakh C4 using deterministic normalization, legal-language heuristics, conservative near-exact deduplication, and leakage-controlled splits.

Generated C4-derived corpus files are intentionally excluded from git. Reproduce them with:

```bash
python scripts/build_corpus.py
```

Manual semantic-similarity annotations belong under `data/annotations/`. Candidate pair generation leaves `similarity_score` blank; those scores must be filled only by human annotators using the 0-5 scale.

