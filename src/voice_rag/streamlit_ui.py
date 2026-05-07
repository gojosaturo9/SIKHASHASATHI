import html

import streamlit as st

from src.voice_rag.attendance_context import build_role_context
from src.voice_rag.documents import json_to_documents
from src.voice_rag.pipeline import VoiceRAGPipeline


def get_voice_rag_pipeline():
    return VoiceRAGPipeline()


def _load_dashboard_scope(role: str):
    context = build_role_context(role)
    documents = json_to_documents(
        context,
        source=f"{role}_dashboard_scope",
        metadata={"role": role},
    )
    return context, documents


def _is_gemini_ready(pipeline: VoiceRAGPipeline) -> bool:
    key = pipeline.chat_client.api_key or ""
    return bool(key and key != "PASTE_REAL_KEY_HERE")


def _role_intro(role: str) -> str:
    if role == "student":
        return "Ask about your attendance, subjects, profile, and eligibility."
    if role == "teacher":
        return "Ask about your classes, subjects, students, and attendance reports."
    return "Ask about all students, teachers, subjects, reports, and analytics."


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


def _inject_styles():
    st.markdown(
        """
        <style>
            [data-testid="stAppViewContainer"] {
                background: #f6f7f9;
            }
            [data-testid="stHeader"] {
                background: rgba(246, 247, 249, 0.85);
            }
            .block-container {
                padding-top: 1rem;
                padding-bottom: 6rem;
            }
            .rag-layout {
                max-width: 1120px;
                margin: 0 auto;
            }
            .rag-hero {
                border: 1px solid #e5e7eb;
                background: #ffffff;
                border-radius: 14px;
                padding: 1rem 1.1rem;
                margin-bottom: 0.9rem;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
            }
            .rag-kicker {
                color: #2563eb;
                font-size: 0.78rem;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0;
                margin-bottom: 0.25rem;
            }
            .rag-title {
                color: #111827;
                font-size: 1.65rem;
                font-weight: 780;
                line-height: 1.2;
                margin: 0;
            }
            .rag-subtitle {
                color: #667085;
                font-size: 0.95rem;
                margin: 0.35rem 0 0 0;
            }
            .rag-chip-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.45rem;
                margin-top: 0.75rem;
            }
            .rag-chip {
                border: 1px solid #e5e7eb;
                border-radius: 999px;
                background: #f9fafb;
                color: #344054;
                padding: 0.22rem 0.55rem;
                font-size: 0.78rem;
                font-weight: 700;
            }
            .rag-chip.ok {
                background: #ecfdf3;
                color: #166534;
                border-color: #bbf7d0;
            }
            .rag-chip.warn {
                background: #fff7ed;
                color: #9a3412;
                border-color: #fed7aa;
            }
            .rag-sidebar {
                border: 1px solid #e5e7eb;
                background: #ffffff;
                border-radius: 14px;
                padding: 0.9rem;
                min-height: 28rem;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
            }
            .rag-main {
                border: 1px solid #e5e7eb;
                background: #ffffff;
                border-radius: 14px;
                padding: 0.9rem;
                min-height: 28rem;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
            }
            .rag-section-title {
                color: #111827;
                font-weight: 760;
                font-size: 0.95rem;
                margin-bottom: 0.55rem;
            }
            .rag-help {
                color: #667085;
                font-size: 0.86rem;
                line-height: 1.35;
                margin-bottom: 0.7rem;
            }
            .rag-empty {
                border: 1px dashed #d0d5dd;
                border-radius: 12px;
                background: #f9fafb;
                color: #667085;
                padding: 1rem;
                text-align: center;
                margin-bottom: 0.75rem;
            }
            .rag-answer-card {
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                background: #f9fafb;
                padding: 0.85rem 0.9rem;
                color: #111827;
                line-height: 1.45;
                white-space: pre-wrap;
            }
            div[data-testid="stChatMessage"] {
                border-radius: 14px;
                border: 1px solid #e5e7eb;
                background: #ffffff;
                box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
                padding: 0.25rem 0.35rem;
            }
            .stButton > button {
                border-radius: 10px;
                min-height: 2.5rem;
                font-weight: 700;
                white-space: normal;
            }
            textarea {
                border-radius: 12px !important;
            }
            div[data-testid="stFileUploader"] section {
                border-radius: 12px;
            }
            .st-key-ai_assistant_launcher {
                position: fixed;
                right: 1.25rem;
                bottom: 1.25rem;
                z-index: 1000;
            }
            .st-key-ai_assistant_launcher .stButton > button {
                width: 4rem;
                height: 4rem;
                min-height: 4rem;
                border-radius: 999px;
                border: 1px solid rgba(255,255,255,0.35);
                background: linear-gradient(135deg, #6d5dfc, #2f80ed 48%, #e94b9b);
                color: #ffffff;
                box-shadow: 0 0 0 8px rgba(109, 93, 252, 0.10), 0 18px 42px rgba(47, 128, 237, 0.35);
                animation: aiPulse 2.4s ease-in-out infinite;
                font-size: 0;
            }
            .st-key-ai_assistant_launcher .stButton > button:before {
                content: "AI";
                font-size: 1rem;
                font-weight: 850;
            }
            .st-key-ai_assistant_launcher .stButton > button:after {
                content: "AI Assistant";
                position: absolute;
                right: 4.55rem;
                bottom: 0.85rem;
                width: max-content;
                background: rgba(17, 24, 39, 0.92);
                color: #ffffff;
                padding: 0.38rem 0.58rem;
                border-radius: 8px;
                font-size: 0.78rem;
                opacity: 0;
                pointer-events: none;
                transform: translateX(0.35rem);
                transition: all 160ms ease;
            }
            .st-key-ai_assistant_launcher .stButton > button:hover:after {
                opacity: 1;
                transform: translateX(0);
            }
            @keyframes aiPulse {
                0%, 100% { transform: translateY(0); box-shadow: 0 0 0 8px rgba(109, 93, 252, 0.10), 0 18px 42px rgba(47, 128, 237, 0.35); }
                50% { transform: translateY(-2px); box-shadow: 0 0 0 12px rgba(233, 75, 155, 0.12), 0 22px 52px rgba(109, 93, 252, 0.40); }
            }
            div[data-testid="stDialog"] div[role="dialog"] {
                border-radius: 18px;
                border: 1px solid rgba(255,255,255,0.20);
                background: rgba(246, 247, 249, 0.96);
                box-shadow: 0 26px 80px rgba(15, 23, 42, 0.28);
            }
            @media (max-width: 820px) {
                .rag-sidebar,
                .rag-main {
                    min-height: auto;
                }
                .rag-title {
                    font-size: 1.35rem;
                }
                .st-key-ai_assistant_launcher {
                    right: 0.9rem;
                    bottom: 0.9rem;
                }
                div[data-testid="stDialog"] div[role="dialog"] {
                    width: calc(100vw - 1rem);
                    max-width: calc(100vw - 1rem);
                    height: calc(100vh - 1rem);
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_answer(answer: str):
    safe = html.escape(answer or "No answer returned.")
    st.markdown(f'<div class="rag-answer-card">{safe}</div>', unsafe_allow_html=True)


def _submit_text(role: str, question: str):
    question = (question or "").strip()
    if not question:
        return

    history_key = f"{role}_rag_messages"
    st.session_state[history_key].append({"role": "user", "content": question})

    context, documents = _load_dashboard_scope(role)
    response = get_voice_rag_pipeline().answer(
        role=role,
        question=question,
        documents=documents,
        dashboard_context=context,
    )
    st.session_state[history_key].append(
        {"role": "assistant", "content": response.answer}
    )


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
            {"role": "user", "content": response.transcript}
        )
    st.session_state[history_key].append(
        {"role": "assistant", "content": response.answer}
    )


def _render_chat_interface(role: str):
    pipeline = get_voice_rag_pipeline()
    gemini_ready = _is_gemini_ready(pipeline)
    history_key = f"{role}_rag_messages"
    input_key = f"{role}_rag_input"

    if history_key not in st.session_state:
        st.session_state[history_key] = []
    if input_key not in st.session_state:
        st.session_state[input_key] = ""

    status_class = "ok" if gemini_ready else "warn"
    status_text = "Gemini ready" if gemini_ready else "Gemini key missing"

    st.markdown('<div class="rag-layout">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="rag-hero">
            <div class="rag-kicker">{html.escape(role)} assistant</div>
            <h2 class="rag-title">AI Attendance Chatbot</h2>
            <p class="rag-subtitle">{html.escape(_role_intro(role))}</p>
            <div class="rag-chip-row">
                <span class="rag-chip ok">Authenticated</span>
                <span class="rag-chip ok">Role-based access</span>
                <span class="rag-chip ok">Database RAG</span>
                <span class="rag-chip {status_class}">{status_text}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sidebar, main = st.columns([0.34, 0.66], gap="medium")

    with sidebar:
        st.markdown('<div class="rag-sidebar">', unsafe_allow_html=True)
        st.markdown('<div class="rag-section-title">Chat history</div>', unsafe_allow_html=True)
        if not st.session_state[history_key]:
            st.caption("No chats yet.")
        else:
            for idx, message in enumerate(st.session_state[history_key][-8:], start=1):
                label = "You" if message["role"] == "user" else "AI"
                preview = message["content"].replace("\n", " ")[:70]
                st.caption(f"{idx}. {label}: {preview}")

        if st.button("Clear chat", icon=":material/delete:", use_container_width=True):
            st.session_state[history_key] = []
            st.rerun()

        st.divider()
        st.markdown('<div class="rag-section-title">Quick prompts</div>', unsafe_allow_html=True)
        for index, prompt in enumerate(_quick_prompts(role)):
            if st.button(prompt, key=f"{role}_prompt_{index}", use_container_width=True):
                _submit_text(role, prompt)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with main:
        st.markdown('<div class="rag-main">', unsafe_allow_html=True)
        st.markdown('<div class="rag-section-title">Conversation</div>', unsafe_allow_html=True)

        if not st.session_state[history_key]:
            st.markdown(
                '<div class="rag-empty">Ask a question by typing below or using your microphone.</div>',
                unsafe_allow_html=True,
            )
        else:
            for message in st.session_state[history_key]:
                with st.chat_message(message["role"]):
                    if message["role"] == "assistant":
                        _render_answer(message["content"])
                    else:
                        st.write(message["content"])

        st.divider()
        st.markdown('<div class="rag-section-title">Ask with text</div>', unsafe_allow_html=True)
        st.text_area(
            "Message",
            key=input_key,
            placeholder="Ask about attendance, subjects, students, class reports, or profile details...",
            height=90,
            label_visibility="collapsed",
        )
        send_col, voice_col = st.columns([0.72, 0.28], vertical_alignment="bottom")
        with send_col:
            if st.button("Send", icon=":material/send:", type="primary", use_container_width=True):
                _submit_text(role, st.session_state.get(input_key, ""))
                st.session_state[input_key] = ""
                st.rerun()

        with voice_col:
            st.caption("Voice command")

        st.markdown('<div class="rag-section-title">Ask with voice</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="rag-help">Record or upload audio, then click Enter. If microphone permission is denied, use audio upload.</div>',
            unsafe_allow_html=True,
        )
        mic_col, upload_col, enter_col = st.columns([0.38, 0.38, 0.24], vertical_alignment="bottom")
        audio_file = None
        with mic_col:
            try:
                audio_file = st.audio_input("Microphone", key=f"{role}_voice_audio")
            except Exception:
                st.warning("Microphone is unavailable or permission was denied.")
        with upload_col:
            uploaded_audio = st.file_uploader(
                "Upload audio",
                type=["wav", "mp3", "m4a", "aac", "ogg", "webm"],
                key=f"{role}_upload_audio",
            )
            if uploaded_audio is not None:
                audio_file = uploaded_audio
        with enter_col:
            if st.button(
                "Enter",
                icon=":material/keyboard_return:",
                type="primary",
                disabled=audio_file is None,
                use_container_width=True,
            ):
                if not gemini_ready:
                    st.error("Voice transcription needs a valid GEMINI_API_KEY in `.env`.")
                else:
                    with st.spinner("Transcribing and answering..."):
                        _submit_voice(role, audio_file)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


@st.dialog("AI Assistant", width="large")
def _open_chatbot_dialog(role: str):
    _render_chat_interface(role)


def render_voice_rag_chatbot(role: str):
    if not st.session_state.get("is_logged_in") or st.session_state.get("user_role") != role:
        return

    _inject_styles()
    with st.container(key="ai_assistant_launcher"):
        if st.button("AI Assistant", key=f"{role}_floating_ai_assistant"):
            _open_chatbot_dialog(role)
