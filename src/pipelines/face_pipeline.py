from contextlib import contextmanager
import os
import sys

import numpy as np
import streamlit as st
from PIL import Image, ImageEnhance, ImageOps
from src.utils.secrets import get_secret

# ye line 9 se 22 size resize krne ke liye hai ye photo is size(1240x720) se 640px ki size kr dega eske wajah se app 3x to 4x fast ho jayega
# Use: Internal helper for resize for detection.
# Linked with: _encode_live_faces
def _resize_for_detection(image_np, max_size=640):
    h, w = image_np.shape[:2]
    if max(h, w) <= max_size:
        return image_np
    scale = max_size / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = Image.fromarray(image_np).resize((new_w, new_h), Image.LANCZOS)
    return np.asarray(resized)
from src.pipelines.anti_spoofing_pipeline import (
    AntiSpoofResult,
    AntiSpoofingSetupError,
    check_face_liveness,
)


class FacePipelineSetupError(RuntimeError):
    pass


# Use: Internal helper for suppress native output.
# Linked with: _detect_faces, _encode_live_faces, load_dlib_models
@contextmanager
def _suppress_native_output():
    """
    Suppress noisy native library stdout/stderr safely.
    """

    devnull = open(os.devnull, "w")

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        sys.stdout = devnull
        sys.stderr = devnull
        yield

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        devnull.close()
# @contextmanager
# def _suppress_native_output():
#     try:
#         sys.stdout.flush()
#     except Exception:
#         pass
#     try:
#         sys.stderr.flush()
#     except Exception:
#         pass

#     stdout_fd = None
#     stderr_fd = None

#     try:
#         stdout_fd = os.dup(1)
#         stderr_fd = os.dup(2)
#         with open(os.devnull, "w", encoding="utf-8") as devnull:
#             os.dup2(devnull.fileno(), 1)
#             os.dup2(devnull.fileno(), 2)
#             yield
#     except Exception:
#         yield
#     finally:
#         try:
#             sys.stdout.flush()
#         except Exception:
#             pass
#         try:
#             sys.stderr.flush()
#         except Exception:
#             pass
#         if stdout_fd is not None:
#             os.dup2(stdout_fd, 1)
#             os.close(stdout_fd)
#         if stderr_fd is not None:
#             os.dup2(stderr_fd, 2)
#             os.close(stderr_fd)


# Use: Internal helper for load face dependencies.
# Linked with: get_trained_model, load_dlib_models
def _load_face_dependencies():
    missing = []

    try:
        import dlib
    except ModuleNotFoundError:
        dlib = None
        missing.append("dlib")

    try:
        import face_recognition_models
    except ModuleNotFoundError:
        face_recognition_models = None
        missing.append("face_recognition_models")

    try:
        from sklearn.svm import SVC
    except ModuleNotFoundError:
        SVC = None
        missing.append("scikit-learn")

    if missing:
        raise FacePipelineSetupError(
            "Face AI dependencies are missing: "
            + ", ".join(missing)
            + ". Install project requirements in a Python 3.11/3.12 environment for full face recognition support."
        )

    return dlib, face_recognition_models, SVC


# Use: Loads dlib models resources or configuration.
# Linked with: _detect_faces, _encode_live_faces
@st.cache_resource
def load_dlib_models():
    dlib, face_recognition_models, _ = _load_face_dependencies()
    with _suppress_native_output():
        detector = dlib.get_frontal_face_detector()

        sp = dlib.shape_predictor(face_recognition_models.pose_predictor_model_location())

        facerec = dlib.face_recognition_model_v1(
            face_recognition_models.face_recognition_model_location()
        )

    return detector, sp, facerec


# Use: Finds face rectangles with dlib HOG detector, then retries with brighter/contrast-enhanced image.
# Called from: _encode_live_faces before liveness and face embedding generation.
def _detect_faces(image_np, upsample_times=2):
    detector, _, _ = load_dlib_models()
    with _suppress_native_output():
        faces = detector(image_np, upsample_times)
    if faces:
        return faces

    enhanced_image = Image.fromarray(image_np.astype(np.uint8)).convert("RGB")
    enhanced_image = ImageOps.autocontrast(enhanced_image, cutoff=1)
    enhanced_image = ImageEnhance.Brightness(enhanced_image).enhance(1.2)
    enhanced_image = ImageEnhance.Contrast(enhanced_image).enhance(1.15)
    enhanced_np = np.asarray(enhanced_image)

    with _suppress_native_output():
        faces = detector(enhanced_np, upsample_times)
    if faces:
        return faces

    with _suppress_native_output():
        faces = detector(enhanced_np, upsample_times + 1)
    if faces:
        return faces

    with _suppress_native_output():
        faces = detector(enhanced_np, upsample_times + 2)
    if faces:
        return faces

    # Final pass for small classroom faces. This is slower, so it only runs after cheaper passes fail.
    with _suppress_native_output():
        return detector(enhanced_np, upsample_times + 3)


