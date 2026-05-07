import cv2
import numpy as np
import onnxruntime as ort
import streamlit as st
import gc
import os
import logging


logger = logging.getLogger(__name__)


@st.cache_resource
def load_antispoof_model():
    model_path = os.path.join("src", "models", "antispoof.onnx")
    if not os.path.exists(model_path):
        logger.warning("Anti-spoof model file not found at %s", model_path)
        return None
    try:
        session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        logger.info("Anti-spoof model loaded")
        return session
    except Exception as e:
        logger.exception("Anti-spoof model load error: %s", e)
        return None


def _crop_face_with_scale(image_bgr, bbox, scale=2.7):
    """
    Model needs context (background) to detect edges of paper/screens.
    """
    h, w, _ = image_bgr.shape
    x1, y1, x2, y2 = bbox
    cw, ch = (x1 + x2) // 2, (y1 + y2) // 2
    fw, fh = x2 - x1, y2 - y1
    side = int(max(fw, fh) * scale)
    nx1 = max(0, cw - side // 2)
    ny1 = max(0, ch - side // 2)
    nx2 = min(w, nx1 + side)
    ny2 = min(h, ny1 + side)
    return image_bgr[ny1:ny2, nx1:nx2]


def _apply_clahe(face_bgr):
    """Normalize lighting for better consistency"""
    lab = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def check_liveness(face_crop_rgb, bbox=None, full_image_rgb=None):
    face_resized = None
    face_tensor = None

    try:
        session = load_antispoof_model()
        if session is None:
            return True  # Fallback

        # --- STEP 1: SCALE CROP (2.7 is standard for this model) ---
        if bbox is not None and full_image_rgb is not None:
            # Model v2 needs wider context (background edges) to detect screens/paper
            full_bgr = cv2.cvtColor(full_image_rgb, cv2.COLOR_RGB2BGR)
            face_to_process = _crop_face_with_scale(full_bgr, bbox, scale=2.7)
        else:
            face_to_process = cv2.cvtColor(face_crop_rgb, cv2.COLOR_RGB2BGR)

        if face_to_process.size == 0:
            return False

        # --- STEP 2: ENHANCE & RESIZE ---
        face_enhanced = _apply_clahe(face_to_process)
        face_resized = cv2.resize(face_enhanced, (80, 80))

        # --- STEP 3: PREPARE TENSOR (Standard Normalization) ---
        # Note: Kuch Silent-Face versions RGB order aur ImageNet Mean/Std mangte hain
        face_final_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
        face_input = face_final_rgb.astype(np.float32) / 255.0

        # Mean/Std subtraction (Crucial step)
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        face_input = (face_input - mean) / std

        # (H, W, C) -> (1, C, H, W)
        face_tensor = np.transpose(face_input, (2, 0, 1))
        face_tensor = np.expand_dims(face_tensor, axis=0)

        # --- STEP 4: INFERENCE ---
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        raw_scores = session.run([output_name], {input_name: face_tensor})[0][0]

        # --- STEP 5: SOFTMAX & CLASS INDICES ---
        exp_scores = np.exp(raw_scores - np.max(raw_scores))
        probs = exp_scores / np.sum(exp_scores)

        # Index Mapping for Silent-Face-Anti-Spoofing V2:
        # Index 1 = Real Face ✅ (Standard)
        # Index 0 = Paper ❌
        # Index 2 = Screen ❌

        # TEST: Agar abhi bhi 90%+ Screen dikhaye, toh probs[1] aur probs[0] swap karke dekhna
        fake_paper  = float(probs[1])
        real_score  = float(probs[2])
        fake_screen = float(probs[0])

        logger.info(
            "[AI Liveness] Real: %.1f%% | Paper: %.1f%% | Screen: %.1f%%",
            real_score * 100,
            fake_paper * 100,
            fake_screen * 100,
        )

        threshold = 0.50 # Testing ke liye thoda low rakha hai
        is_real = real_score >= threshold
        logger.info("[AI Liveness] %s", "REAL" if is_real else "FAKE")

        return is_real

    except Exception as e:
        logger.exception("[Liveness Error]: %s", e)
        return False
    finally:
        del face_resized, face_tensor
        gc.collect()


