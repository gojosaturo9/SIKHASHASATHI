---
title: SIKHASHASASATHI
sdk: docker
app_port: 7860
---

# SIKHASHASASATHI - AI-Powered Attendance Platform

SIKHASHASASATHI is an AI-powered attendance management platform built for colleges and coaching institutes. It combines face recognition, liveness verification, role-based dashboards, Supabase cloud storage, automated reports, email notifications, and AI-assisted insights in one Streamlit application.

The goal of the project is to reduce manual attendance work, make attendance records easier to manage, and reduce proxy attendance through live biometric verification.

## Live Demo

Add these links after deployment:

```text
Live App: <your-deployed-app-link>
GitHub: <your-github-repository-link>
Demo Video: <your-demo-video-link>
```

## Key Features

- Admin, Teacher, and Student portals
- Face recognition attendance using dlib embeddings
- Anti-spoofing verification using an ONNX model
- Blink/liveness challenge to reduce photo-based proxy attendance
- Student registration with face and voice profile support
- Teacher subject management and attendance capture
- Student dashboard with attendance percentage and subject-wise records
- Admin dashboard for managing teachers, students, records, and announcements
- Supabase PostgreSQL backend with RLS policy scripts
- AI insights and voice/RAG chatbot support
- Attendance reports, feedback handling, and email notifications
- Custom Streamlit UI with dark dashboard styling

## Tech Stack

| Area | Technology |
| --- | --- |
| App Framework | Streamlit |
| Language | Python |
| Database | Supabase PostgreSQL |
| Face Recognition | dlib, face-recognition models, scikit-learn |
| Anti-Spoofing | ONNX Runtime |
| Image Processing | OpenCV, Pillow, NumPy |
| Voice / Audio | librosa, soundfile, Torch |
| AI Features | Google Generative AI |
| Data and Reports | pandas |
| Deployment | Docker, Hugging Face Spaces / Render |

## Project Structure

```text
AI-powered-attendance-platform/
+-- app.py
+-- requirements.txt
+-- Dockerfile
+-- README.md
+-- PROJECT_GUIDE.md
+-- TECHNOLOGY_SCRIPT.md
+-- supabase_*_migration.sql
+-- src/
|   +-- components/
|   +-- database/
|   +-- model/
|   +-- pipelines/
|   +-- screens/
|   +-- ui/
|   +-- utils/
|   +-- voice_rag/
+-- docs/
```

## Main Modules

- `app.py` routes users to the home page, teacher portal, student portal, and admin dashboard.
- `src/screens/` contains Admin, Teacher, Student, and Home screens.
- `src/pipelines/face_pipeline.py` handles face detection, embeddings, recognition, and attendance prediction.
- `src/pipelines/anti_spoofing_pipeline.py` runs ONNX-based anti-spoofing checks.
- `src/database/` manages Supabase configuration and database operations.
- `src/components/` contains reusable Streamlit dialogs and UI components.
- `src/voice_rag/` contains the voice assistant and retrieval-based chatbot flow.

## Local Setup

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd AI-powered-attendance-platform
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

For macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If `dlib` installation fails on Windows, install Visual Studio Build Tools or use a Python version that supports available prebuilt wheels.

### 4. Configure secrets

Create:

```text
.streamlit/secrets.toml
```

Add:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-supabase-anon-key"
SUPABASE_SERVICE_ROLE_KEY = "your-supabase-service-role-key"
ADMIN_PASSWORD = "your-admin-password"

SENDER_EMAIL = "your-email@example.com"
SENDER_PASSWORD = "your-email-app-password"

GOOGLE_API_KEY = "your-google-generative-ai-key"
SIKHASHASASATHI_APP_URL = "https://your-deployed-app-link"
```

Do not commit `.streamlit/secrets.toml` to GitHub.

### 5. Set up Supabase

Create a Supabase project and run these SQL files in the Supabase SQL Editor:

```text
supabase_email_automation_migration.sql
supabase_feedback_migration.sql
supabase_rls_policies.sql
supabase_student_registration_rls.sql
supabase_zero_trust_migration.sql
```

Then copy your Supabase project URL, anon key, and service role key into your deployment secrets.

### 6. Run locally

```bash
streamlit run app.py
```

Local URL:

```text
http://localhost:8501
```

## Free Deployment Recommendation

For this project, the best free deployment target is:

```text
Hugging Face Spaces with Docker
```

Reason: this app has heavier ML dependencies such as `dlib`, OpenCV, ONNX Runtime, and Torch/audio packages. Streamlit Community Cloud is simpler, but it may fail because of memory or dependency limits. Hugging Face Spaces is better suited for AI/ML portfolio demos.

## Deploy on Hugging Face Spaces

1. Push this project to GitHub.
2. Go to `https://huggingface.co/spaces`.
3. Click `Create new Space`.
4. Use these settings:

```text
Space name: sikhashasasathi
SDK: Docker
Hardware: CPU Basic
Visibility: Public
```

5. Upload or push this project to the Hugging Face Space repository.
6. In the Space settings, add these secrets:

```text
SUPABASE_URL
SUPABASE_KEY
SUPABASE_SERVICE_ROLE_KEY
ADMIN_PASSWORD
SENDER_EMAIL
SENDER_PASSWORD
GOOGLE_API_KEY
SIKHASHASASATHI_APP_URL
```

7. Wait for the Docker build to finish.
8. Open the live Space URL and test Admin, Teacher, and Student flows.

## Docker Run Command

The included Dockerfile starts the app using:

```bash
streamlit run app.py --server.port=${PORT:-7860} --server.address=0.0.0.0
```

For local Docker testing:

```bash
docker build -t sikhashasasathi .
docker run -p 7860:7860 --env-file .env sikhashasasathi
```

## Security Notes

- Never commit `.streamlit/secrets.toml`, `.env`, Supabase keys, email passwords, or API keys.
- Use Supabase service role keys only in trusted server-side deployments.
- Review Supabase RLS policies before deploying with real student data.
- Get proper user consent before collecting or processing biometric data.
- Use demo data when sharing the app publicly with recruiters.

## Resume Highlights

**Project:** SIKHASHASASATHI - AI-Powered Attendance Platform

Suggested resume points:

- Built a role-based AI attendance platform using Python, Streamlit, Supabase, and computer vision.
- Implemented face recognition with dlib embeddings and anti-spoofing verification using ONNX Runtime.
- Designed Admin, Teacher, and Student portals for account management, subject handling, attendance tracking, and reports.
- Integrated Supabase PostgreSQL with RLS scripts for secure cloud-backed data storage.
- Added AI insights, voice chatbot support, automated email notifications, and attendance analytics.

## Future Improvements

- Add automated tests for database and attendance flows
- Add screenshots and a demo video
- Add PDF export for attendance reports
- Add Docker image publishing through GitHub Actions
- Improve biometric privacy and consent documentation

## License

This project is intended for academic, portfolio, and learning purposes. Add a license before using it in production or distributing it publicly.
