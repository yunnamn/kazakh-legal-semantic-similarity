# Testing, reproducibility and environment scope

The delivered test report is `reports/pytest-results.xml` with the captured terminal
summary in `reports/pytest-output.txt`. `reports/environment.json` records the actual
Python/platform/package versions; `reports/delivery_status.json` records explicit
completion boundaries. These are observed execution results, not proposed outcomes.

Run `python -m pytest -q` or `PYTHONPATH=src python -m pytest -q`. Tests construct
marked, nonlegal `TEST_ONLY` fixtures inside temporary directories. They do not
download legal data, train a model, produce publishable annotations or claim that
fixture source URLs prove authenticity. The production pipeline permanently blocks
fixture-marked builds and text from research export.

Coverage includes normalization and structural parsing; dates/initials/list numbering;
provenance on duplicate harvests and distinct provisions; acquisition/robots/challenge
failures; metadata-only discovery; reused-data schemas; malformed streams; immutable
raw and experiment artifacts; both endpoints of protected similarity pairs; law
versions; exact, verified near and contiguous overlap; sentence/paragraph boundaries;
prior-split conflicts; deterministic repeat builds; independent count/blocker checks;
blank, incomplete, stale and rejected human-QA forms; strict configuration; and
fixed masked-LM diagnostic helpers. The exact-prefix Jaccard join is checked against
a brute-force implementation on deterministic fixtures. These are correctness tests,
not measured legal-language precision/recall or a full-corpus performance benchmark.

The default installation uses only Beautiful Soup and standard-library components.
`requirements-core.lock` and `requirements-dev.lock` capture exact packages already
installed in the offline test environment. They do not include wheel hashes or an
entire OS image. The processed manifest records Python, Unicode, parser and pipeline
code versions. For a publication, archive the complete acquisition/training
`pip freeze` or lockfile, OS/container image digest, model/tokenizer commits and any
platform-dependent numeric settings as well as these core files.

Hub acquisition is optional and pinned by full dataset revision; the installed client
version is recorded but its live network path was not exercised. Parquet support is
optional, declared as a bounded dependency range, and was not installed/tested here.
An operator choosing Parquet must resolve and freeze the exact Arrow environment,
validate the actual input and record it before claiming byte-level reproduction.
No `trust_remote_code` dataset scripts are run.

The included CI workflow proposes a Python 3.11/3.12/3.13 test matrix. Only the local
reported environment was actually executed in this delivery. An online CI definition
is not a report that those jobs passed. Live Adilet DOM/encoding and real Hub source
files, original-repository integration, native-Kazakh review, training, human
annotation and full-census scaling remain untested.
