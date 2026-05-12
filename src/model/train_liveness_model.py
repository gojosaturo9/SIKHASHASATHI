from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import joblib
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

try:
    from src.model.liveness_features import FEATURE_VERSION, extract_liveness_features
except ModuleNotFoundError:
    from liveness_features import FEATURE_VERSION, extract_liveness_features


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
LIVE_DIR_NAMES = {"live", "real", "real_video", "genuine"}
LIVE_ATTACK_TYPE = "live"
UNKNOWN_ATTACK_TYPE = "spoof"
ATTACK_TYPE_ALIASES = {
    "print": "print_attack",
    "printed": "print_attack",
    "paper": "print_attack",
    "paper_photo": "print_attack",
    "print_attack": "print_attack",
    "print_cut": "partial_spoof",
    "screen": "replay_attack",
    "screen_photo": "replay_attack",
    "phone": "replay_attack",
    "monitor": "replay_attack",
    "pad": "replay_attack",
    "tablet": "replay_attack",
    "replay": "replay_attack",
    "replay_attack": "replay_attack",
    "video_replay": "replay_attack",
    "mask": "3d_mask",
    "3d_mask": "3d_mask",
    "mask_attack": "3d_mask",
    "partial": "partial_spoof",
    "partial_spoof": "partial_spoof",
    "cutout": "partial_spoof",
    "cut_out": "partial_spoof",
    "mask_cut": "partial_spoof",
    "outline": "partial_spoof",
}
CELEBA_SPOOF_TYPE_TO_ATTACK = {
    0: LIVE_ATTACK_TYPE,
    1: "print_attack",
    2: "print_attack",
    3: "print_attack",
    4: "print_attack",
    5: "print_attack",
    6: "partial_spoof",
    7: "replay_attack",
    8: "replay_attack",
    9: "replay_attack",
    10: "3d_mask",
}
SPOOF_DIR_NAMES = {
    "spoof",
    "fake",
    "attack",
    "photo",
    "paper",
    "paper_photo",
    "screen",
    "screen_photo",
    "mask",
    "mask_cut",
    "outline",
    "print",
    "print_cut",
    "monitor",
    "phone",
    "pad",
    "replay",
    *ATTACK_TYPE_ALIASES.keys(),
}


# Use: Internal helper for normalise attack type.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def _normalise_attack_type(value: str | None):
    if not value:
        return UNKNOWN_ATTACK_TYPE
    cleaned = value.lower().replace("-", "_").replace(" ", "_")
    return ATTACK_TYPE_ALIASES.get(cleaned, cleaned)


# Use: Internal helper for infer attack type.
# Linked with: _iter_media
def _infer_attack_type(parts: set[str], label: int):
    if label == 1:
        return LIVE_ATTACK_TYPE

    for part in sorted(parts):
        attack_type = ATTACK_TYPE_ALIASES.get(part)
        if attack_type:
            return attack_type
    return UNKNOWN_ATTACK_TYPE


