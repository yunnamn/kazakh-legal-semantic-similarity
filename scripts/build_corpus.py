from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.corpus import build_corpus_from_c4, make_splits
from src.utils import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and split the weakly filtered Kazakh legal-domain candidate corpus.")
    parser.add_argument("--config", default="config/default.yaml", help="Path to YAML configuration.")
    args = parser.parse_args()
    config = load_config(args.config)
    corpus = build_corpus_from_c4(config)
    split_df = make_splits(corpus, config)
    print(split_df["split"].value_counts().to_string())


if __name__ == "__main__":
    main()
