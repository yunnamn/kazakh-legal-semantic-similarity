from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.annotation import generate_annotation_candidates
from src.utils import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate blank human-annotation candidate sentence pairs from annotation_pool only.")
    parser.add_argument("--config", default="config/default.yaml", help="Path to YAML configuration.")
    args = parser.parse_args()
    candidates = generate_annotation_candidates(load_config(args.config))
    print(candidates["sampling_strategy"].value_counts().to_string())


if __name__ == "__main__":
    main()
