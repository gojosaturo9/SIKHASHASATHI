from dataclasses import dataclass
import os
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image, ImageEnhance, ImageOps
from src.model.liveness_features import extract_liveness_features


MODEL_DIR = Path(__file__).resolve().parents[1] / "model"
CUSTOM_LIVENESS_MODEL_PATH = MODEL_DIR / "liveness_model.joblib"
ANTISPOOFING_MODEL_PATH = MODEL_DIR / "antispoofing.onnx"
LEGACY_ANTISPOOF_MODEL_PATH = MODEL_DIR / "antispoof.onnx"
DEFAULT_CUSTOM_LIVENESS_THRESHOLD = 0.50
DEFAULT_CUSTOM_UNCERTAIN_THRESHOLD = 0.25
DEFAULT_DEEPPIX_THRESHOLD = 0.03
DEFAULT_DEEPPIX_UNCERTAIN_THRESHOLD = 0.08
DEFAULT_MINIFASNET_REAL_THRESHOLD = 0.75
DEFAULT_MINIFASNET_UNCERTAIN_THRESHOLD = 0.60
DEFAULT_MINIFASNET_SPOOF_THRESHOLD = 0.70


class AntiSpoofingSetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class AntiSpoofResult:
    is_live: bool
    label: str
    confidence: float
    real_score: float
    details: dict | None = None


# Use: Internal helper for get float setting.
# Linked with: _check_custom_liveness, _check_deeppix_liveness, _check_minifasnet_liveness
def _get_float_setting(name, default):
    value = os.environ.get(name)
    if value is None:
        try:
            value = st.secrets.get(name)
        except Exception:
            value = None

    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# Use: Internal helper for get bool setting.
# Linked with: _check_custom_liveness, _check_minifasnet_liveness
def _get_bool_setting(name, default):
    value = os.environ.get(name)
    if value is None:
        try:
            value = st.secrets.get(name)
        except Exception:
            value = None

    if value is None:
        return default

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# Use: Internal helper for load runtime.
# Linked with: load_anti_spoofing_session
def _load_runtime():
    try:
        import onnxruntime as ort
    except ModuleNotFoundError as exc:
        raise AntiSpoofingSetupError(
            "Anti-spoofing requires onnxruntime. Install project requirements again: "
            "python -m pip install -r requirements.txt"
        ) from exc

    if (
        not ANTISPOOFING_MODEL_PATH.exists()
        and not LEGACY_ANTISPOOF_MODEL_PATH.exists()
    ):
        raise AntiSpoofingSetupError(
            "Anti-spoofing model not found. Expected "
            f"{ANTISPOOFING_MODEL_PATH}."
        )

    return ort


# Use: Loads custom liveness model resources or configuration.
# Linked with: check_face_liveness
@st.cache_resource
def load_custom_liveness_model():
    if not CUSTOM_LIVENESS_MODEL_PATH.exists():
        return None

    try:
        import joblib
    except ModuleNotFoundError as exc:
        raise AntiSpoofingSetupError(
            "Custom liveness model requires joblib. Install project requirements again: "
            "python -m pip install -r requirements.txt"
        ) from exc

    artifact = joblib.load(CUSTOM_LIVENESS_MODEL_PATH)
    if not isinstance(artifact, dict) or "model" not in artifact:
        raise AntiSpoofingSetupError(
            f"Invalid custom liveness model artifact: {CUSTOM_LIVENESS_MODEL_PATH}"
        )
    return artifact


# Use: Loads anti spoofing session resources or configuration.
# Linked with: check_face_liveness
@st.cache_resource
def load_anti_spoofing_session():
    ort = _load_runtime()
    if ANTISPOOFING_MODEL_PATH.exists():
        model_path = ANTISPOOFING_MODEL_PATH
    else:
        model_path = LEGACY_ANTISPOOF_MODEL_PATH
    model_kind = "minifasnet"
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_meta = session.get_inputs()[0]
    output_names = [output.name for output in session.get_outputs()]
    return session, input_meta.name, input_meta.shape, output_names, model_kind


