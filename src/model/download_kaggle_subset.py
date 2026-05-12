from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import zipfile
from io import StringIO
from pathlib import Path


DEFAULT_DATASET = "trainingdatapro/real-vs-fake-anti-spoofing-video-classification"


# Use: Internal helper for run kaggle.
# Linked with: _list_dataset_files, download_subset
def _run_kaggle(args):
    command = [sys.executable, "-m", "kaggle.cli", *args]
    return subprocess.run(command, check=True, capture_output=True, text=True)


# Use: Internal helper for list dataset files.
# Linked with: download_subset
def _list_dataset_files(dataset: str):
    result = _run_kaggle(
        ["datasets", "files", dataset, "--page-size", "200", "-v"]
    )
    reader = csv.DictReader(StringIO(result.stdout.replace("\r", "")))
    return [
        {"name": row["name"], "size": int(row["size"])}
        for row in reader
        if row.get("name") and row.get("size", "").isdigit()
    ]


# Use: Internal helper for pick files.
# Linked with: download_subset
def _pick_files(files, per_class: int):
    videos = [file for file in files if file["name"].lower().endswith((".mp4", ".mov", ".avi"))]
    live = [
        file for file in videos
        if "/real_video/" in file["name"].replace("\\", "/")
        or "/real/" in file["name"].replace("\\", "/")
        or "/live/" in file["name"].replace("\\", "/")
    ]
    spoof = [
        file for file in videos
        if "/attack/" in file["name"].replace("\\", "/")
        or "/spoof/" in file["name"].replace("\\", "/")
        or "/print/" in file["name"].replace("\\", "/")
    ]

    if len(live) < per_class or len(spoof) < per_class:
        raise RuntimeError(
            f"Not enough files for a balanced subset. live={len(live)}, spoof={len(spoof)}"
        )

    live = sorted(live, key=lambda file: file["size"])[:per_class]
    spoof = sorted(spoof, key=lambda file: file["size"])[:per_class]
    return live + spoof


# Use: Handles download subset behavior in this module.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def download_subset(dataset: str, output_dir: Path, per_class: int, force: bool):
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_files = _pick_files(_list_dataset_files(dataset), per_class=per_class)

    for file in selected_files:
        target = output_dir / file["name"]
        if target.exists() and not force:
            print(f"Already exists: {target}")
            continue

        print(f"Downloading {file['name']} ({file['size']} bytes)")
        command = [
            "datasets",
            "download",
            dataset,
            "-f",
            file["name"],
            "-p",
            str(target.parent),
            "-q",
        ]
        if force:
            command.append("-o")
        _run_kaggle(command)

        downloaded_name = target.parent / Path(file["name"]).name
        if downloaded_name.exists() and downloaded_name != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            downloaded_name.replace(target)

        zip_wrapper = target.with_suffix(target.suffix + ".zip")
        if zip_wrapper.exists():
            with zipfile.ZipFile(zip_wrapper) as archive:
                archive.extractall(target.parent)

    print(f"Downloaded {len(selected_files)} files into {output_dir}")


# Use: Handles parse args behavior in this module.
# Linked with: parse_args
def parse_args():
    parser = argparse.ArgumentParser(
        description="Download a small balanced subset from a Kaggle liveness dataset."
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "kaggle_liveness_subset",
    )
    parser.add_argument("--per-class", type=int, default=12)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    download_subset(args.dataset, args.output, args.per_class, args.force)
