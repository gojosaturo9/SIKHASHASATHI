import io

import numpy as np
import streamlit as st


"""
Voice biometric helpers.

Debugging map:
- _load_voice_dependencies: imports audio libraries and tells callers which
  embedding backend is available.
- _read_audio: decodes Streamlit audio bytes into mono 16 kHz samples.
- get_voice_embedding: converts one registration audio clip into a stored vector.
- identify_speaker: compares a new vector with stored student vectors.
- process_bulk_audio: splits classroom audio into speech chunks and marks matches.
"""


class VoicePipelineSetupError(RuntimeError):
    pass


# Use: Internal helper for load voice dependencies.
# Linked with: get_voice_embedding, load_voice_encoder, process_bulk_audio
def _load_voice_dependencies():
    """Load voice libraries without making resemblyzer/librosa mandatory on Windows."""
    missing = []

    try:
        import soundfile as sf
    except ModuleNotFoundError:
        sf = None
        missing.append("soundfile")

    try:
        from resemblyzer import VoiceEncoder, preprocess_wav
    except (ModuleNotFoundError, ImportError):
        VoiceEncoder = None
        preprocess_wav = None

    if missing:
        raise VoicePipelineSetupError(
            "Voice AI dependencies are missing: "
            + ", ".join(missing)
            + ". Install project requirements to enable voice attendance."
        )

    return sf, VoiceEncoder, preprocess_wav


# Use: Loads voice encoder resources or configuration.
# Linked with: get_voice_embedding, process_bulk_audio
@st.cache_resource
def load_voice_encoder():
    """Cache the resemblyzer neural encoder when its native dependencies are installed."""
    _, VoiceEncoder, _ = _load_voice_dependencies()
    if VoiceEncoder is None:
        return None
    return VoiceEncoder()


# Use: Internal helper for resample linear.
# Linked with: _read_audio
def _resample_linear(audio, original_sr, target_sr=16000):
    """Resample audio with numpy interpolation to avoid slow optional audio backends."""
    if original_sr == target_sr:
        return audio.astype(np.float32), target_sr
    duration = len(audio) / float(original_sr)
    old_times = np.linspace(0, duration, num=len(audio), endpoint=False)
    new_len = max(1, int(duration * target_sr))
    new_times = np.linspace(0, duration, num=new_len, endpoint=False)
    return np.interp(new_times, old_times, audio).astype(np.float32), target_sr


# Use: Internal helper for read audio.
# Linked with: get_voice_embedding, process_bulk_audio
def _read_audio(sf, audio_bytes, target_sr=16000):
    """Decode recorded audio bytes into mono samples."""
    audio, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return _resample_linear(audio, sr, target_sr)


# Use: Internal helper for normalize embedding.
# Linked with: _fallback_embedding, get_voice_embedding, process_bulk_audio
def _normalize_embedding(values):
    """Normalize vectors so dot product works as cosine-like similarity."""
    embedding = np.asarray(values, dtype=np.float32)
    norm = np.linalg.norm(embedding)
    if norm == 0:
        return embedding.tolist()
    return (embedding / norm).tolist()