# Use: Internal helper for resolve input size.
# Linked with: _preprocess_deeppix, _preprocess_minifasnet
def _resolve_input_size(input_shape):
    dims = [dim if isinstance(dim, int) else None for dim in input_shape]

    if len(dims) == 4:
        if dims[1] == 3:
            return dims[2] or 224, dims[3] or 224, "nchw"
        if dims[3] == 3:
            return dims[1] or 224, dims[2] or 224, "nhwc"

    return 224, 224, "nchw"


# Use: Internal helper for crop face.
# Linked with: _check_custom_liveness, _check_deeppix_liveness, _check_minifasnet_liveness
def _crop_face(image_np, face_rect, margin=0.55):
    height, width = image_np.shape[:2]
    left = max(0, face_rect.left())
    top = max(0, face_rect.top())
    right = min(width, face_rect.right())
    bottom = min(height, face_rect.bottom())

    face_width = max(1, right - left)
    face_height = max(1, bottom - top)
    pad_x = int(face_width * margin)
    pad_y = int(face_height * margin)

    left = max(0, left - pad_x)
    top = max(0, top - pad_y)
    right = min(width, right + pad_x)
    bottom = min(height, bottom + pad_y)

    return image_np[top:bottom, left:right]


# Use: Internal helper for enhance low light.
# Linked with: _preprocess_deeppix, _preprocess_minifasnet
def _enhance_low_light(image):
    image = ImageOps.autocontrast(image, cutoff=1)
    image = ImageEnhance.Brightness(image).enhance(1.18)
    image = ImageEnhance.Contrast(image).enhance(1.12)
    return image


# Use: Internal helper for preprocess deeppix.
# Linked with: _run_deeppix_prediction
def _preprocess_deeppix(face_crop, input_shape, low_light_enhance=False):
    input_h, input_w, layout = _resolve_input_size(input_shape)
    image = Image.fromarray(face_crop.astype(np.uint8)).convert("RGB")
    if low_light_enhance:
        image = _enhance_low_light(image)
    image = image.resize((input_w, input_h), Image.Resampling.BILINEAR)

    array = np.asarray(image).astype(np.float32) / 255.0
    array = (array - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
        [0.229, 0.224, 0.225], dtype=np.float32
    )

    if layout == "nchw":
        array = np.transpose(array, (2, 0, 1))

    return np.expand_dims(array, axis=0).astype(np.float32)


# Use: Internal helper for preprocess minifasnet.
# Linked with: _run_minifasnet_prediction
def _preprocess_minifasnet(face_crop, input_shape, low_light_enhance=False):
    input_h, input_w, layout = _resolve_input_size(input_shape)
    image = Image.fromarray(face_crop.astype(np.uint8)).convert("RGB")
    if low_light_enhance:
        image = _enhance_low_light(image)
    image = image.resize((input_w, input_h), Image.Resampling.BILINEAR)

    array = np.asarray(image).astype(np.float32)[:, :, ::-1]

    if layout == "nchw":
        array = np.transpose(array, (2, 0, 1))

    return np.expand_dims(array, axis=0).astype(np.float32)


# Use: Internal helper for softmax.
# Linked with: _class_probabilities
def _softmax(scores):
    scores = scores.astype(np.float32)
    scores = scores - np.max(scores)
    exp_scores = np.exp(scores)
    return exp_scores / np.sum(exp_scores)


# Use: Internal helper for class probabilities.
# Linked with: _run_minifasnet_prediction
def _class_probabilities(output):
    scores = np.asarray(output).reshape(-1)

    if scores.size == 1:
        real_score = float(1 / (1 + np.exp(-scores[0])))
        label = "real" if real_score >= 0.5 else "spoof"
        confidence = real_score if label == "real" else 1.0 - real_score
        return label, confidence, real_score, np.array([1.0 - real_score, real_score])

    if np.all(scores >= 0) and 0.98 <= float(np.sum(scores)) <= 1.02:
        probabilities = scores / np.sum(scores)
    else:
        probabilities = _softmax(scores)
    best_index = int(np.argmax(probabilities))

    if probabilities.size == 2:
        labels = ["spoof", "real"]
        real_index = 1
    else:
        labels = ["spoof", "real", "spoof"]
        real_index = 1 if probabilities.size > 1 else best_index

    real_score = float(probabilities[real_index])
    label = labels[best_index] if best_index < len(labels) else f"class_{best_index}"
    return label, float(probabilities[best_index]), real_score, probabilities


