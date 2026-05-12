import logging

from src.utils.env_loader import load_env_file
from src.utils.secrets import get_secret
from src.voice_rag.config import SYSTEM_PROMPT

logger = logging.getLogger(__name__)
_GEMINI_KEY_STATUS_PRINTED = False
_GEMINI_FALLBACK_MODELS = (
    "gemini-2.0-flash",
    "models/gemini-2.0-flash",
    "gemini-2.5-flash",
    "models/gemini-2.5-flash",
    "gemini-1.5-flash-latest",
)


# Use: Internal helper for candidate gemini models.
# Linked with: generate_gemini_content
def _candidate_gemini_models(genai, configured_model: str):
    seen = set()
    candidates = [configured_model, *_GEMINI_FALLBACK_MODELS]

    try:
        listed = []
        for model in genai.list_models():
            methods = set(getattr(model, "supported_generation_methods", []) or [])
            name = getattr(model, "name", "")
            if name and "generateContent" in methods:
                listed.append(name)

        flash_models = [name for name in listed if "flash" in name.lower()]
        candidates.extend(flash_models or listed)
    except Exception:
        pass

    for name in candidates:
        if not name or name in seen:
            continue
        seen.add(name)
        yield name


# Use: Handles generate gemini content behavior in this module.
# Linked with: GeminiChatClient.answer, VoiceRAGPipeline._transcribe_audio_with_gemini, _generate_with_gemini
def generate_gemini_content(api_key: str, model_name: str, contents, temperature: float | None = None):
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    last_error = None
    generation_config = None
    if temperature is not None:
        generation_config = {"temperature": temperature}

    for candidate in _candidate_gemini_models(genai, model_name):
        try:
            model = genai.GenerativeModel(
                candidate,
                generation_config=generation_config,
            )
            response = model.generate_content(contents)
            text = (response.text or "").strip()
            if text:
                return text, candidate
        except Exception as exc:
            last_error = exc

    raise RuntimeError(
        "No Gemini model with generateContent worked. "
        f"Last error: {last_error}"
    )


class GeminiChatClient:
    # Use: Internal helper for init.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    def __init__(self, model: str, temperature: float = 0.2):
        global _GEMINI_KEY_STATUS_PRINTED

        load_env_file()
        self.model = model
        self.temperature = temperature
        self.api_key = get_secret("GEMINI_API_KEY")
        self.last_error = None
        if self.api_key:
            message = "[Gemini] API key detected."
            logger.info(message)
            if not _GEMINI_KEY_STATUS_PRINTED:
                print(message)
                _GEMINI_KEY_STATUS_PRINTED = True

    # Use: Handles answer behavior in this module.
    # Linked with: UnifiedChatClient.answer, VoiceRAGPipeline.answer, VoiceRAGPipeline.answer_audio, _submit_text
    def answer(self, role: str, question: str, context: str) -> str | None:
        if not self.api_key:
            self.last_error = "GEMINI_API_KEY missing."
            return None

        try:
            prompt = self._build_prompt(role, question, context)
            text, used_model = generate_gemini_content(
                self.api_key,
                self.model,
                prompt,
                temperature=self.temperature,
            )
            self.model = used_model
            return text
        except Exception as exc:
            self.last_error = str(exc)
            return None

    # Use: Internal helper for build prompt.
    # Linked with: GeminiChatClient.answer, _generate_ai_analysis
    def _build_prompt(self, role: str, question: str, context: str) -> str:
        return (
            f"{SYSTEM_PROMPT}\n\n"
            "If the user asks for unauthorized data, reply exactly: "
            "\"You do not have permission to access this information.\"\n"
            f"Logged-in role: {role}\n"
            f"Question: {question}\n\n"
            f"Retrieved context:\n{context}"
        )


class OpenAIChatClient:
    # Use: Internal helper for init.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    def __init__(self, model: str, temperature: float = 0.2):
        load_env_file()
        self.model = model
        self.temperature = temperature
        self.api_key = get_secret("OPENAI_API_KEY")
        self.last_error = None

    # Use: Handles answer behavior in this module.
    # Linked with: UnifiedChatClient.answer, VoiceRAGPipeline.answer, VoiceRAGPipeline.answer_audio, _submit_text
    def answer(self, role: str, question: str, context: str) -> str | None:
        if not self.api_key:
            self.last_error = "OPENAI_API_KEY missing."
            return None

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                f"Role: {role}\n"
                f"Question: {question}\n\n"
                f"Context: {context}"
            )
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            self.last_error = str(exc)
            return None


