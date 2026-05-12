import html
import json
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.voice_rag.attendance_context import build_role_context
from src.voice_rag.documents import json_to_documents
from src.voice_rag.pipeline import VoiceRAGPipeline


# Use: Fetches voice rag pipeline data for the app flow.
# Linked with: _render_chat_interface, _submit_text, _submit_voice
def get_voice_rag_pipeline():
    return VoiceRAGPipeline()


# Use: Internal helper for load dashboard scope.
# Linked with: _submit_text, _submit_voice
def _load_dashboard_scope(role: str):
    context = build_role_context(role)
    documents = json_to_documents(
        context,
        source=f"{role}_dashboard_scope",
        metadata={"role": role},
    )
    return context, documents


# Use: Internal helper for is gemini ready.
# Linked with: _render_chat_interface
def _is_gemini_ready(pipeline: VoiceRAGPipeline) -> bool:
    key = pipeline.chat_client.api_key or ""
    return bool(key and key != "PASTE_REAL_KEY_HERE")


# Use: Internal helper for role intro.
# Linked with: _render_chat_interface
def _role_intro(role: str) -> str:
    if role == "student":
        return "Ask about your attendance, subjects, profile, and eligibility."
    if role == "teacher":
        return "Ask about your classes, subjects, students, and attendance reports."
    return "Ask about all students, teachers, subjects, reports, and analytics."


# Use: Internal helper for quick prompts.
# Linked with: _render_chat_interface
def _quick_prompts(role: str) -> list[str]:
    if role == "student":
        return [
            "What is my attendance percentage?",
            "Which subjects am I enrolled in?",
            "Am I eligible for exam based on attendance?",
        ]
    if role == "teacher":
        return [
            "Show students enrolled in my subjects.",
            "Show low attendance students in my subject.",
            "Generate attendance summary for this week.",
        ]
    return [
        "Show total students and teachers.",
        "Show overall attendance report.",
        "Show subject-wise attendance analytics.",
    ]


