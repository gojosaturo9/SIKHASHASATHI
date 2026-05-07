# Voice-RAG Chatbot Details

Fill this file with your project-specific configuration, credentials, and notes.

## Project Summary

- Project name:
- Purpose:
- Target users:
- Main chatbot features:

## Required Secrets

Add these values in `.streamlit/secrets.toml` or environment variables.

```toml
SUPABASE_URL = ""
SUPABASE_KEY = ""

GEMINI_API_KEY = ""
GEMINI_MODEL = "gemini-2.5-flash"
```

## Data Sources

- Student records:
- Teacher records:
- Subject records:
- Attendance records:
- Fields that must never be shown:

## Role Permissions

### Admin

- Can access:
- Cannot access:

### Teacher

- Can access:
- Cannot access:

### Student

- Can access:
- Cannot access:

## Voice-RAG Flow

1. User asks a question by text or voice.
2. Voice input is transcribed to text.
3. Role-specific attendance data is loaded.
4. Data is converted into documents and chunks.
5. Relevant chunks are retrieved using embeddings.
6. The chatbot answers using only retrieved context.
7. Optional speech output reads the answer aloud.

## Files Added

- `src/voice_rag/config.py`
- `src/voice_rag/documents.py`
- `src/voice_rag/embeddings.py`
- `src/voice_rag/vector_store.py`
- `src/voice_rag/llm.py`
- `src/voice_rag/speech.py`
- `src/voice_rag/attendance_context.py`
- `src/voice_rag/pipeline.py`
- `src/voice_rag/streamlit_ui.py`
- `src/components/chatbot.py`

## Setup Notes

- Python version:
- Streamlit command:
- Local URL:
- Supabase project:
- Google AI Studio / Gemini API project:

## Testing Checklist

- [ ] App starts with `python -m streamlit run app.py`
- [ ] Student chatbot answers only student data
- [ ] Teacher chatbot answers only teacher subject data
- [ ] Admin chatbot answers admin dashboard data
- [ ] Text question works
- [ ] Voice question transcribes correctly
- [ ] Retrieval context is relevant
- [ ] Speech answer works when enabled
- [ ] No passwords or biometric embeddings are shown

## Known Issues

- 

## Future Improvements

- 
