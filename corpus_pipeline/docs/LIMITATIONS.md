# Limitations and remaining work

1. **Original repository not obtained.** No complete audit, model reconstruction,
   original-code patch, README merge, training-loader integration or reproduction of
   reported metrics was possible. The toolkit remains additive and research export
   requires a real reviewed reference checkout. This is partial task completion,
   not a claim that an uninspected repository was upgraded successfully.
2. **No live corpus was acquired.** Public source cards/schemas were assessed; complete
   Hub files and Adilet documents were not downloaded here. The HTML selectors,
   network redirects, source encodings and current source layouts need live review.
   Mocked acquisition tests do not establish availability or scraping permission.
3. **Authenticity is source-backed, not magically proven by hashing.** Checksums and
   chain-of-custody receipts detect changes, not a dishonest/manual source assertion.
   The system cannot prove a person performed the required source/QA review. A public
   curator's license declaration is not an independent chain-of-title opinion.
4. **No optimal thresholds or representativeness claimed.** Proposed proportions,
   Jaccard/window cutoffs, common-text limits, component cap and QA sample size have
   not been calibrated on an acquired Kazakh legal corpus. Choose them without
   final-test feedback, record the decision and quantify sensitivity/coverage.
5. **Rule-based language and structure.** Cyrillic/Kazakh-character heuristics can
   reject valid short passages and accept mixed text. Sentence boundaries, amendment
   wording, annex numbering, unusual headings and line wraps can be ambiguous. Tables
   are retained but excluded from the prose view. No PDF/OCR adapter is delivered.
6. **Source-specific losses cannot be reversed.** Reused text may have lost footnotes,
   anchors, metadata or sentence boundaries. Unknown URLs/timestamps remain null.
   Chunk fragments are not stitched or completed. Official re-acquisition is needed
   when full fidelity matters.
7. **Bounded leakage claim.** The implementation checks observed source families,
   explicit cross-registry identities, exact guard matches, thresholded word-shingle
   overlap and contiguous windows. It cannot identify every semantic paraphrase,
   short substring, translated overlap, unknown cross-registry alias or overlap with
   a pretrained model's undisclosed pretraining data. No perfect decontamination claim.
8. **Determinism has a scope.** Identical frozen bytes/config/reviews/code/runtime
   reproduce outputs in the tested environment. Fresh network retrievals and dependency
   or Unicode/parser changes create different releases. New corpora need the prior
   split lock for role continuity. Existing outputs are not overwritten automatically.
9. **Scaling is unbenchmarked on a full legal census.** Text/overlap indexes are
   SQLite-backed and sources stream, but identity graphs, catalog metadata, some
   exact-group lists and provenance occupy memory. Long documents/windows can consume
   substantial disk/time. Candidate-budget limits abort rather than skip checks.
   Benchmark a pilot, retain failure reports and do not infer capacity from tiny tests.
10. **Experimental environment not reproduced.** Core offline tests ran on the
    reported Linux/Python environment only. Optional live Hub/Adilet, Parquet and GPU
    training paths were not exercised. No tokenizer-token counts, performance deltas,
    annotator agreement or gold labels were generated. A proposed CI matrix is not
    evidence it ran.
11. **Human-QA and rights gates are necessary, not sufficient for publication.** The
    default source sample is a smoke check, not a reliability estimate. Decide a
    defensible stratified review and publication/privacy policy with the research
    team. Export readiness means local input-view readiness, not legal advice or an
    automatically approved public dataset.