class UnifiedChatClient:
    # Use: Internal helper for init.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    def __init__(self, config):
        if config.provider == "openai":
            self.client = OpenAIChatClient(config.openai_model, config.temperature)
        else:
            self.client = GeminiChatClient(config.chat_model, config.temperature)
            
    # Use: Handles api key behavior in this module.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    @property
    def api_key(self):
        return self.client.api_key

    # Use: Handles last error behavior in this module.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    @property
    def last_error(self):
        return self.client.last_error

    # Use: Handles last error behavior in this module.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    @last_error.setter
    def last_error(self, value):
        self.client.last_error = value

    # Use: Handles answer behavior in this module.
    # Linked with: UnifiedChatClient.answer, VoiceRAGPipeline.answer, VoiceRAGPipeline.answer_audio, _submit_text
    def answer(self, role: str, question: str, context: str) -> str | None:
        return self.client.answer(role, question, context)


class DashboardAnswerer:
    # Use: Handles keyword answer behavior in this module.
    # Linked with: VoiceRAGPipeline.answer
    def keyword_answer(self, role: str, question: str, context: dict | None) -> str | None:
        context = context or {}
        question_lower = (question or "").lower()

        if self._is_unauthorized(role, question_lower):
            return "You do not have permission to access this information."

        if role == "teacher":
            return self._teacher_keyword_answer(question_lower, context)
        if role == "student":
            return self._student_keyword_answer(question_lower, context)
        if role == "admin":
            return self._admin_keyword_answer(question_lower, context)
        return None

    # Use: Handles answer behavior in this module.
    # Linked with: UnifiedChatClient.answer, VoiceRAGPipeline.answer, VoiceRAGPipeline.answer_audio, _submit_text
    def answer(self, role: str, question: str, context: dict | None, retrieved) -> str:
        context = context or {}
        question_lower = (question or "").lower()

        if self._is_unauthorized(role, question_lower):
            return "You do not have permission to access this information."

        if role == "student":
            return self._student_answer(question_lower, context)
        if role == "teacher":
            return self._teacher_answer(question_lower, context)
        if role == "admin":
            return self._admin_answer(question_lower, context)

        if not retrieved:
            return "I could not find matching records in your permitted dashboard data."
        return self._retrieved_summary(retrieved)

    # Use: Internal helper for is unauthorized.
    # Linked with: DashboardAnswerer.answer, DashboardAnswerer.keyword_answer
    def _is_unauthorized(self, role: str, question: str) -> bool:
        if role == "admin":
            return False
        admin_terms = ["all students", "all teachers", "everyone", "whole college", "all users"]
        teacher_terms = ["teacher password", "admin", "other teacher", "all classes"]
        student_terms = ["other student", "another student", "classmate", "teacher data"]
        if role == "student":
            return any(term in question for term in admin_terms + teacher_terms + student_terms)
        if role == "teacher":
            return any(term in question for term in ["all teachers", "other teacher", "admin password", "all users"])
        return False

    # Use: Internal helper for student answer.
    # Linked with: DashboardAnswerer.answer
    def _student_answer(self, question: str, context: dict) -> str:
        profile = context.get("profile") or {}
        subjects = context.get("enrolled_subjects") or []
        attendance = context.get("attendance_summary") or []
        recent = context.get("recent_attendance") or []

        if any(word in question for word in ["profile", "who am i", "name", "email"]):
            return "\n".join(
                [
                    "Here is your profile:",
                    f"Name: {profile.get('name', 'Not available')}",
                    f"Email: {profile.get('email_id', 'Not available')}",
                    f"Enrollment: {profile.get('enrollment_no', 'Not available')}",
                    f"Branch: {profile.get('branch', 'Not available')}",
                    f"Semester: {profile.get('semester', 'Not available')}",
                    f"Section: {profile.get('section', 'Not available')}",
                ]
            )

        if any(word in question for word in ["subject", "course", "enrolled"]):
            if not subjects:
                return "You are not enrolled in any subjects yet."
            return "Your enrolled subjects:\n" + "\n".join(f"- {item}" for item in subjects)

        if "recent" in question:
            if not recent:
                return "No recent attendance records were found for your account."
            lines = ["Your recent attendance records:"]
            for row in recent[:8]:
                subject = (row.get("subjects") or {}).get("name", row.get("subject_id", "Subject"))
                status = "Present" if row.get("is_present") else "Absent"
                timestamp = row.get("timestamp", "No date")
                lines.append(f"- {subject}: {status} on {timestamp}")
            return "\n".join(lines)

        if attendance:
            lines = ["Your attendance summary:"]
            lines.extend(f"- {item}" for item in attendance)
            alerts = context.get("alerts") or []
            if alerts:
                lines.append("\nAlerts:")
                lines.extend(f"- {item}" for item in alerts)
            return "\n".join(lines)
        return "No attendance records were found for your account."

    # Use: Internal helper for teacher answer.
    # Linked with: DashboardAnswerer.answer
    def _teacher_answer(self, question: str, context: dict) -> str:
        teacher = context.get("teacher") or {}
        subjects = context.get("subjects") or []
        attendance = context.get("attendance_summary") or []
        sessions = context.get("recent_sessions") or []
        recent = context.get("recent_attendance") or []

        if any(word in question for word in ["profile", "who am i", "name", "email"]):
            return "\n".join(
                [
                    "Here is your teacher profile:",
                    f"Name: {teacher.get('name', 'Not available')}",
                    f"Username: {teacher.get('username', 'Not available')}",
                    f"Email: {teacher.get('email_id', 'Not available')}",
                ]
            )

        if self._has_any(question, ["enrolled", "total students", "how many students", "class strength"]):
            enrolled = context.get("enrolled_students_by_subject") or []
            if not enrolled:
                return "No enrolled students were found for your subjects."
            lines = ["Enrolled students in your subjects:"]
            for subject in enrolled:
                lines.append(
                    f"- {subject.get('subject', 'Subject')} ({subject.get('subject_code', '-')})"
                    f": {subject.get('total_students', 0)} students"
                )
                for student in (subject.get("students") or [])[:8]:
                    lines.append(f"  - {student.get('name', 'Unknown student')}")
            return "\n".join(lines)

        if self._has_any(question, ["low", "below", "eligible", "defaulter", "defaulters"]):
            low = context.get("low_attendance_students") or []
            if not low:
                return "No low-attendance students were found in your subjects."
            lines = ["Low-attendance students in your subjects:"]
            for row in low[:20]:
                lines.append(
                    f"- {row.get('student', 'Unknown student')} in {row.get('subject', 'Subject')}: "
                    f"{row.get('present', 0)}/{row.get('total', 0)} "
                    f"({row.get('attendance_percent', 0)}%)"
                )
            return "\n".join(lines)

        if "recent" in question or "session" in question:
            if not sessions:
                return "No recent class sessions were found for your subjects."
            lines = ["Your recent sessions:"]
            for row in sessions[:10]:
                lines.append(
                    f"- {row.get('subject', 'Subject')} on {row.get('date', 'Unknown date')}: "
                    f"{row.get('records', 0)} records"
                )
            return "\n".join(lines)

        if any(word in question for word in ["student", "absent", "present"]):
            if not recent:
                return "No student attendance records were found for your subjects."
            lines = ["Student records from your classes:"]
            for row in recent[:10]:
                student = (row.get("students") or {}).get("name", "Unknown student")
                subject = (row.get("subjects") or {}).get("name", "Subject")
                status = "Present" if row.get("is_present") else "Absent"
                lines.append(f"- {student}: {status} in {subject}")
            return "\n".join(lines)

        if attendance:
            lines = ["Your class attendance summary:"]
            for row in attendance:
                lines.append(
                    f"- {row.get('subject', 'Subject')}: "
                    f"{row.get('present_marks', 0)}/{row.get('total_marks', 0)} present "
                    f"({row.get('attendance_percent', 0)}%), "
                    f"{row.get('students_seen', 0)} students"
                )
            return "\n".join(lines)
        return "No attendance records were found for your subjects."

    # Use: Internal helper for admin answer.
    # Linked with: DashboardAnswerer.answer
    def _admin_answer(self, question: str, context: dict) -> str:
        totals = context.get("totals") or {}

        if any(word in question for word in ["total", "overall", "report", "analytics", "trend"]):
            return "\n".join(
                [
                    "Admin dashboard summary:",
                    f"Students: {totals.get('students', 0)}",
                    f"Teachers: {totals.get('teachers', 0)}",
                    f"Subjects: {totals.get('subjects', 0)}",
                    f"Attendance records: {totals.get('attendance_records', 0)}",
                    f"Students by branch: {context.get('students_by_branch', {})}",
                ]
            )

        if "teacher" in question:
            teachers = context.get("teachers") or []
            if not teachers:
                return "No teachers were found."
            return "Registered teachers:\n" + "\n".join(
                f"- {row.get('name', 'Unknown')} ({row.get('username', 'no username')}, {row.get('email_id', 'no email')})"
                for row in teachers[:20]
            )

        if "student" in question:
            students = context.get("students") or []
            if not students:
                return "No students were found."
            lines = [
                f"Total students: {totals.get('students', len(students))}",
                f"By branch: {context.get('students_by_branch', {})}",
                "Sample students:",
            ]
            lines.extend(
                f"- {row.get('name', 'Unknown')} | {row.get('branch', '-')}, Sem {row.get('semester', '-')}, Sec {row.get('section', '-')}"
                for row in students[:10]
            )
            return "\n".join(lines)

        if "subject" in question:
            subjects = context.get("subjects") or []
            if not subjects:
                return "No subjects were found."
            return "Subjects:\n" + "\n".join(
                f"- {row.get('name', 'Unknown')} ({row.get('subject_code', '-')})"
                for row in subjects[:20]
            )

        return "\n".join(
            [
                "Admin dashboard summary:",
                f"Students: {totals.get('students', 0)}",
                f"Teachers: {totals.get('teachers', 0)}",
                f"Subjects: {totals.get('subjects', 0)}",
                f"Attendance records: {totals.get('attendance_records', 0)}",
                f"Students by branch: {context.get('students_by_branch', {})}",
            ]
        )

    # Use: Internal helper for retrieved summary.
    # Linked with: DashboardAnswerer.answer
    def _retrieved_summary(self, retrieved) -> str:
        lines = ["I found these matching records:"]
        for item in retrieved[:6]:
            path = item.document.metadata.get("path", "record")
            lines.append(f"- {path}: {item.document.text}")
        return "\n".join(lines)

    # Use: Internal helper for has any.
    # Linked with: DashboardAnswerer._admin_keyword_answer, DashboardAnswerer._student_keyword_answer, DashboardAnswerer._teacher_answer, DashboardAnswerer._teacher_keyword_answer
    @staticmethod
    def _has_any(question: str, keywords: list[str]) -> bool:
        return any(keyword in question for keyword in keywords)

    # Use: Internal helper for teacher keyword answer.
    # Linked with: DashboardAnswerer.keyword_answer
    def _teacher_keyword_answer(self, question: str, context: dict) -> str | None:
        if self._has_any(question, ["this week", "weekly", "week report", "week summary", "last 7 days"]):
            weekly = context.get("weekly_attendance_summary") or []
            if not weekly:
                return "Weekly attendance summary: No attendance records were found in the last 7 days."
            lines = ["Weekly attendance summary:"]
            for row in weekly:
                lines.append(
                    f"- {row.get('subject', 'Subject')}: "
                    f"{row.get('present_marks', 0)}/{row.get('total_marks', 0)} present "
                    f"({row.get('attendance_percent', 0)}%), "
                    f"{row.get('students_seen', 0)} students, "
                    f"{row.get('sessions', 0)} sessions"
                )
            return "\n".join(lines)

        if self._has_any(
            question,
            [
                "total students",
                "total number of students",
                "how many students",
                "students enrolled",
                "enrolled students",
                "class strength",
            ],
        ):
            enrolled = context.get("enrolled_students_by_subject") or []
            total = context.get("total_enrolled_students", 0)
            if not enrolled:
                return "Enrolled students: No enrolled students were found for your subjects."
            lines = [f"Total enrolled student entries across your subjects: {total}"]
            for subject in enrolled:
                lines.append(
                    f"- {subject.get('subject', 'Subject')} ({subject.get('subject_code', '-')}): "
                    f"{subject.get('total_students', 0)} students"
                )
                for student in (subject.get("students") or [])[:12]:
                    lines.append(f"  - {student.get('name', 'Unknown student')}")
            return "\n".join(lines)

        if self._has_any(
            question,
            [
                "low attendance",
                "below 75",
                "less than 75",
                "short attendance",
                "defaulter",
                "defaulters",
                "not eligible",
            ],
        ):
            low = context.get("low_attendance_students") or []
            if not low:
                return "Low-attendance students: No students are currently below 75% in your subjects."
            lines = ["Low-attendance students below 75%:"]
            for row in low[:30]:
                lines.append(
                    f"- {row.get('student', 'Unknown student')} in {row.get('subject', 'Subject')}: "
                    f"{row.get('present', 0)}/{row.get('total', 0)} present "
                    f"({row.get('attendance_percent', 0)}%)"
                )
            return "\n".join(lines)

        return None

    # Use: Internal helper for student keyword answer.
    # Linked with: DashboardAnswerer.keyword_answer
    def _student_keyword_answer(self, question: str, context: dict) -> str | None:
        if self._has_any(question, ["low attendance", "below 75", "eligible", "not eligible"]):
            alerts = context.get("alerts") or []
            if not alerts:
                return "Attendance eligibility: No subjects are currently below 75%."
            return "Attendance alerts:\n" + "\n".join(f"- {item}" for item in alerts)
        return None

    # Use: Internal helper for admin keyword answer.
    # Linked with: DashboardAnswerer.keyword_answer
    def _admin_keyword_answer(self, question: str, context: dict) -> str | None:
        if self._has_any(question, ["total", "overall", "count", "summary"]):
            totals = context.get("totals") or {}
            return "\n".join(
                [
                    "Admin totals:",
                    f"- Students: {totals.get('students', 0)}",
                    f"- Teachers: {totals.get('teachers', 0)}",
                    f"- Subjects: {totals.get('subjects', 0)}",
                    f"- Attendance records: {totals.get('attendance_records', 0)}",
                ]
            )
        return None