# Use: Internal helper for face area.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def _face_area(face):
    return max(0, face.right() - face.left()) * max(0, face.bottom() - face.top())


# Use: Internal helper for filter duplicate faces.
# Linked with: _encode_live_faces
def _filter_duplicate_faces(faces, min_center_distance=18):
    filtered = []
    for face in sorted(faces, key=_face_area, reverse=True):
        center = np.array(
            [
                (face.left() + face.right()) / 2,
                (face.top() + face.bottom()) / 2,
            ]
        )
        if all(
            np.linalg.norm(
                center
                - np.array(
                    [
                        (seen.left() + seen.right()) / 2,
                        (seen.top() + seen.bottom()) / 2,
                    ]
                )
            )
            > min_center_distance
            for seen in filtered
        ):
            filtered.append(face)
    return filtered


# Use: Internal helper for get float env.
# Linked with: _should_allow_borderline_liveness, get_zero_trust_settings, predict_attendance
def _get_float_env(name, default):
    try:
        return float(os.environ.get(name) or get_secret(name, default))
    except (TypeError, ValueError):
        return default


# Use: Internal helper for reading boolean debug/config flags from env or Streamlit secrets.
# Linked with: _should_allow_borderline_liveness
def _get_bool_env(name, default=False):
    value = os.environ.get(name)
    if value is None:
        value = get_secret(name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# Use: Internal helper for normalize face embedding.
# Linked with: get_trained_model
def _normalize_face_embedding(embedding):
    if embedding is None:
        return None
    if isinstance(embedding, str) and not embedding.strip():
        return None
    try:
        vector = np.asarray(embedding, dtype=np.float32)
    except (TypeError, ValueError):
        return None
    if vector.ndim != 1 or vector.size != 128:
        return None
    if not np.isfinite(vector).all():
        return None
    return vector


# Use: Internal helper for accept face match.
# Linked with: predict_attendance
def _is_confident_embedding_match(best_distance, second_best_distance, threshold, gap):
    if best_distance > threshold:
        return False
    if gap <= 0:
        return True
    if second_best_distance is None:
        return True
    return (second_best_distance - best_distance) >= gap


# Use: Internal helper for should allow borderline liveness.
# Linked with: _encode_live_faces
def _should_allow_borderline_liveness(liveness, mode):
    if liveness.is_live:
        return True

    if mode == "student" and liveness.real_score >= 0.05:
        return True

    attendance_uncertain_floor = _get_float_env("ATTENDANCE_UNCERTAIN_LIVE_FLOOR", 0.32)
    if mode == "attendance" and liveness.label == "uncertain":
        return float(liveness.real_score) >= attendance_uncertain_floor

    # Temporary debugging switch. Keep this false in real attendance use.
    if mode == "attendance" and liveness.label == "spoof":
        return _get_bool_env("ALLOW_SPOOF_FOR_ATTENDANCE_TEST", False)

    return False
# float(liveness.real_score) >= student_floor

# Use: Detects faces, applies liveness/anti-spoofing, then creates 128-d face embeddings only for accepted live faces.
# Called from: get_face_embeddings for student registration/login and get_live_face_embeddings for attendance.
def _encode_live_faces(image_np, mode="attendance"):
    _, sp, facerec = load_dlib_models()
    image_np = np.ascontiguousarray(image_np.astype(np.uint8))
    max_size = 1280 if mode == "attendance" else 960
    image_np = _resize_for_detection(image_np, max_size=max_size)
    image_np = np.ascontiguousarray(image_np.astype(np.uint8))
    faces = _filter_duplicate_faces(_detect_faces(image_np, upsample_times=2))


    encodings = []
    spoofed_faces = []
    uncertain_faces = []

    for face in faces:
        try:
            with _suppress_native_output():
                liveness = check_face_liveness(image_np, face)
        except AntiSpoofingSetupError as exc:
            raise FacePipelineSetupError(str(exc)) from exc

        if liveness.label == "uncertain":
            uncertain_faces.append(liveness)

        if not _should_allow_borderline_liveness(liveness, mode):
            spoofed_faces.append(liveness)
            continue

        if not liveness.is_live:
            liveness = AntiSpoofResult(
                is_live=True,
                label="uncertain",
                confidence=liveness.confidence,
                real_score=liveness.real_score,
                details={
                    **(liveness.details or {}),
                    "borderline_allowed_for": mode,
                },
            )
            uncertain_faces.append(liveness)

        with _suppress_native_output():
            shape = sp(image_np, face)
            face_descriptor = facerec.compute_face_descriptor(
                image_np, shape, 1
            )  # 128 embedding

        encodings.append(np.array(face_descriptor))

    st.session_state["_last_face_liveness"] = {
        "total_faces": len(faces),
        "live_faces": len(encodings),
        "spoofed_faces": spoofed_faces,
        "uncertain_faces": uncertain_faces,
    }
    return encodings, spoofed_faces, len(faces)


# Use: Fetches face embeddings data for the app flow.
# Linked with: student_screen
def get_face_embeddings(image_np, mode="student"):
    encodings, _, _ = _encode_live_faces(image_np, mode=mode)
    return encodings


# Use: Fetches live face embeddings data for the app flow.
# Linked with: predict_attendance
def get_live_face_embeddings(image_np, mode="attendance"):
    return _encode_live_faces(image_np, mode=mode)


# Use: Fetches trained model data for the app flow.
# Linked with: get_face_profile_count, predict_attendance
@st.cache_resource
def get_trained_model(subject_id=None):  # 🚀 FIX: subject_id ab optional hai
    _, _, SVC = _load_face_dependencies()
    from src.database.db import get_students_for_subject, get_all_students

    X = []
    y = []

    # 🚀 SMART LOGIC:
    # Agar subject_id nahi hai (Student Login), toh saare bacche lao
    if subject_id is None:
        student_db = get_all_students()
    # Agar subject_id hai (Teacher Attendance), toh sirf us class ke bacche lao
    else:
        student_db = get_students_for_subject(subject_id)

    if not student_db:
        return None

    for student in student_db:
        embedding = _normalize_face_embedding(student.get("face_embedding"))
        if embedding is not None:
            X.append(embedding)
            y.append(int(student.get("student_id")))

    if len(X) == 0:
        return None

    clf = SVC(kernel="linear", probability=True, class_weight="balanced", C=100)

    fitted = False
    try:
        clf.fit(X, y)
        fitted = True
    except ValueError:
        pass

    return {"clf": clf, "X": X, "y": y, "students_data": student_db, "fitted": fitted}


# Use: Handles train classifier behavior in this module.
# Linked with: student_screen
def train_classifier():
    st.cache_resource.clear()
    return True


# Use: Fetches face profile count data for the app flow.
# Linked with: student_screen
def get_face_profile_count(subject_id=None):
    model_data = get_trained_model(subject_id)
    if not model_data:
        return 0
    return len(model_data.get("X") or [])


# 🚀 NAYA FIX: Ab predict karte waqt subject_id pass karni hogi
# Use: Handles predict attendance behavior in this module.
# Linked with: student_screen, teacher_tab_take_attendance
def predict_attendance(class_image_np, subject_id=None):
    mode = "student" if subject_id is None else "attendance"
    encodings, _, total_faces = get_live_face_embeddings(class_image_np, mode=mode)

    detected_student = {}

    model_data = get_trained_model(subject_id)

    if not model_data:
        return detected_student, [], total_faces

    clf = model_data["clf"]
    X_train = model_data["X"]
    y_train = model_data["y"]
    fitted = bool(model_data.get("fitted"))

    all_students = sorted(list(set(y_train)))
    # dlib face descriptors usually use about 0.6 as the practical match threshold.
    # Classroom uploads vary in light/angle, so allow a small configurable margin.
    resemblance_threshold = _get_float_env("FACE_RECOGNITION_THRESHOLD", 0.82)
    classifier_margin = _get_float_env("FACE_RECOGNITION_CLASSIFIER_MARGIN", 0.08)
    match_gap = _get_float_env("FACE_RECOGNITION_MATCH_GAP", 0.0)

    for encoding in encodings:
        distances = [
            float(np.linalg.norm(train_embedding - encoding))
            for train_embedding in X_train
        ]
        best_index = int(np.argmin(distances))
        nearest_id = int(y_train[best_index])
        nearest_score = distances[best_index]
        competitor_scores = [
            distance
            for distance, student_id in zip(distances, y_train)
            if int(student_id) != nearest_id
        ]
        second_score = min(competitor_scores) if competitor_scores else None

        predicted_id = None
        predicted_score = None
        if len(all_students) >= 2 and fitted:
            predicted_id = int(clf.predict([encoding])[0])
            candidate_indexes = [
                index
                for index, student_id in enumerate(y_train)
                if int(student_id) == predicted_id
            ]
            if candidate_indexes:
                predicted_score = min(
                    float(np.linalg.norm(X_train[index] - encoding))
                    for index in candidate_indexes
                )

        classifier_agrees = (
            predicted_id is not None
            and predicted_id == nearest_id
            and predicted_score is not None
            and predicted_score <= resemblance_threshold + classifier_margin
        )

        confident_nearest = _is_confident_embedding_match(
            nearest_score,
            second_score,
            resemblance_threshold,
            match_gap,
        )

        if confident_nearest or classifier_agrees:
            detected_student[nearest_id] = {
                "distance": round(nearest_score, 4),
                "match_method": "database_nearest_embedding",
                "classifier_id": predicted_id,
                "classifier_distance": round(predicted_score, 4)
                if predicted_score is not None
                else None,
                "classifier_agrees": classifier_agrees,
                "threshold": resemblance_threshold,
                "second_distance": round(second_score, 4)
                if second_score is not None
                else None,
                "match_gap": match_gap,
            }

    return detected_student, all_students, total_faces
