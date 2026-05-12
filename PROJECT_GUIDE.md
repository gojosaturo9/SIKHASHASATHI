# SIKHASHASASATHI | Project Guide & Interview Preparation

This document provides a comprehensive overview of the technologies used in the **SIKHASHASASATHI** AI-powered attendance platform, their implementation, and a guide for interviews and error management.

---

## 🚀 Technology Stack: The "What, Where, and Why"

### 1. Python (The Core Engine)
*   **Where used:** Powers the full application logic, AI pipelines (`src/pipelines/`), database interactions (`src/database/`), and report generation.
*   **Why used:** Python is the industry standard for AI and Data Science. It offers mature libraries for image processing and seamless integration with machine learning models.
*   **Why it's better:** Compared to Java or PHP, Python's syntax is concise, making the complex logic of face embeddings and liveness detection easier to maintain and faster to develop.

### 2. Streamlit (The UI Framework)
*   **Where used:** All frontend screens (`src/screens/`) and interactive components like camera/audio input.
*   **Why used:** It allows building data-rich web apps entirely in Python. It handles the "reactive" state management automatically.
*   **Why it's better:** Traditional web development requires a separate Frontend (React/Angular) and Backend (Node/Django). Streamlit merges them, allowing AI code to run directly in the same process as the UI, reducing latency and deployment complexity.

### 3. Supabase (The Database & Backend)
*   **Where used:** Storing student/teacher profiles, subject enrollments, and attendance logs.
*   **Why used:** It provides a cloud-hosted PostgreSQL database with a powerful real-time API.
*   **Why it's better:** Unlike a local SQLite database, Supabase allows multi-user access from different devices. It also handles authentication and scaling much better than a traditional self-hosted SQL server.

### 4. dlib & Face Recognition (The Vision AI)
*   **Where used:** `src/pipelines/face_pipeline.py`. Detects faces, extracts 68-point landmarks, and generates 128D face embeddings.
*   **Why used:** dlib is highly accurate for landmark detection (essential for blink detection) and provides stable face embeddings.
*   **Why it's better:** Simple pixel-matching fails with lighting changes. dlib's embeddings are "distance-based," meaning they recognize the same person even with different hair, glasses, or expressions.

### 5. ONNX Runtime (Anti-Spoofing Inference)
*   **Where used:** `src/pipelines/anti_spoofing_pipeline.py`. Runs the `antispoof.onnx` model.
*   **Why used:** ONNX is a cross-platform format for ML models. The runtime is extremely fast and light on CPU.
*   **Why it's better:** Running a full PyTorch/TensorFlow model for every frame is too heavy for a standard PC. ONNX Runtime provides high-speed "inference" (prediction) without needing a GPU.

---

## 🎤 PPT Script / Presentation Flow

1.  **Slide 1: Introduction:** "Welcome to **SIKHASHASASATHI**, an AI-driven solution to the manual attendance problem in colleges."
2.  **Slide 2: The Problem:** "Manual registers are slow, prone to 'proxy' attendance, and hard to digitize."
3.  **Slide 3: The Solution (AI):** "We use a 4-layer verification system: Metadata check, Face Liveness, Roster Validation, and a two-step Blink Challenge for students."
4.  **Slide 4: Technology:** "Built on Python and Streamlit for speed, Supabase for cloud data, and dlib for biometric accuracy."
5.  **Slide 5: Live Demo (Student):** "Show the 'Eyes Open' -> 'Blink' transition. This proves the user is a live human, not a photo."
6.  **Slide 6: Conclusion:** "Efficient, Secure, and Scalable for modern educational institutions."

---

## ❓ Common Interview Questions

**Q: How do you prevent someone from showing a photo of a student?**
*   **A:** We use two layers: 
    1.  **Liveness Detection:** An ONNX model analyzes texture and depth to distinguish a screen/paper from a human face.
    2.  **Blink Challenge:** The student must first show their eyes open, then capture a frame while blinking. A static photo cannot change states.

**Q: Why use face embeddings instead of storing images?**
*   **A:** Privacy and Speed. We convert a face into 128 numbers (an embedding). We store only these numbers. Comparing numbers is mathematically faster than comparing millions of pixels.

**Q: What happens if the internet is slow?**
*   **A:** We use `@st.cache_data` in `src/screens/student_screen.py` to cache database results for 30 seconds. This makes the UI feel "instant" even if the database response takes a moment.

**Q: Why choose Streamlit over React?**
*   **A:** For an AI-heavy project, Streamlit is better because it keeps the AI model and the UI in the same Python environment. This avoids the overhead of creating complex APIs just to pass image data between a JS frontend and a Python backend.

---

## 🛠️ Error Handling & Troubleshooting

### Total Common Errors & Solutions:

1.  **ModuleNotFoundError (e.g., websockets, supafunc):**
    *   **Cause:** Missing or incompatible library versions in the virtual environment.
    *   **Fix:** Always use the specific versions in `requirements.txt`. For `websockets`, version `13.1` is used to maintain compatibility with `realtime`.

2.  **ImportError (e.g., USER_AGENT missing):**
    *   **Cause:** Circular imports or library updates that moved internal classes.
    *   **Fix:** Downgrade the library to a known stable version or use `lazy-loading` (importing inside the function) to avoid top-level conflicts.

3.  **Supabase Config Error:**
    *   **Cause:** Missing `SUPABASE_URL` or `KEY` in `.streamlit/secrets.toml`.
    *   **Fix:** The project has a built-in `render_supabase_setup()` helper that detects this and shows a user-friendly setup guide instead of crashing.

4.  **Face/Blink Detection Failure:**
    *   **Cause:** Poor lighting, face too far, or missing `dlib` models.
    *   **Fix:** 
        *   Check `src/pipelines/face_pipeline.py` logs.
        *   We implemented `_enhance_low_light` to automatically adjust brightness before AI processing.
        *   We provide specific feedback (e.g., "Eyes Closed", "No Face Found") so the user knows exactly why it failed.

5.  **PyArrow Serialization Error:**
    *   **Cause:** Streamlit's data table doesn't like mixed data types in a column (e.g., Int and String).
    *   **Fix:** Force column types using `.astype(str)` or ensure data consistency before passing DataFrames to `st.dataframe`.

---
*Created for the **SIKHASHASASATHI** Project - 2026*
