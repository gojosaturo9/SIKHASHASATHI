<<<<<<< HEAD
# TRUEPRESENCE - AI-Powered Attendance Platform

TRUEPRESENCE is a Streamlit-based attendance management system that uses face recognition, liveness checks, Supabase-backed records, role-based dashboards, and AI-assisted insights to reduce manual attendance work and proxy attendance risk.

The project is built as a practical college attendance platform with separate portals for administrators, teachers, and students.

## Features

- Role-based portals for Admin, Teacher, and Student users
- Face recognition attendance using dlib face embeddings
- Anti-spoofing and liveness verification using an ONNX model
- Blink-based verification flow for stronger live-user checks
- Student registration with face and voice profile support
- Teacher subject management and attendance capture
- Student attendance dashboard with subject-wise summaries
- Admin tools for managing teachers, students, records, and announcements
- Supabase PostgreSQL backend with Row Level Security policy scripts
- AI insights and voice/RAG chatbot support
- Attendance reports, feedback handling, and email notifications
- Streamlit UI with custom dark theme styling

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend / App UI | Streamlit |
| Language | Python |
| Database / Backend | Supabase PostgreSQL |
| Face Recognition | dlib, face-recognition models, scikit-learn |
| Anti-Spoofing | ONNX Runtime |
| Image Processing | OpenCV, Pillow, NumPy |
| Voice / Audio | librosa, soundfile, Torch |
| AI Features | Google Generative AI |
| Reports / Data | pandas |

## Project Structure

```text
AI-powered-attendance-platform/
+-- app.py
+-- requirements.txt
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

- `app.py` routes users between the home page, teacher portal, student portal, and admin dashboard.
- `src/screens/` contains the Admin, Teacher, Student, and Home UI screens.
- `src/pipelines/face_pipeline.py` handles face detection, embeddings, recognition, and attendance prediction.
- `src/pipelines/anti_spoofing_pipeline.py` runs anti-spoofing checks using the ONNX model.
- `src/database/` manages Supabase configuration and database operations.
- `src/components/` contains reusable Streamlit UI dialogs and dashboard components.
- `src/voice_rag/` contains the voice assistant and retrieval-based chatbot flow.

## Local Setup

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd AI-powered-attendance-platform
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
.venv\Scripts\activate
```

For macOS/Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If `dlib` installation fails on Windows, install Visual Studio Build Tools or use a Python version compatible with available prebuilt wheels.

### 4. Configure secrets

Create this file:

```text
.streamlit/secrets.toml
```

Add your local credentials:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-supabase-anon-key"
SUPABASE_SERVICE_ROLE_KEY = "your-supabase-service-role-key"
ADMIN_PASSWORD = "your-admin-password"

SENDER_EMAIL = "your-email@example.com"
SENDER_PASSWORD = "your-email-app-password"

GOOGLE_API_KEY = "your-google-generative-ai-key"
```

Do not commit `.streamlit/secrets.toml` to GitHub.

### 5. Set up Supabase

Create a Supabase project and run the SQL files from this repository in the Supabase SQL Editor:

```text
supabase_email_automation_migration.sql
supabase_feedback_migration.sql
supabase_rls_policies.sql
supabase_student_registration_rls.sql
supabase_zero_trust_migration.sql
```

Run the migration files carefully and confirm that the required tables, policies, and permissions are created before using the app.

### 6. Run the app

```bash
streamlit run app.py
```

The app should open at:

```text
http://localhost:8501
```

## Deployment

This project can be deployed as a Streamlit app, but because it uses heavier computer vision dependencies such as `dlib`, OpenCV, ONNX Runtime, and Torch-related libraries, a Docker-based host is recommended for a more reliable deployment.

Recommended platforms:

- Render
- Railway
- Hugging Face Spaces with Docker
- Any VPS or cloud VM with Docker support

Basic production command:

```bash
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
```

On the deployment platform, add the same secrets used locally as environment variables or platform secrets.

## Security Notes

- Store secrets only in `.streamlit/secrets.toml` locally or in the hosting provider's secret manager.
- Never commit Supabase keys, email passwords, or API keys.
- Use the Supabase service role key only on trusted server-side deployments.
- Review the included RLS policy SQL files before deploying with real student data.
- Biometric data should be handled carefully and only with proper user consent.

## Resume Highlights

**Project:** TRUEPRESENCE - AI-Powered Attendance Platform

Suggested resume points:

- Built a role-based AI attendance platform using Python, Streamlit, Supabase, and computer vision.
- Implemented face recognition with dlib embeddings and anti-spoofing verification using ONNX Runtime.
- Designed Admin, Teacher, and Student portals for account management, subject handling, attendance tracking, and reports.
- Integrated Supabase PostgreSQL with RLS scripts for secure cloud-backed data storage.
- Added AI insights, voice chatbot support, automated email notifications, and attendance analytics.

## Future Improvements

- Add Dockerfile and CI deployment workflow
- Add automated unit and integration tests
- Add screenshots and a live demo link
- Add CSV/PDF export options for attendance reports
- Improve biometric consent and privacy documentation
- Add production monitoring and structured logs

## License

This project is intended for academic, portfolio, and learning purposes. Add a license before using it in production or distributing it publicly.
=======
# chatbot
for ai chat bot
>>>>>>> 1a21d617c178140330836d50b61117f23b3c2a1b
