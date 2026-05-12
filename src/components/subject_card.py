import html

import streamlit as st


# Use: Internal helper for clean display text.
# Linked with: _stat_badge, subject_card
def _clean_display_text(value):
    text = str(value).strip()
    return "".join(char for char in text if char.isascii() and char.isprintable()).strip()


# Use: Internal helper for stat badge.
# Linked with: Streamlit UI, decorators, tests, or external runtime calls.
def _stat_badge(icon, label):
    icon_text = _clean_display_text(icon)
    if icon_text and icon_text.isalnum() and len(icon_text) <= 3:
        return icon_text.upper()

    words = [word for word in _clean_display_text(label).split() if word]
    if len(words) >= 2:
        return "".join(word[0] for word in words[:2]).upper()
    if words:
        return words[0][:2].upper()
    return "IN"


# Use: Handles subject card behavior in this module.
# Linked with: student_dashboard, teacher_tab_manage_subjects
def subject_card(name, code, section, stats=None, footer_callback=None):
    safe_name = html.escape(str(name))
    safe_code = html.escape(str(code))
    safe_section = html.escape(_clean_display_text(section) or str(section))

    stats_html = ""
    if stats:
        stat_tds = []
        for icon, label, value in stats:
            safe_label = html.escape(_clean_display_text(label) or str(label).strip())
            safe_value = html.escape(_clean_display_text(value) or str(value).strip())
            stat_tds.append(
                f'<td>'
                f'<span class="stat-value">{safe_value}</span>'
                f'<span class="stat-label">{safe_label}</span>'
                f'</td>'
            )
        stats_html = f'<table class="ss-subject-stats-table"><tr>{"".join(stat_tds)}</tr></table>'

    st.markdown(
        '<article class="ss-subject-card">'
        '<div class="ss-subject-top">'
        '<div class="ss-subject-icon">AI</div>'
        "<div>"
        f"<h3>{safe_name}</h3>"
        f"<p>Code <span>{safe_code}</span> | {safe_section}</p>"
        "</div>"
        "</div>"
        f"{stats_html}"
        "</article>",
        unsafe_allow_html=True,
    )

    if footer_callback:
        footer_callback()
