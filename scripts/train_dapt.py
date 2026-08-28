from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dapt import train_dapt
from src.utils import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MLM domain-adaptive pretraining for one model.")
    parser.add_argument("--config", default="config/default.yaml", help="Path to YAML configuration.")
    parser.add_argument("--model", required=True, choices=["mbert", "xlmr", "kazroberta"], help="Model key.")
    args = parser.parse_args()
    metadata = train_dapt(args.model, load_config(args.config))
    print(metadata)


if __name__ == "__main__":
    main()
