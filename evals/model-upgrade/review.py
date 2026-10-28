"""Offline glare review helpers; validate saved preference choices."""

import argparse
from pathlib import Path

from evaluation import build_glare_review, reveal_ratings
from records import RunStore


def main() -> None:
    """Build a labelled page or validate a downloaded ratings file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "reveal"))
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--ratings", type=Path)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    store = RunStore(args.run_dir)
    store.manifest()
    if args.command == "build":
        output = build_glare_review(store, seed=args.seed)
    else:
        if args.ratings is None:
            parser.error("reveal requires --ratings")
        output = reveal_ratings(store, args.ratings)
    print(output)


if __name__ == "__main__":
    main()
