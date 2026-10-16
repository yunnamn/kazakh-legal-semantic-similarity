#!/bin/sh
# Run from the corpus_pipeline root after a completed acquisition and experiment audit.
# QA/export are separate: this script never fabricates approvals.
set -eu
: "${RAW_DIR:?Set RAW_DIR to the frozen raw store}"
: "${RAW_LOCK:?Set RAW_LOCK to the frozen raw lock JSON}"
: "${CONFIG:?Set CONFIG to the reviewed TOML profile}"
: "${EXPERIMENT_LOCK:?Set EXPERIMENT_LOCK to the approved experiment lock}"
: "${ORIGINAL:?Set ORIGINAL to the immutable original reference checkout}"
: "${PROCESSED:?Set PROCESSED to a new output directory}"
: "${DERIVED:?Set DERIVED to a new output directory}"
: "${REPORT:?Set REPORT to a new validation report path}"
python -m kazlegal_corpus process --raw-dir "$RAW_DIR" --raw-lock "$RAW_LOCK" --config "$CONFIG" --output "$PROCESSED"
python -m kazlegal_corpus split --processed "$PROCESSED" --experiment-lock "$EXPERIMENT_LOCK" --repo-root "$ORIGINAL" --output "$DERIVED"
python -m kazlegal_corpus validate --raw-dir "$RAW_DIR" --processed "$PROCESSED" --derived "$DERIVED" --repo-root "$ORIGINAL" --report "$REPORT"
