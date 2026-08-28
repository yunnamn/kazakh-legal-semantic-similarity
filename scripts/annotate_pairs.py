from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.annotation import annotate_pairs_cli
from src.utils import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactively annotate sentence pairs on the human 0-5 semantic-similarity scale.")
    parser.add_argument("--config", default="config/default.yaml", help="Path to YAML configuration.")
    parser.add_argument("--annotator", required=True, help="Annotator identifier.")
    parser.add_argument("--no-resume", action="store_true", help="Start a fresh annotation file.")
    args = parser.parse_args()
    annotate_pairs_cli(args.annotator, load_config(args.config), resume=not args.no_resume)


if __name__ == "__main__":
    main()