# Use: Internal helper for inject styles.
# Linked with: render_voice_rag_chatbot
def _inject_styles():
    return
    st.markdown(
        """
        <style>
            /* 🚀 ADVANCED CHATBOT UI/UX */
            [data-testid="stAppViewContainer"] {
                background: #0b0b0f !important;
            }
            
            .rag-layout {
                max-width: 1050px;
                margin: 0 auto;
                font-family: var(--ss-font-body, 'Inter', sans-serif);
            }

            .rag-hero {
                border-bottom: 1px solid rgba(255, 255, 255, 0.12);
                padding: 0 0 1.1rem;
                margin-bottom: 1.4rem;
                text-align: left;
            }

            .rag-kicker {
                color: #e50914;
                font-size: 0.78rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0;
                margin-bottom: 0.5rem;
            }

            .rag-title {
                color: #f5f5f1;
                font-family: var(--ss-font-display, 'Arial Narrow', sans-serif);
                font-size: 2.8rem;
                font-weight: 400;
                margin: 0;
                letter-spacing: 0;
            }

            .rag-subtitle {
                color: #b8b8b3;
                font-size: 0.98rem;
                margin: 0.5rem 0 1rem 0;
            }

            .rag-chip-row {
                display: flex;
                justify-content: flex-start;
                flex-wrap: wrap;
                gap: 0.75rem;
            }

            .rag-chip {
                border-radius: 999px;
                padding: 0.42rem 0.72rem;
                font-size: 0.75rem;
                font-weight: 600;
                border: 1px solid rgba(255, 255, 255, 0.14);
                background: #15151a;
                color: #f5f5f1;
            }

            .rag-chip.ok { border-color: rgba(48, 209, 88, 0.45); color: #d8f6df; background: rgba(48, 209, 88, 0.12); }
            .rag-chip.warn { border-color: rgba(229, 9, 20, 0.5); color: #ffb3b7; background: rgba(229, 9, 20, 0.14); }

            .rag-sidebar, .rag-main {
                background: #111116;
                border-radius: 8px;
                padding: 1.2rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
                min-height: 35rem;
            }

            .rag-section-title {
                color: #f5f5f1;
                font-weight: 700;
                font-size: 0.92rem;
                margin-bottom: 1rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .rag-answer-card {
                background: #18181e;
                border-left: 3px solid #e50914;
                border-radius: 6px;
                padding: 1rem;
                color: #f5f5f1;
                font-size: 0.96rem;
                line-height: 1.6;
            }

            /* Floating AI Assistant Button */
            .st-key-ai_assistant_launcher {
                position: fixed;
                right: 2rem;
                bottom: 2rem;
                z-index: 9999;
            }

            .st-key-ai_assistant_launcher .stButton > button {
                width: 70px;
                height: 70px;
                border-radius: 35px;
                background: #e50914 !important;
                border: none !important;
                box-shadow: 0 12px 28px rgba(0, 0, 0, 0.35) !important;
                color: white !important;
                font-size: 0 !important;
                transition: background 0.18s ease !important;
            }

            .st-key-ai_assistant_launcher .stButton > button:before {
                content: "AI";
                font-size: 1.5rem;
                font-weight: 800;
            }

            .st-key-ai_assistant_launcher .stButton > button:hover {
                background: #b80710 !important;
            }

            /* Thinking Animation */
            .thinking-dots {
                display: inline-flex;
                gap: 4px;
                align-items: center;
            }
            .thinking-dots span {
                width: 6px;
                height: 6px;
                background: #e50914;
                border-radius: 50%;
                animation: thinking 1.4s infinite ease-in-out;
            }
            .thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
            .thinking-dots span:nth-child(3) { animation-delay: 0.4s; }

            @keyframes thinking {
                0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
                40% { transform: scale(1); opacity: 1; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


# Use: Internal helper for render answer.
# Linked with: _render_chat_interface
def _render_answer(answer: str):
    safe = html.escape(answer or "No answer returned.")
    st.markdown(f'<div class="rag-answer-card">{safe}</div>', unsafe_allow_html=True)


# Use: Internal helper for answer table rows.
# Linked with: _render_answer_table
def _answer_table_rows(answer: str):
    rows = []
    for raw_line in (answer or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        line = re.sub(r"^[-*]\s*", "", line)
        if ":" in line:
            label, value = line.split(":", 1)
            rows.append({"Item": label.strip(), "Details": value.strip()})
        elif re.search(r"\d", line):
            rows.append({"Item": "Result", "Details": line})

    return rows


# Use: Internal helper for render answer table.
# Linked with: _render_chat_interface
def _render_answer_table(answer: str):
    rows = _answer_table_rows(answer)
    if not rows:
        return

    st.markdown(
        '<div class="rag-section-title rag-table-title">Table view</div>',
        unsafe_allow_html=True,
    )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# Use: Internal helper for speak latest answer.
# Linked with: _render_chat_interface
def _speak_latest_answer(role: str, messages: list[dict]):
    if not messages:
        return

    last_message = messages[-1]
    if last_message.get("role") != "assistant":
        return
    if not last_message.get("speak"):
        return

    spoken_key = f"{role}_spoken_length"
    if st.session_state.get(spoken_key) == len(messages):
        return

    st.session_state[spoken_key] = len(messages)
    clean_text = json.dumps(
        last_message["content"].replace("\n", " ").replace("\r", "")
    )
    components.html(
        f"""
        <script>
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance({clean_text});
            utterance.lang = 'en-IN';
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            window.speechSynthesis.speak(utterance);
        </script>
        """,
        height=0,
        width=0,
    )


# Use: Internal helper for submit text.
# Linked with: _render_chat_interface
def _submit_text(role: str, question: str):
    question = (question or "").strip()
    if not question:
        return

    history_key = f"{role}_rag_messages"
    st.session_state[history_key].append(
        {"role": "user", "content": question, "source": "text"}
    )

    context, documents = _load_dashboard_scope(role)
    response = get_voice_rag_pipeline().answer(
        role=role,
        question=question,
        documents=documents,
        dashboard_context=context,
    )
    st.session_state[history_key].append(
        {"role": "assistant", "content": response.answer, "source": "text"}
    )


# Use: Internal helper for submit voice.
# Linked with: _render_chat_interface
def _submit_voice(role: str, audio_file):
    history_key = f"{role}_rag_messages"
    context, documents = _load_dashboard_scope(role)
    response = get_voice_rag_pipeline().answer_audio(
        role=role,
        audio_bytes=audio_file.read(),
        documents=documents,
        dashboard_context=context,
        filename=getattr(audio_file, "name", "question.wav"),
    )
    if response.transcript:
        st.session_state[history_key].append(
            {"role": "user", "content": response.transcript, "source": "voice"}
        )
    st.session_state[history_key].append(
        {
            "role": "assistant",
            "content": response.answer,
            "source": "voice",
            "speak": True,
        }
    )


# Use: Internal helper for request ai help reopen.
# Linked with: _render_chat_interface
def _request_ai_help_reopen(role: str):
    st.session_state[f"{role}_ai_help_open"] = True
    st.session_state[f"{role}_ai_help_reopen_once"] = True


# Use: Internal helper for render chat interface.
# Linked with: _open_chatbot_dialog
def _render_chat_interface(role: str):
    pipeline = get_voice_rag_pipeline()
    gemini_ready = _is_gemini_ready(pipeline)
    history_key = f"{role}_rag_messages"
    input_key = f"{role}_rag_input"
    voice_mode_key = f"{role}_voice_mode"

    if history_key not in st.session_state:
        st.session_state[history_key] = []
    if input_key not in st.session_state:
        st.session_state[input_key] = ""
    if voice_mode_key not in st.session_state:
        st.session_state[voice_mode_key] = False

    status_class = "ok" if gemini_ready else "warn"
    status_text = "Gemini connected" if gemini_ready else "Gemini key missing"
    role_title = role.title()

    st.markdown('<div class="rag-layout">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="rag-hero">
            <div class="rag-kicker">AI Help</div>
            <h2 class="rag-title">{role_title} AI Help</h2>
            <p class="rag-subtitle">{html.escape(_role_intro(role))}</p>
            <div class="rag-chip-row">
                <span class="rag-chip ok">Attendance context</span>
                <span class="rag-chip ok">Voice input</span>
                <span class="rag-chip {status_class}">{status_text}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sidebar, main = st.columns([0.34, 0.66], gap="large")

    with sidebar:
        st.markdown('<div class="rag-sidebar">', unsafe_allow_html=True)
        st.markdown('<div class="rag-section-title">Controls</div>', unsafe_allow_html=True)
        
        st.toggle("Conversational Voice Mode", key=voice_mode_key, help="Automatically play AI responses and enable faster voice interactions.")

        if st.button("Close AI Help", icon=":material/close:", use_container_width=True):
            st.session_state[f"{role}_ai_help_open"] = False
            st.session_state[f"{role}_ai_help_reopen_once"] = False
            st.rerun()
        
        if st.button("Clear Memory", icon=":material/refresh:", use_container_width=True):
            st.session_state[history_key] = []
            _request_ai_help_reopen(role)
            st.rerun()

        st.divider()
        st.markdown('<div class="rag-section-title">Quick questions</div>', unsafe_allow_html=True)
        for index, prompt in enumerate(_quick_prompts(role)):
            if st.button(prompt, key=f"{role}_prompt_{index}", use_container_width=True):
                with st.spinner("Processing..."):
                    _submit_text(role, prompt)
                _request_ai_help_reopen(role)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with main:
        st.markdown('<div class="rag-main">', unsafe_allow_html=True)
        st.markdown('<div class="rag-section-title">Conversation</div>', unsafe_allow_html=True)

        chat_container = st.container(height=360, border=False)
        with chat_container:
            if not st.session_state[history_key]:
                st.markdown(
                    '<div class="rag-empty">Ask a question with text or voice.</div>',
                    unsafe_allow_html=True,
                )
            else:
                for message in st.session_state[history_key]:
                    with st.chat_message(message["role"]):
                        if message["role"] == "assistant":
                            _render_answer(message["content"])
                            _render_answer_table(message["content"])
                        else:
                            st.write(message["content"])
                if (
                    st.session_state[voice_mode_key]
                    and st.session_state[history_key][-1].get("role") == "assistant"
                ):
                    st.session_state[history_key][-1]["speak"] = True
                _speak_latest_answer(role, st.session_state[history_key])

        st.divider()
        input_col, action_col = st.columns([0.8, 0.2], vertical_alignment="bottom")
        with input_col:
            user_input = st.text_input(
                "Type your message",
                placeholder="Ask about attendance, subjects, or reports...",
                label_visibility="collapsed",
                key=input_key
            )
        with action_col:
            if st.button("Send", icon=":material/send:", type="primary", use_container_width=True):
                if user_input.strip():
                    with st.spinner("Preparing answer..."):
                        _submit_text(role, user_input)
                    _request_ai_help_reopen(role)
                    st.rerun()

        st.markdown('<div class="rag-section-title rag-voice-title">Voice input</div>', unsafe_allow_html=True)
        
        v_col1, v_col2 = st.columns([0.7, 0.3], vertical_alignment="center")
        audio_file = None
        with v_col1:
            try:
                audio_file = st.audio_input("Record Voice", key=f"{role}_voice_audio", label_visibility="collapsed")
            except Exception:
                st.warning("Microphone not available")
        
        with v_col2:
            if st.button("Process Audio", icon=":material/mic:", type="primary", disabled=audio_file is None, use_container_width=True):
                with st.spinner("Transcribing..."):
                    _submit_voice(role, audio_file)
                _request_ai_help_reopen(role)
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# Use: Internal helper for open chatbot dialog.
# Linked with: render_voice_rag_chatbot
@st.dialog("AI Help", width="large")
def _open_chatbot_dialog(role: str):
    _render_chat_interface(role)


# Use: Renders the voice rag chatbot UI section.
# Linked with: admin_dashboard, student_dashboard, teacher_dashboard
def render_voice_rag_chatbot(role: str):
    if not st.session_state.get("is_logged_in") or st.session_state.get("user_role") != role:
        return

    _inject_styles()
    should_open_dialog = False
    with st.container(key="ai_assistant_launcher"):
        if st.button("AI Help", key=f"{role}_floating_ai_assistant"):
            st.session_state[f"{role}_ai_help_open"] = True
            should_open_dialog = True

    if st.session_state.get(f"{role}_ai_help_reopen_once"):
        st.session_state[f"{role}_ai_help_reopen_once"] = False
        should_open_dialog = True

    if should_open_dialog and st.session_state.get(f"{role}_ai_help_open"):
        _open_chatbot_dialog(role)
