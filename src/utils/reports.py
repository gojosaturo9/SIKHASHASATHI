import io
from datetime import datetime

import pandas as pd


# Use: Internal helper for clean text.
# Linked with: _pdf_line
def _clean_text(value):
    text = str(value)
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


# Use: Internal helper for pdf line.
# Linked with: _simple_pdf
def _pdf_line(line):
    return f"({_clean_text(line)}) Tj"


# Use: Internal helper for simple pdf.
# Linked with: build_attendance_report
def _simple_pdf(title, lines):
    stream_lines = [
        "BT",
        "/F1 16 Tf",
        "50 790 Td",
        _pdf_line(title[:72]),
        "/F1 9 Tf",
        "0 -22 Td",
    ]

    for line in lines[:44]:
        stream_lines.append(_pdf_line(line[:105]))
        stream_lines.append("0 -14 Td")

    stream_lines.append("ET")
    content = "\n".join(stream_lines).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode())
        buffer.write(obj)
        buffer.write(b"\nendobj\n")

    xref = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode())
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode())

    buffer.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return buffer.getvalue()


# Use: Builds attendance report data used by another workflow.
# Linked with: teacher_tab_attendance_records
def build_attendance_report(df, title):
    report_df = df.copy()
    csv_bytes = report_df.to_csv(index=False).encode("utf-8")

    lines = [f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}", ""]
    if report_df.empty:
        lines.append("No attendance records available for this report.")
    else:
        display_columns = [
            col
            for col in [
                "Date",
                "Time",
                "Subject",
                "Subject Code",
                "Student Name",
                "Status",
            ]
            if col in report_df.columns
        ]
        for _, row in report_df[display_columns].head(40).iterrows():
            lines.append(" | ".join(f"{col}: {row[col]}" for col in display_columns))

        if len(report_df) > 40:
            lines.append(f"... {len(report_df) - 40} more rows included in the CSV report.")

    return csv_bytes, _simple_pdf(title, lines)


# Use: Handles filter report period behavior in this module.
# Linked with: teacher_tab_attendance_records
def filter_report_period(df, period):
    report_df = df.copy()
    report_df["_report_date"] = pd.to_datetime(report_df["Date"], errors="coerce")
    today = pd.Timestamp.today().normalize()

    if period == "This Week":
        start = today - pd.Timedelta(days=today.weekday())
        report_df = report_df[report_df["_report_date"] >= start]
    elif period == "This Month":
        report_df = report_df[
            (report_df["_report_date"].dt.year == today.year)
            & (report_df["_report_date"].dt.month == today.month)
        ]

    return report_df.drop(columns=["_report_date"], errors="ignore")
