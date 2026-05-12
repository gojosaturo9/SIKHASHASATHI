from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


FEATURE_VERSION = 1
IMAGE_SIZE = 96


# Use: Internal helper for to rgb image.
# Linked with: extract_liveness_features
def _to_rgb_image(image) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    return Image.fromarray(np.asarray(image).astype(np.uint8)).convert("RGB")


# Use: Internal helper for crop with margin.
# Linked with: extract_liveness_features
def _crop_with_margin(image: Image.Image, box, margin: float = 0.45) -> Image.Image:
    if box is None:
        return image

    width, height = image.size
    if hasattr(box, "left"):
        left, top, right, bottom = box.left(), box.top(), box.right(), box.bottom()
    else:
        left, top, right, bottom = box

    face_width = max(1, int(right - left))
    face_height = max(1, int(bottom - top))
    pad_x = int(face_width * margin)
    pad_y = int(face_height * margin)

    left = max(0, int(left) - pad_x)
    top = max(0, int(top) - pad_y)
    right = min(width, int(right) + pad_x)
    bottom = min(height, int(bottom) + pad_y)

    if right <= left or bottom <= top:
        return image
    return image.crop((left, top, right, bottom))


# Use: Internal helper for normalise image.
# Linked with: extract_liveness_features
def _normalise_image(image: Image.Image) -> Image.Image:
    image = ImageOps.autocontrast(image, cutoff=1)
    image = ImageEnhance.Contrast(image).enhance(1.08)
    return image.resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR)


# Use: Internal helper for lbp histogram.
# Linked with: extract_liveness_features
def _lbp_histogram(gray: np.ndarray) -> np.ndarray:
    center = gray[1:-1, 1:-1]
    code = np.zeros_like(center, dtype=np.uint8)
    neighbours = (
        gray[:-2, :-2],
        gray[:-2, 1:-1],
        gray[:-2, 2:],
        gray[1:-1, 2:],
        gray[2:, 2:],
        gray[2:, 1:-1],
        gray[2:, :-2],
        gray[1:-1, :-2],
    )

    for bit, neighbour in enumerate(neighbours):
        code |= ((neighbour >= center) << bit).astype(np.uint8)

    hist, _ = np.histogram(code, bins=256, range=(0, 256), density=True)
    return hist.astype(np.float32)


# Use: Internal helper for laplacian.
# Linked with: extract_liveness_features
def _laplacian(gray: np.ndarray) -> np.ndarray:
    return (
        -4.0 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
    )


# Use: Internal helper for fft features.
# Linked with: extract_liveness_features
def _fft_features(gray: np.ndarray) -> np.ndarray:
    spectrum = np.fft.fftshift(np.fft.fft2(gray))
    magnitude = np.log1p(np.abs(spectrum))
    height, width = magnitude.shape
    y, x = np.ogrid[:height, :width]
    distance = np.sqrt((y - height / 2) ** 2 + (x - width / 2) ** 2)
    max_distance = float(distance.max())

    bands = []
    for start, stop in ((0.0, 0.18), (0.18, 0.38), (0.38, 0.65), (0.65, 1.0)):
        mask = (distance >= start * max_distance) & (distance < stop * max_distance)
        bands.append(float(np.mean(magnitude[mask])) if np.any(mask) else 0.0)
    return np.array(bands, dtype=np.float32)


# Use: Handles extract liveness features behavior in this module.
# Linked with: _extract_records, _predict_attack_type, _predict_custom_live_score
def extract_liveness_features(image, face_box=None) -> np.ndarray:
    """Extract print/screen spoof cues from an RGB image or face crop."""
    rgb_image = _to_rgb_image(image)
    rgb_image = _crop_with_margin(rgb_image, face_box)
    rgb_image = _normalise_image(rgb_image)

    rgb = np.asarray(rgb_image).astype(np.float32) / 255.0
    gray_image = rgb_image.convert("L")
    gray = np.asarray(gray_image).astype(np.float32) / 255.0
    hsv = np.asarray(rgb_image.convert("HSV")).astype(np.float32) / 255.0

    channel_stats = []
    for channel in range(3):
        values = rgb[:, :, channel]
        channel_stats.extend(
            [
                float(values.mean()),
                float(values.std()),
                float(np.percentile(values, 10)),
                float(np.percentile(values, 90)),
            ]
        )

    color_hist = []
    for channel in range(3):
        hist, _ = np.histogram(rgb[:, :, channel], bins=12, range=(0.0, 1.0), density=True)
        color_hist.extend(hist.astype(np.float32).tolist())

    hsv_stats = []
    for channel in range(3):
        values = hsv[:, :, channel]
        hsv_stats.extend([float(values.mean()), float(values.std())])

    gradient_y, gradient_x = np.gradient(gray)
    gradient_mag = np.sqrt(gradient_x**2 + gradient_y**2)
    lap = _laplacian(gray)
    edges = np.asarray(gray_image.filter(ImageFilter.FIND_EDGES)).astype(np.float32) / 255.0

    texture_stats = np.array(
        [
            float(gray.mean()),
            float(gray.std()),
            float(gradient_mag.mean()),
            float(gradient_mag.std()),
            float(np.var(lap)),
            float(np.mean(np.abs(lap))),
            float(edges.mean()),
            float(edges.std()),
            float(np.mean(rgb.max(axis=2) > 0.92)),
            float(np.mean(rgb.min(axis=2) < 0.08)),
            float(np.mean(hsv[:, :, 1] < 0.12)),
            float(np.mean(hsv[:, :, 2] > 0.90)),
        ],
        dtype=np.float32,
    )

    return np.concatenate(
        [
            np.array(channel_stats, dtype=np.float32),
            np.array(color_hist, dtype=np.float32),
            np.array(hsv_stats, dtype=np.float32),
            texture_stats,
            _fft_features(gray),
            _lbp_histogram(gray),
        ]
    ).astype(np.float32)
