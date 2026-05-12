from datetime import datetime, timedelta
import os

from PIL import ExifTags


DEFAULT_MAX_PHOTO_AGE_MINUTES = 15
DEFAULT_MIN_FACES = 1
DEFAULT_MIN_ROSTER_MATCHES = 1
DEFAULT_MIN_ROSTER_RATIO = 0.5
DEFAULT_EDIT_HOURS = 6
EXIF_DATE_TAGS = {"DateTimeOriginal", "DateTimeDigitized", "DateTime"}


# Use: Reads an integer setting from environment variables.
# Called from: get_zero_trust_settings to load max photo age, minimum face count, minimum roster matches, and edit window hours.
def _get_int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Use: Reads a decimal/float setting from environment variables.
# Called from: get_zero_trust_settings to load ZERO_TRUST_MIN_ROSTER_RATIO.
def _get_float_env(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Use: Central config for upload-photo zero-trust rules and teacher manual-edit window.
# Called from: extract_photo_metadata, validate_crowd_and_roster, editable_until.
def get_zero_trust_settings():
    return {
        "max_photo_age_minutes": _get_int_env(
            "ZERO_TRUST_MAX_PHOTO_AGE_MINUTES", DEFAULT_MAX_PHOTO_AGE_MINUTES
        ),
        "min_faces": _get_int_env("ZERO_TRUST_MIN_FACES", DEFAULT_MIN_FACES),
        "min_roster_matches": _get_int_env(
            "ZERO_TRUST_MIN_ROSTER_MATCHES", DEFAULT_MIN_ROSTER_MATCHES
        ),
        "min_roster_ratio": _get_float_env(
            "ZERO_TRUST_MIN_ROSTER_RATIO", DEFAULT_MIN_ROSTER_RATIO
        ),
        "edit_hours": _get_int_env("ATTENDANCE_EDIT_HOURS", DEFAULT_EDIT_HOURS),
    }


# Use: Converts EXIF date strings into Python datetime values.
# Called from: extract_photo_metadata when an uploaded image has DateTimeOriginal/DateTimeDigitized/DateTime.
def _parse_exif_datetime(value):
    if not value:
        return None

    value = str(value).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


# Use: Validates photo freshness metadata.
# Called from: dialog_add_photo.add_photos_dialog.
# Important: camera captures are always accepted with current timestamp; EXIF age checks apply only to uploaded files.
def extract_photo_metadata(image, source, filename=None):
    now = datetime.now()
    metadata = {
        "source": source,
        "filename": filename,
        "captured_at": None,
        "accepted": True,
        "reason": None,
    }

    if source == "camera":
        metadata["captured_at"] = now.isoformat(timespec="seconds")
        return metadata

    exif = image.getexif()
    captured_at = None
    for tag_id, value in exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        if tag_name in EXIF_DATE_TAGS:
            captured_at = _parse_exif_datetime(value)
            if captured_at:
                break

    if captured_at is None:
        metadata.update({"accepted": False, "reason": "missing_exif_timestamp"})
        return metadata

    metadata["captured_at"] = captured_at.isoformat(timespec="seconds")
    max_age = timedelta(minutes=get_zero_trust_settings()["max_photo_age_minutes"])
    if now - captured_at > max_age:
        metadata.update({"accepted": False, "reason": "old_photo"})
    elif captured_at - now > timedelta(minutes=5):
        metadata.update({"accepted": False, "reason": "future_photo_timestamp"})

    return metadata


# Use: Zero-trust validation for uploaded classroom photos only.
# Called from: teacher_screen.teacher_tab_take_attendance, only when source == "upload".
# It is not applied to fresh camera captures.
def validate_crowd_and_roster(total_faces, roster_matches):
    settings = get_zero_trust_settings()
    if total_faces < settings["min_faces"]:
        return False, "not_enough_faces"
    if roster_matches < settings["min_roster_matches"]:
        return False, "not_enough_roster_matches"
    if total_faces and roster_matches / total_faces < settings["min_roster_ratio"]:
        return False, "low_roster_density"
    return True, None


# Use: Computes how long teacher manual correction remains editable.
# Called from: teacher_screen.teacher_tab_take_attendance and dialog_voice_attendance.voice_attendance_dialog before saving attendance logs.
def editable_until(timestamp=None):
    base_time = timestamp or datetime.now()
    hours = get_zero_trust_settings()["edit_hours"]
    return (base_time + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
