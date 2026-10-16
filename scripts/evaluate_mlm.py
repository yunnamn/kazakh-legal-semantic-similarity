from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.corpus import load_split
from src.dapt import evaluate_mlm_checkpoint
from src.utils import get_path, load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a base or DAPT MLM checkpoint on deterministic held-out masks.")
    parser.add_argument("--config", default="config/default.yaml", help="Path to YAML configuration.")
    parser.add_argument("--model", required=True, choices=["mbert", "xlmr", "kazroberta"], help="Model key.")
    parser.add_argument("--variant", required=True, choices=["base", "dapt"], help="Checkpoint variant.")
    args = parser.parse_args()
    config = load_config(args.config)
    test_df = load_split("mlm_test", config)
    result = evaluate_mlm_checkpoint(args.model, args.variant, test_df, config)
    out = get_path(config, "metrics_dir") / f"{args.model}_{args.variant}_mlm.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.Series(result).to_json(out, force_ascii=False, indent=2)
    print(pd.Series(result).to_string())


if __name__ == "__main__":
    main()