# Use: Internal helper for iter media.
# Linked with: _load_records
def _iter_media(dataset_dir: Path):
    for path in sorted(dataset_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
            parts = {
                part.lower().replace("-", "_").replace(" ", "_")
                for part in path.relative_to(dataset_dir).parts
            }
            if parts & LIVE_DIR_NAMES:
                yield path, 1, LIVE_ATTACK_TYPE
            elif parts & SPOOF_DIR_NAMES:
                yield path, 0, _infer_attack_type(parts, 0)


# Use: Internal helper for iter labeled media.
# Linked with: _load_records
def _iter_labeled_media(dataset_dir: Path, label: int, attack_type: str):
    for path in sorted(dataset_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
            yield path, label, attack_type


# Use: Internal helper for iter celeba spoof media.
# Linked with: _load_records
def _iter_celeba_spoof_media(image_root: Path, labels_path: Path):
    with labels_path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    if isinstance(metadata, dict):
        items = metadata.items()
    elif isinstance(metadata, list):
        items = (
            (
                entry.get("path")
                or entry.get("image")
                or entry.get("image_path")
                or entry.get("file"),
                entry.get("labels") or entry.get("label") or entry.get("attributes"),
            )
            for entry in metadata
            if isinstance(entry, dict)
        )
    else:
        raise RuntimeError(f"Unsupported CelebA-Spoof label format: {labels_path}")

    for relative_path, labels in items:
        if not relative_path or labels is None:
            continue

        try:
            spoof_type = int(labels[40])
        except (TypeError, ValueError, IndexError) as exc:
            raise RuntimeError(
                f"Invalid CelebA-Spoof labels for {relative_path} in {labels_path}"
            ) from exc

        attack_type = CELEBA_SPOOF_TYPE_TO_ATTACK.get(
            spoof_type, UNKNOWN_ATTACK_TYPE
        )
        label = 1 if attack_type == LIVE_ATTACK_TYPE else 0
        image_path = image_root / str(relative_path).replace("\\", "/")
        if image_path.exists():
            yield image_path, label, attack_type


# Use: Internal helper for augment images.
# Linked with: _extract_records
def _augment_images(image: Image.Image):
    image = image.convert("RGB")
    yield image
    yield ImageOps.mirror(image)
    yield ImageEnhance.Brightness(image).enhance(0.82)
    yield ImageEnhance.Brightness(image).enhance(1.18)
    yield ImageEnhance.Contrast(image).enhance(1.22)


# Use: Internal helper for sample video frames.
# Linked with: _load_media_images
def _sample_video_frames(path: Path, frames_per_video: int):
    try:
        import cv2
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Video datasets require opencv-python-headless. Install requirements again: "
            "python -m pip install -r requirements.txt"
        ) from exc

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return

    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count <= 0:
        frame_indexes = range(frames_per_video)
    else:
        frame_indexes = np.linspace(0, max(0, frame_count - 1), frames_per_video, dtype=int)

    for frame_index in frame_indexes:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        ok, frame = capture.read()
        if not ok:
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        yield Image.fromarray(rgb)

    capture.release()


# Use: Internal helper for load media images.
# Linked with: _extract_records
def _load_media_images(path: Path, frames_per_video: int):
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        yield Image.open(path).convert("RGB")
    else:
        yield from _sample_video_frames(path, frames_per_video)


# Use: Internal helper for deduplicate records.
# Linked with: _load_records
def _deduplicate_records(records):
    labels_by_path = {}
    deduplicated = []

    for path, label, attack_type in records:
        key = str(path.resolve())
        existing_record = labels_by_path.get(key)
        if existing_record is not None:
            if existing_record != (label, attack_type):
                raise RuntimeError(
                    f"Conflicting liveness/attack labels for the same file: {path}"
                )
            continue
        labels_by_path[key] = (label, attack_type)
        deduplicated.append((path, label, attack_type))

    return deduplicated


# Use: Internal helper for balance records.
# Linked with: _load_records
def _balance_records(records, max_per_class: int | None, seed: int):
    if max_per_class is None or max_per_class <= 0:
        return records

    rng = np.random.default_rng(seed)
    balanced = []
    for label in (0, 1):
        class_records = [record for record in records if record[1] == label]
        if len(class_records) > max_per_class:
            selected_indexes = rng.choice(
                len(class_records), size=max_per_class, replace=False
            )
            class_records = [class_records[int(index)] for index in selected_indexes]
        balanced.extend(class_records)

    return sorted(balanced, key=lambda record: str(record[0]))


# Use: Internal helper for load records.
# Linked with: train_model
def _load_records(
    dataset_dir: Path,
    live_dirs: list[Path],
    spoof_dirs: list[Path],
    attack_dirs: dict[str, list[Path]],
    celeba_spoof_root: Path | None,
    celeba_spoof_labels: list[Path],
    max_per_class: int | None,
    seed: int,
):
    if celeba_spoof_labels and celeba_spoof_root is None:
        raise RuntimeError("--celeba-spoof-labels requires --celeba-spoof-root.")

    records = list(_iter_media(dataset_dir))
    for live_dir in live_dirs:
        records.extend(_iter_labeled_media(live_dir, 1, LIVE_ATTACK_TYPE))
    for spoof_dir in spoof_dirs:
        records.extend(_iter_labeled_media(spoof_dir, 0, UNKNOWN_ATTACK_TYPE))
    for attack_type, paths in attack_dirs.items():
        for attack_dir in paths:
            records.extend(_iter_labeled_media(attack_dir, 0, attack_type))
    if celeba_spoof_root is not None:
        for labels_path in celeba_spoof_labels:
            records.extend(_iter_celeba_spoof_media(celeba_spoof_root, labels_path))

    records = _balance_records(_deduplicate_records(records), max_per_class, seed)

    if not records:
        raise RuntimeError(
            "No training media found. Use folders like "
            "src/model/liveness_dataset/live and src/model/liveness_dataset/spoof, "
            "or pass --live-data/--spoof-data for raw dataset folders."
        )

    class_counts = {
        label: sum(record_label == label for _, record_label, _ in records)
        for label in (0, 1)
    }
    if any(count == 0 for count in class_counts.values()):
        raise RuntimeError(
            f"Need both live and spoof media files. Current media counts: {class_counts}"
        )
    if any(count < 2 for count in class_counts.values()):
        raise RuntimeError(
            f"Need at least two media files per class for validation. Current media counts: {class_counts}"
        )
    return records, class_counts


# Use: Internal helper for extract records.
# Linked with: train_model
def _extract_records(records, augment: bool, frames_per_video: int):
    features = []
    labels = []
    attack_types = []
    paths = []

    for path, label, attack_type in records:
        try:
            source_images = list(_load_media_images(path, frames_per_video))
        except Exception as exc:
            print(f"Skipping unreadable media: {path} ({exc})")
            continue

        for image in source_images:
            images = _augment_images(image) if augment else (image,)
            for augmented in images:
                features.append(extract_liveness_features(augmented))
                labels.append(label)
                attack_types.append(attack_type)
                paths.append(str(path))

    if not features:
        raise RuntimeError("No readable training images found.")

    return np.vstack(features), np.array(labels), np.array(attack_types), paths


# Use: Internal helper for train attack type model.
# Linked with: train_model
def _train_attack_type_model(X_train, attack_train, X_test, attack_test, seed: int):
    train_mask = attack_train != LIVE_ATTACK_TYPE
    test_mask = attack_test != LIVE_ATTACK_TYPE
    train_labels = attack_train[train_mask]
    test_labels = attack_test[test_mask]

    attack_counts = {
        attack_type: int(np.sum(train_labels == attack_type))
        for attack_type in sorted(set(train_labels.tolist()))
    }

    enough_classes = len(attack_counts) >= 2
    enough_samples = all(count >= 2 for count in attack_counts.values())
    if not enough_classes or not enough_samples:
        print("\nAttack subtype model skipped.")
        print(
            "Need at least two spoof attack types with at least two training "
            f"samples each. Current spoof train counts: {attack_counts}"
        )
        return None, attack_counts

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                SVC(
                    kernel="rbf",
                    C=4.0,
                    gamma="scale",
                    class_weight="balanced",
                    probability=True,
                    random_state=seed,
                ),
            ),
        ]
    )
    model.fit(X_train[train_mask], train_labels)

    if np.any(test_mask):
        predictions = model.predict(X_test[test_mask])
        print("\nAttack subtype classifier report:")
        print(classification_report(test_labels, predictions, zero_division=0))
        print("Confusion matrix:")
        print(confusion_matrix(test_labels, predictions))

    return model, attack_counts