# Use: Internal helper for run minifasnet prediction.
# Linked with: _check_minifasnet_liveness
def _run_minifasnet_prediction(session, input_name, input_shape, face_crop, enhanced=False):
    input_tensor = _preprocess_minifasnet(
        face_crop, input_shape, low_light_enhance=enhanced
    )
    output = session.run(None, {input_name: input_tensor})[0]
    return _class_probabilities(output)


# Use: Internal helper for run deeppix prediction.
# Linked with: _check_deeppix_liveness
def _run_deeppix_prediction(session, input_name, input_shape, output_names, face_crop, enhanced=False):
    input_tensor = _preprocess_deeppix(face_crop, input_shape, low_light_enhance=enhanced)
    outputs = session.run(output_names, {input_name: input_tensor})
    output_map = dict(zip(output_names, outputs))
    output_pixel = output_map.get("output_pixel", outputs[0])
    output_binary = output_map.get("output_binary", outputs[-1])
    pixel_score = float(np.mean(output_pixel))
    binary_score = float(np.mean(output_binary))
    return (pixel_score + binary_score) / 2.0


# Use: Internal helper for check deeppix liveness.
# Linked with: check_face_liveness
def _check_deeppix_liveness(
    session,
    input_name,
    input_shape,
    output_names,
    image_np,
    face_rect,
    threshold=DEFAULT_DEEPPIX_THRESHOLD,
):
    scores = []

    for margin in (0.25, 0.45, 0.65):
        face_crop = _crop_face(image_np, face_rect, margin=margin)
        if face_crop.size == 0:
            continue

        scores.append(
            _run_deeppix_prediction(
                session, input_name, input_shape, output_names, face_crop, enhanced=False
            )
        )
        scores.append(
            _run_deeppix_prediction(
                session, input_name, input_shape, output_names, face_crop, enhanced=True
            )
        )

    if not scores:
        return AntiSpoofResult(False, "invalid_face_crop", 1.0, 0.0, {})

    best_score = float(max(scores))
    average_score = float(np.mean(scores))
    live_threshold = _get_float_setting("DEEPPIX_LIVE_THRESHOLD", threshold)
    uncertain_threshold = _get_float_setting(
        "DEEPPIX_UNCERTAIN_THRESHOLD", DEFAULT_DEEPPIX_UNCERTAIN_THRESHOLD
    )

    if best_score >= uncertain_threshold or average_score >= live_threshold:
        label = "real"
        is_live = True
    elif best_score >= live_threshold:
        label = "uncertain"
        is_live = True
    else:
        label = "spoof"
        is_live = False

    return AntiSpoofResult(
        is_live=is_live,
        label=label,
        confidence=best_score if is_live else 1.0 - best_score,
        real_score=best_score,
        details={
            "model": "deeppix",
            "best_score": round(best_score, 4),
            "average_score": round(average_score, 4),
            "live_threshold": live_threshold,
            "uncertain_threshold": uncertain_threshold,
            "scores": [round(score, 4) for score in scores],
        },
    )


