# Project Explanation

## Core Concepts

Semantic textual similarity asks how close two texts are in meaning. In this project, Kazakh legal sentence pairs are scored by humans on a 0-5 scale, and systems are evaluated by how well their numeric similarity scores correlate with those human judgments.

Low-resource NLP studies languages with fewer datasets, benchmarks, tools, and pretrained resources. Kazakh has fewer widely used NLP benchmarks than English, and legal-domain Kazakh is still more specialized.

Kazakh-specific challenges include morphology, Cyrillic and Kazakh-specific characters, domain vocabulary, code-switching or borrowed legal terminology, and fewer curated evaluation datasets.

Domain adaptation means taking a general pretrained model and exposing it to text from a target domain. Here, the target domain is weakly filtered Kazakh legal text.

Masked-language modeling trains a model to predict hidden tokens from surrounding context. DAPT continues MLM training on the domain corpus.

Pretraining is broad initial training on large text. DAPT is continued pretraining on a narrower domain. Downstream fine-tuning would train for a task such as semantic similarity using labeled pairs; this repository does not invent labels for that.

mBERT is a multilingual BERT model trained across many languages. XLM-R is a multilingual RoBERTa-style model trained on large multilingual data. Kaz-RoBERTa is a Kazakh-oriented RoBERTa model. LaBSE is a sentence-embedding model designed for language-agnostic sentence representations and is used through SentenceTransformers.

Mean pooling converts token representations into a sentence vector by averaging final hidden states. This project uses attention-mask-aware pooling so padding tokens do not affect the sentence vector.

L2 normalization scales a vector to unit length. After normalization, cosine similarity can be computed as a dot product.

Cosine similarity measures the angle between vectors. Higher cosine means two sentence embeddings point in a more similar direction.

Spearman correlation measures rank agreement. It is useful when exact numeric spacing matters less than whether a system orders pairs similarly to humans.

Pearson correlation measures linear association. It is useful when system scores and human scores should move together numerically.

Bootstrap confidence intervals resample the evaluated pairs to estimate uncertainty, which is important for a small benchmark.

Deterministic masked evaluation uses fixed masks derived from seed, model key, and sentence id. This ensures the base and DAPT variants of the same model family are evaluated on identical masked tokens.

The annotation pool is excluded from DAPT so that future human benchmark sentences are held out from adaptation. This protects the semantic-similarity evaluation from avoidable leakage.

The old pseudo-label experiment was circular because model-generated similarity labels were treated as gold labels and then used to evaluate systems. This repository rejects pseudo-label columns and evaluates semantic similarity only against human annotations.

Loading fresh base models after DAPT was wrong because it erased the adaptation. This repository has explicit `base` and `dapt` checkpoint resolution and raises an error when a requested DAPT checkpoint is missing.

MLM loss is mainly compared within model families because different tokenizers split text differently and produce different prediction spaces.

Lexical baselines matter because legal sentences may share words for shallow reasons. TF-IDF cosine and token Jaccard show how far simple surface overlap can go.

Project limitations include heuristic filtering, noisy web-derived corpus text, limited Kazakh NLP resources, likely small human annotation data, possible single-annotator bias, compute constraints, and the fact that generic MLM encoders are not optimized sentence encoders.

Pretrained libraries provide tokenizers, model architectures, checkpoint loading, MLM training utilities, SentenceTransformers encoding, TF-IDF vectorization, nearest-neighbor search, and statistical correlation functions.

What I personally implemented in this project: corpus filtering and deduplication, deterministic splitting, split leakage checks, explicit base/DAPT checkpoint handling, DAPT training orchestration, deterministic MLM evaluation masks, transformer mean-pooling embeddings, LaBSE integration, annotation candidate generation with blank labels, CLI annotation support, lexical baselines, correlation and bootstrap evaluation, smoke tests, and regression tests against pseudo-label and checkpoint fallback errors.

# Graduate Interview Questions

1. What is semantic textual similarity?
   It is the task of estimating how close two texts are in meaning, usually with a continuous or ordinal score.

2. Why use a 0-5 human scale?
   It gives annotators a graded way to distinguish unrelated, partially related, and equivalent sentence pairs.

3. Why is Kazakh considered lower-resource in NLP?
   It has fewer large curated datasets, benchmarks, and domain-specific tools than high-resource languages such as English.

4. Why focus on legal text?
   Legal language has specialized vocabulary and phrasing that general pretrained models may not represent well.

5. What is DAPT?
   Domain-adaptive pretraining is continued pretraining on unlabeled text from a target domain.

6. What is MLM?
   Masked-language modeling hides tokens and trains the model to predict them from context.

7. Why use MLM for DAPT?
   It can adapt a pretrained encoder to legal-domain language without requiring labeled semantic pairs.

8. Which split is used for DAPT optimization?
   Only the `train` split.

9. Which split selects checkpoints?
   The `validation` split.

10. Which split is used for final MLM evaluation?
    The `mlm_test` split.

11. Why keep `annotation_pool` separate?
    It reserves sentences for human STS evaluation and prevents adaptation leakage.

12. What makes the corpus weakly filtered?
    It is selected by heuristics from C4, not verified by legal experts.

13. What is conservative near-exact deduplication?
    It removes trivial variants while avoiding semantic paraphrase detection.

14. Why was the "Шарты" case important?
    It showed that ambiguous terms can appear in non-legal contexts and need stricter filtering.

15. Why not generate labels with model cosine scores?
    That would make evaluation circular because model outputs would become the supposed ground truth.

16. How does checkpoint resolution work?
    `resolve_checkpoint(model_key, variant)` returns either the base id or an existing DAPT path.

17. What happens if a DAPT checkpoint is missing?
    The code raises `FileNotFoundError` and does not load the base model.

18. Why is silent fallback dangerous?
    It can make a run appear adapted when it actually used the original base checkpoint.

19. Why deterministic evaluation masks?
    They ensure base and DAPT variants in one family predict the same masked tokens.

20. Why dynamic masks for training?
    Dynamic masking exposes the model to varied MLM examples during DAPT.

21. Why compare MLM loss mainly within a model family?
    Tokenizers and vocabularies differ across families, so raw loss is not directly comparable.

22. What is mean pooling?
    It averages token embeddings into one sentence vector.

23. Why use attention masks in pooling?
    Padding tokens should not influence the sentence representation.

24. Why apply L2 normalization?
    It makes cosine similarity stable and comparable across vectors.

25. Why use LaBSE differently?
    LaBSE is a SentenceTransformer model with a native sentence-embedding architecture.

26. What are the lexical baselines?
    TF-IDF cosine similarity and token Jaccard similarity.

27. Why include lexical baselines?
    They show whether transformer embeddings beat simple word-overlap signals.

28. What does Spearman correlation evaluate?
    Whether the system ranks sentence pairs similarly to human scores.

29. What does Pearson correlation evaluate?
    Whether system scores have a linear relationship with human scores.

30. Why bootstrap confidence intervals?
    They estimate uncertainty, especially when the benchmark is small.

31. What is a single-annotator pilot benchmark?
    A preliminary human-scored dataset from one annotator, not a gold standard.

32. What would be the next methodological improvement?
    Add more annotators, measure agreement, and expand the human STS benchmark.

33. Does this project train large models automatically?
    No. Training is exposed through explicit CLI commands.

34. Does this project claim results before experiments run?
    No. Documentation states when evaluation is pending.

35. What did the implementation contribute beyond using libraries?
    It designed the reproducible pipeline, leakage controls, evaluation guards, annotation workflow, and portfolio-ready structure.