# Use: Handles train model behavior in this module.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def train_model(
    dataset_dir: Path,
    output_path: Path,
    threshold: float,
    test_size: float,
    frames_per_video: int,
    live_dirs: list[Path],
    spoof_dirs: list[Path],
    attack_dirs: dict[str, list[Path]],
    celeba_spoof_root: Path | None,
    celeba_spoof_labels: list[Path],
    max_per_class: int | None,
    seed: int,
):
    records, image_class_counts = _load_records(
        dataset_dir=dataset_dir,
        live_dirs=live_dirs,
        spoof_dirs=spoof_dirs,
        attack_dirs=attack_dirs,
        celeba_spoof_root=celeba_spoof_root,
        celeba_spoof_labels=celeba_spoof_labels,
        max_per_class=max_per_class,
        seed=seed,
    )
    record_paths = np.array([path for path, _, _ in records], dtype=object)
    record_labels = np.array([label for _, label, _ in records])
    record_attack_types = np.array([attack_type for _, _, attack_type in records])
    validation_count = max(2, int(math.ceil(len(records) * test_size)))
    validation_count = min(validation_count, len(records) - 2)

    train_paths, test_paths, train_labels, test_labels, train_attack_types, test_attack_types = train_test_split(
        record_paths,
        record_labels,
        record_attack_types,
        test_size=validation_count,
        random_state=seed,
        stratify=record_labels,
    )

    train_records = list(
        zip(train_paths.tolist(), train_labels.tolist(), train_attack_types.tolist())
    )
    test_records = list(
        zip(test_paths.tolist(), test_labels.tolist(), test_attack_types.tolist())
    )
    X_train, y_train, attack_train, train_augmented_paths = _extract_records(
        train_records, augment=True, frames_per_video=frames_per_video
    )
    X_test, y_test, attack_test, test_paths = _extract_records(
        test_records, augment=False, frames_per_video=frames_per_video
    )

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                SVC(
                    kernel="rbf",
                    C=4.0,
                    gamma="scale",
                    class_weight="balanced",
                    probability=True,
                    random_state=seed,
                ),
            ),
        ]
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)
    live_index = list(model.classes_).index(1)
    live_scores = probabilities[:, live_index]
    threshold_predictions = (live_scores >= threshold).astype(int)

    print("Model classes:", model.classes_.tolist())
    print("Training samples:", len(X_train), "Validation samples:", len(X_test))
    print("Original media files:", len(records))
    print("Media class counts:", image_class_counts)
    attack_type_counts = {
        attack_type: int(np.sum(record_attack_types == attack_type))
        for attack_type in sorted(set(record_attack_types.tolist()))
    }
    print("Attack type media counts:", attack_type_counts)
    print("\nDefault classifier report:")
    print(classification_report(y_test, predictions, target_names=["spoof", "live"]))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, predictions))
    print(f"\nThreshold report at live threshold {threshold}:")
    print(classification_report(y_test, threshold_predictions, target_names=["spoof", "live"]))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, threshold_predictions))

    attack_type_model, attack_train_counts = _train_attack_type_model(
        X_train, attack_train, X_test, attack_test, seed
    )

    artifact = {
        "version": 2,
        "feature_version": FEATURE_VERSION,
        "model_type": "texture_svc_liveness",
        "model": model,
        "attack_type_model": attack_type_model,
        "threshold": threshold,
        "class_names": {0: "spoof", 1: "live"},
        "attack_type_names": sorted(
            attack_type
            for attack_type in set(record_attack_types.tolist())
            if attack_type != LIVE_ATTACK_TYPE
        ),
        "metrics": {
            "train_samples": int(len(X_train)),
            "validation_samples": int(len(X_test)),
            "original_media_files": int(len(records)),
            "train_media_files": int(len(set(train_augmented_paths))),
            "validation_media_files": int(len(set(test_paths))),
            "frames_per_video": int(frames_per_video),
            "class_counts": image_class_counts,
            "attack_type_counts": attack_type_counts,
            "attack_type_train_counts": attack_train_counts,
            "live_dirs": [str(path) for path in live_dirs],
            "spoof_dirs": [str(path) for path in spoof_dirs],
            "attack_dirs": {
                attack_type: [str(path) for path in paths]
                for attack_type, paths in attack_dirs.items()
            },
            "celeba_spoof_root": (
                str(celeba_spoof_root) if celeba_spoof_root is not None else None
            ),
            "celeba_spoof_labels": [str(path) for path in celeba_spoof_labels],
            "max_per_class": max_per_class,
            "seed": int(seed),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output_path)
    print(f"\nSaved liveness model to: {output_path}")


# Use: Handles parse args behavior in this module.
# Linked with: parse_args
def parse_args():
    parser = argparse.ArgumentParser(
        description="Train the project's custom face liveness anti-spoofing model."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parent / "liveness_dataset",
        help="Dataset root containing live/ and spoof/ folders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "liveness_model.joblib",
        help="Where to save the trained model artifact.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.52,
        help="Minimum live probability required by the app.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Validation split size.",
    )
    parser.add_argument(
        "--frames-per-video",
        type=int,
        default=8,
        help="Number of evenly spaced frames sampled from each video file.",
    )
    parser.add_argument(
        "--live-data",
        type=Path,
        action="append",
        default=[],
        help=(
            "Additional dataset folder to label as live/real. Repeat this for "
            "IndicFairFace, ISGD/ISCG, or your own real webcam captures."
        ),
    )
    parser.add_argument(
        "--spoof-data",
        type=Path,
        action="append",
        default=[],
        help=(
            "Additional dataset folder to label as spoof/fake. Repeat this for "
            "printed photo, phone screen, replay, or mask attack folders."
        ),
    )
    parser.add_argument(
        "--print-attack-data",
        type=Path,
        action="append",
        default=[],
        help="Folder containing printed-photo or paper print attack samples.",
    )
    parser.add_argument(
        "--replay-attack-data",
        type=Path,
        action="append",
        default=[],
        help="Folder containing phone, laptop, tablet, monitor, or replay video attacks.",
    )
    parser.add_argument(
        "--mask-attack-data",
        type=Path,
        action="append",
        default=[],
        help="Folder containing 3D mask attack samples.",
    )
    parser.add_argument(
        "--partial-spoof-data",
        type=Path,
        action="append",
        default=[],
        help="Folder containing cutout, eye/mouth cut, or partial spoof samples.",
    )
    parser.add_argument(
        "--celeba-spoof-root",
        type=Path,
        default=None,
        help=(
            "Root folder of an extracted CelebA-Spoof dataset. Paths from the "
            "CelebA-Spoof JSON label files are resolved below this directory."
        ),
    )
    parser.add_argument(
        "--celeba-spoof-labels",
        type=Path,
        action="append",
        default=[],
        help=(
            "CelebA-Spoof JSON label file such as train_label.json, "
            "val_label.json, or test_label.json. Repeat for multiple splits."
        ),
    )
    parser.add_argument(
        "--max-per-class",
        type=int,
        default=None,
        help=(
            "Optional cap on original media files per class before augmentation. "
            "Use this to balance large live datasets against smaller spoof datasets."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for splitting and optional class balancing.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    attack_dirs = {
        "print_attack": args.print_attack_data,
        "replay_attack": args.replay_attack_data,
        "3d_mask": args.mask_attack_data,
        "partial_spoof": args.partial_spoof_data,
    }
    train_model(
        args.data,
        args.output,
        args.threshold,
        args.test_size,
        args.frames_per_video,
        args.live_data,
        args.spoof_data,
        attack_dirs,
        args.celeba_spoof_root,
        args.celeba_spoof_labels,
        args.max_per_class,
        args.seed,
    )