# Use: Internal helper for fallback embedding.
# Linked with: get_voice_embedding, process_bulk_audio
def _fallback_embedding(audio, sr):
    """Fast fallback voice profile using numpy spectral statistics."""
    if len(audio) < sr * 0.5:
        return None

    audio = np.asarray(audio, dtype=np.float32)
    audio = audio - float(np.mean(audio))
    peak = float(np.max(np.abs(audio)))
    if peak <= 1e-6:
        return None
    audio = audio / peak

    frame_size = int(sr * 0.05)
    hop = int(sr * 0.025)
    if len(audio) < frame_size:
        return None

    windows = []
    for start in range(0, len(audio) - frame_size + 1, hop):
        frame = audio[start : start + frame_size] * np.hanning(frame_size)
        spectrum = np.abs(np.fft.rfft(frame))
        total = float(np.sum(spectrum)) + 1e-8
        freqs = np.fft.rfftfreq(frame_size, d=1.0 / sr)
        centroid = float(np.sum(freqs * spectrum) / total)
        bandwidth = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * spectrum) / total))
        rolloff_idx = int(np.searchsorted(np.cumsum(spectrum), total * 0.85))
        rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])
        energy = float(np.mean(frame**2))
        zero_crossings = float(np.mean(np.abs(np.diff(np.signbit(frame)))))
        band_edges = np.linspace(0, len(spectrum), 9, dtype=int)
        band_energy = [
            float(np.mean(spectrum[band_edges[i] : band_edges[i + 1]]))
            for i in range(len(band_edges) - 1)
        ]
        windows.append([centroid, bandwidth, rolloff, energy, zero_crossings, *band_energy])

    matrix = np.asarray(windows, dtype=np.float32)
    features = np.concatenate([matrix.mean(axis=0), matrix.std(axis=0)])
    return _normalize_embedding(features)


# Use: Fetches voice embedding data for the app flow.
# Linked with: student_screen
def get_voice_embedding(audio_bytes):
    """Create one stored voice vector from Streamlit audio bytes."""
    try:
        sf, _, preprocess_wav = _load_voice_dependencies()
        encoder = load_voice_encoder()

        audio, sr = _read_audio(sf, audio_bytes, target_sr=16000)
        if encoder is not None and preprocess_wav is not None:
            wav = preprocess_wav(audio)
            embedding = encoder.embed_utterance(wav)
            return _normalize_embedding(embedding)

        embedding = _fallback_embedding(audio, sr)
        if embedding is None:
            st.error("Voice recording is too short. Please record at least 1 second clearly.")
        return embedding
    except VoicePipelineSetupError as e:
        st.error(str(e))
        return None
    except Exception as exc:
        st.error(f"Voice recognition failed. Please try again with a clearer recording. Detail: {exc}")
        return None


# Use: Handles identify speaker behavior in this module.
# Linked with: process_bulk_audio
def identify_speaker(new_embedding, candidates_dict, threshold=0.65):
    """Return the student id with the highest similarity above the threshold."""
    if new_embedding is None or not candidates_dict:
        return None, 0.0

    best_sid = None
    best_score = -1.0

    for sid, stored_embedding in candidates_dict.items():
        if stored_embedding:
            similarity = float(np.dot(new_embedding, stored_embedding))
            if similarity > best_score:
                best_score = similarity
                best_sid = sid

    if best_score >= threshold:
        return best_sid, best_score

    return None, best_score


# Use: Processes bulk audio input for the workflow.
# Linked with: voice_attendance_dialog
def process_bulk_audio(audio_bytes, candidates_dict, threshold=0.65):
    """Detect enrolled speakers from one classroom recording."""
    try:
        sf, _, preprocess_wav = _load_voice_dependencies()
        encoder = load_voice_encoder()

        audio, sr = _read_audio(sf, audio_bytes, target_sr=16000)
        active = np.abs(audio) > max(0.01, float(np.max(np.abs(audio))) * 0.08)
        if not np.any(active):
            segments = []
        else:
            active_indices = np.where(active)[0]
            segments = [(int(active_indices[0]), int(active_indices[-1]) + 1)]

        identified_results = {}

        for start, end in segments:
            if (end - start) < sr * 0.5:
                continue

            segment_audio = audio[start:end]
            if encoder is not None and preprocess_wav is not None:
                wav = preprocess_wav(segment_audio)
                embedding = _normalize_embedding(encoder.embed_utterance(wav))
            else:
                embedding = _fallback_embedding(segment_audio, sr)

            sid, score = identify_speaker(embedding, candidates_dict, threshold)

            if sid and (sid not in identified_results or score > identified_results[sid]):
                identified_results[sid] = score

        return identified_results
    except VoicePipelineSetupError as e:
        st.error(str(e))
        return {}
    except Exception:
        st.error("Bulk voice processing failed. Please try again with a clearer recording.")
        return {}
