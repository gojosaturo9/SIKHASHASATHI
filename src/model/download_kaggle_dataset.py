from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


DEFAULT_DATASET = "trainingdatapro/real-vs-fake-anti-spoofing-video-classification"


# Use: Handles download dataset behavior in this module.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def download_dataset(dataset: str, output_dir: Path, unzip: bool):
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "kaggle.cli",
        "datasets",
        "download",
        "-d",
        dataset,
        "-p",
        str(output_dir),
    ]
    if unzip:
        command.append("--unzip")

    subprocess.run(command, check=True)


# Use: Handles parse args behavior in this module.
# Linked with: parse_args
def parse_args():
    parser = argparse.ArgumentParser(
        description="Download a Kaggle liveness dataset for local training."
    )
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help="Kaggle dataset slug, for example owner/dataset-name.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "kaggle_liveness_data",
        help="Download/extract location.",
    )
    parser.add_argument(
        "--no-unzip",
        action="store_true",
        help="Keep the downloaded zip instead of extracting it.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    download_dataset(args.dataset, args.output, unzip=not args.no_unzip)