# Use: Internal helper for check minifasnet liveness.
# Linked with: check_face_liveness
def _check_minifasnet_liveness(
    session,
    input_name,
    input_shape,
    image_np,
    face_rect,
    real_threshold=DEFAULT_MINIFASNET_REAL_THRESHOLD,
    spoof_threshold=DEFAULT_MINIFASNET_SPOOF_THRESHOLD,
):
    predictions = []

    for margin in (0.85, 0.65, 1.05):
        face_crop = _crop_face(image_np, face_rect, margin=margin)
        if face_crop.size == 0:
            continue

        predictions.append(
            _run_minifasnet_prediction(
                session, input_name, input_shape, face_crop, enhanced=False
            )
        )
        predictions.append(
            _run_minifasnet_prediction(
                session, input_name, input_shape, face_crop, enhanced=True
            )
        )

    if not predictions:
        return AntiSpoofResult(False, "invalid_face_crop", 1.0, 0.0, {})

    labels = [prediction[0] for prediction in predictions]
    confidences = np.array([prediction[1] for prediction in predictions])
    real_scores = np.array([prediction[2] for prediction in predictions])
    probability_vectors = [prediction[3].round(4).tolist() for prediction in predictions]

    label_scores = {}
    for label, confidence in zip(labels, confidences):
        label_scores[label] = label_scores.get(label, 0.0) + float(confidence)

    best_label = max(label_scores, key=label_scores.get)
    best_confidence = float(max(confidences))
    real_score = float(max(real_scores))
    live_votes = sum(label == "real" for label in labels)
    spoof_votes = len(labels) - live_votes
    uncertain_threshold = _get_float_setting(
        "MINIFASNET_UNCERTAIN_THRESHOLD", DEFAULT_MINIFASNET_UNCERTAIN_THRESHOLD
    )
    real_threshold = _get_float_setting("MINIFASNET_REAL_THRESHOLD", real_threshold)
    spoof_threshold = _get_float_setting("MINIFASNET_SPOOF_THRESHOLD", spoof_threshold)

    if live_votes and real_score >= real_threshold:
        label = "real"
        is_live = True
    elif real_score >= uncertain_threshold:
        label = "uncertain"
        is_live = _get_bool_setting("ALLOW_UNCERTAIN_LIVENESS", True)
    else:
        label = "spoof"
        is_live = False

    return AntiSpoofResult(
        is_live=is_live,
        label=label,
        confidence=best_confidence,
        real_score=real_score,
        details={
            "model": "minifasnet",
            "labels": labels,
            "best_label": best_label,
            "best_confidence": round(best_confidence, 4),
            "real_score": round(real_score, 4),
            "real_threshold": real_threshold,
            "uncertain_threshold": uncertain_threshold,
            "spoof_threshold": spoof_threshold,
            "spoof_votes": spoof_votes,
            "live_votes": live_votes,
            "probabilities": probability_vectors,
        },
    )


# Use: Internal helper for predict custom live score.
# Linked with: _check_custom_liveness
def _predict_custom_live_score(model, face_crop):
    features = extract_liveness_features(face_crop).reshape(1, -1)
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(features)[0]
        classes = list(getattr(model, "classes_", [0, 1]))
        live_index = classes.index(1) if 1 in classes else int(np.argmax(classes))
        return float(probabilities[live_index])

    prediction = model.predict(features)[0]
    return 1.0 if int(prediction) == 1 else 0.0


# Use: Internal helper for predict attack type.
# Linked with: _check_custom_liveness
def _predict_attack_type(attack_type_model, face_crop):
    if attack_type_model is None:
        return None, None

    features = extract_liveness_features(face_crop).reshape(1, -1)
    prediction = str(attack_type_model.predict(features)[0])
    if not hasattr(attack_type_model, "predict_proba"):
        return prediction, None

    probabilities = attack_type_model.predict_proba(features)[0]
    classes = [str(label) for label in attack_type_model.classes_]
    prediction_index = classes.index(prediction)
    return prediction, float(probabilities[prediction_index])


