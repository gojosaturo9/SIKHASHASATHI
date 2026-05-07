import os
import logging

from src.utils.env_loader import load_env_file
from src.voice_rag.config import SYSTEM_PROMPT

logger = logging.getLogger(__name__)
_GEMINI_KEY_STATUS_PRINTED = False


class GeminiChatClient:
    def __init__(self, model: str, temperature: float = 0.2):
        global _GEMINI_KEY_STATUS_PRINTED

        load_env_file()
        self.model = model
        self.temperature = temperature
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.last_error = None
        if self.api_key:
            message = "[Gemini] API key detected from environment."
            logger.info(message)
            if not _GEMINI_KEY_STATUS_PRINTED:
                print(message)
                _GEMINI_KEY_STATUS_PRINTED = True

    def answer(self, role: str, question: str, context: str) -> str | None:
        if not self.api_key:
            self.last_error = "GEMINI_API_KEY is not configured."
            return None

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                "If the user asks for data outside their role scope, reply exactly: "
                "\"You do not have permission to access this information.\"\n"
                "Never invent counts, names, percentages, subjects, or attendance data. "
                "Use only the retrieved context.\n\n"
                f"Logged-in role: {role}\n"
                f"Question: {question}\n\n"
                f"Retrieved context:\n{context}"
            )
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                ),
            )
            return (response.text or "").strip() or None
        except Exception as exc:
            self.last_error = str(exc)
            return None


class DashboardAnswerer:
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

        if any(word in question for word in ["subject", "course", "class"]):
            if not subjects:
                return "You have not created any subjects yet."
            return "Your subjects/classes:\n" + "\n".join(f"- {item}" for item in subjects)

        if "enrolled" in question:
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

        if "low" in question or "below" in question or "eligible" in question:
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

    def _retrieved_summary(self, retrieved) -> str:
        lines = ["I found these matching records:"]
        for item in retrieved[:6]:
            path = item.document.metadata.get("path", "record")
            lines.append(f"- {path}: {item.document.text}")
        return "\n".join(lines)