# Use: Internal helper for check custom liveness.
# Linked with: check_face_liveness
def _check_custom_liveness(artifact, image_np, face_rect):
    model = artifact["model"]
    attack_type_model = artifact.get("attack_type_model")
    live_threshold = _get_float_setting(
        "CUSTOM_LIVENESS_THRESHOLD",
        float(artifact.get("threshold", DEFAULT_CUSTOM_LIVENESS_THRESHOLD)),
    )
    uncertain_threshold = _get_float_setting(
        "CUSTOM_LIVENESS_UNCERTAIN_THRESHOLD", DEFAULT_CUSTOM_UNCERTAIN_THRESHOLD
    )
    scores = []
    attack_predictions = []

    for margin in (0.35, 0.45, 0.55, 0.65, 0.75):
        face_crop = _crop_face(image_np, face_rect, margin=margin)
        if face_crop.size == 0:
            continue

        live_score = _predict_custom_live_score(model, face_crop)
        scores.append(live_score)

        attack_type, attack_confidence = _predict_attack_type(attack_type_model, face_crop)
        if attack_type is not None:
            attack_predictions.append((attack_type, attack_confidence, live_score))

        for b, c in [(1.18, 1.12), (0.9, 1.2), (1.3, 0.9)]:
            enhanced_image = Image.fromarray(face_crop).convert("RGB")
            enhanced_image = ImageOps.autocontrast(enhanced_image, cutoff=1)
            enhanced_image = ImageEnhance.Brightness(enhanced_image).enhance(b)
            enhanced_image = ImageEnhance.Contrast(enhanced_image).enhance(c)
            enhanced_np = np.asarray(enhanced_image)

            live_score = _predict_custom_live_score(model, enhanced_np)
            scores.append(live_score)

            attack_type, attack_confidence = _predict_attack_type(attack_type_model, enhanced_np)
            if attack_type is not None:
                attack_predictions.append((attack_type, attack_confidence, live_score))

    if not scores:
        return AntiSpoofResult(False, "invalid_face_crop", 1.0, 0.0, {})

    best_score = float(max(scores))
    average_score = float(np.mean(scores))

    combined_score = (best_score * 0.6) + (average_score * 0.4)

    if combined_score >= live_threshold:
        label = "real"
        is_live = True
    elif combined_score >= uncertain_threshold:
        label = "uncertain"
        is_live = _get_bool_setting("ALLOW_UNCERTAIN_LIVENESS", False)
    else:
        label = "spoof"
        is_live = False

    attack_type = None
    attack_confidence = None
    if attack_predictions and not is_live:
        attack_scores = {}
        attack_confidences = {}
        for predicted_type, confidence, l_score in attack_predictions:
            score = 1.0 - l_score
            if confidence is not None:
                score *= confidence
            attack_scores[predicted_type] = attack_scores.get(predicted_type, 0.0) + score
            if confidence is not None:
                attack_confidences.setdefault(predicted_type, []).append(confidence)

        attack_type = max(attack_scores, key=attack_scores.get)
        confidences = attack_confidences.get(attack_type, [])
        if confidences:
            attack_confidence = float(max(confidences))

    return AntiSpoofResult(
        is_live=is_live,
        label=label,
        confidence=combined_score if is_live else 1.0 - combined_score,
        real_score=combined_score,
        details={
            "model": artifact.get("model_type", "custom_liveness"),
            "best_score": round(best_score, 4),
            "average_score": round(average_score, 4),
            "combined_score": round(combined_score, 4),
            "live_threshold": live_threshold,
            "uncertain_threshold": uncertain_threshold,
            "attack_type": attack_type,
            "attack_confidence": (
                round(attack_confidence, 4)
                if attack_confidence is not None
                else None
            ),
            "attack_type_model": attack_type_model is not None,
            "scores": [round(s, 4) for s in scores],
        },
    )


# Use: Main anti-spoofing entry point for one detected face.
# Called from: face_pipeline._encode_live_faces after dlib finds a face and before face embedding is generated.
# Order: custom joblib liveness model if present, otherwise ONNX anti-spoofing model.
def check_face_liveness(
    image_np,
    face_rect,
    real_threshold=DEFAULT_MINIFASNET_REAL_THRESHOLD,
    spoof_threshold=DEFAULT_MINIFASNET_SPOOF_THRESHOLD,
):
    custom_model = load_custom_liveness_model()
    if custom_model is not None:
        return _check_custom_liveness(custom_model, image_np, face_rect)

    session, input_name, input_shape, output_names, model_kind = (
        load_anti_spoofing_session()
    )
    if model_kind == "deeppix":
        return _check_deeppix_liveness(
            session, input_name, input_shape, output_names, image_np, face_rect
        )
    return _check_minifasnet_liveness(
        session,
        input_name,
        input_shape,
        image_np,
        face_rect,
        real_threshold=real_threshold,
        spoof_threshold=spoof_threshold,
    )
