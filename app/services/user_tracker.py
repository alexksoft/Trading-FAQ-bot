# app/services/user_tracker.py
# Tracks users in a Google Sheet.
# Columns: phone, name, country, timezone, first_seen, last_seen, messages, language, provider

import logging
from datetime import datetime, timezone
from threading import Thread

logger = logging.getLogger(__name__)

# Phone prefix -> (country, timezone)
_PREFIX_MAP = {
    "+1":    ("USA/Canada",       "America/New_York"),
    "+44":   ("UK",               "Europe/London"),
    "+49":   ("Germany",          "Europe/Berlin"),
    "+33":   ("France",           "Europe/Paris"),
    "+34":   ("Spain",            "Europe/Madrid"),
    "+39":   ("Italy",            "Europe/Rome"),
    "+31":   ("Netherlands",      "Europe/Amsterdam"),
    "+32":   ("Belgium",          "Europe/Brussels"),
    "+41":   ("Switzerland",      "Europe/Zurich"),
    "+43":   ("Austria",          "Europe/Vienna"),
    "+48":   ("Poland",           "Europe/Warsaw"),
    "+380":  ("Ukraine",          "Europe/Kyiv"),
    "+7":    ("Russia/Kazakhstan","Europe/Moscow"),
    "+375":  ("Belarus",          "Europe/Minsk"),
    "+372":  ("Estonia",          "Europe/Tallinn"),
    "+371":  ("Latvia",           "Europe/Riga"),
    "+370":  ("Lithuania",        "Europe/Vilnius"),
    "+40":   ("Romania",          "Europe/Bucharest"),
    "+359":  ("Bulgaria",         "Europe/Sofia"),
    "+36":   ("Hungary",          "Europe/Budapest"),
    "+420":  ("Czech Republic",   "Europe/Prague"),
    "+421":  ("Slovakia",         "Europe/Bratislava"),
    "+386":  ("Slovenia",         "Europe/Ljubljana"),
    "+385":  ("Croatia",          "Europe/Zagreb"),
    "+381":  ("Serbia",           "Europe/Belgrade"),
    "+30":   ("Greece",           "Europe/Athens"),
    "+90":   ("Turkey",           "Europe/Istanbul"),
    "+972":  ("Israel",           "Asia/Jerusalem"),
    "+971":  ("UAE",              "Asia/Dubai"),
    "+966":  ("Saudi Arabia",     "Asia/Riyadh"),
    "+20":   ("Egypt",            "Africa/Cairo"),
    "+27":   ("South Africa",     "Africa/Johannesburg"),
    "+234":  ("Nigeria",          "Africa/Lagos"),
    "+254":  ("Kenya",            "Africa/Nairobi"),
    "+91":   ("India",            "Asia/Kolkata"),
    "+92":   ("Pakistan",         "Asia/Karachi"),
    "+880":  ("Bangladesh",       "Asia/Dhaka"),
    "+86":   ("China",            "Asia/Shanghai"),
    "+81":   ("Japan",            "Asia/Tokyo"),
    "+82":   ("South Korea",      "Asia/Seoul"),
    "+65":   ("Singapore",        "Asia/Singapore"),
    "+60":   ("Malaysia",         "Asia/Kuala_Lumpur"),
    "+62":   ("Indonesia",        "Asia/Jakarta"),
    "+66":   ("Thailand",         "Asia/Bangkok"),
    "+84":   ("Vietnam",          "Asia/Ho_Chi_Minh"),
    "+63":   ("Philippines",      "Asia/Manila"),
    "+55":   ("Brazil",           "America/Sao_Paulo"),
    "+54":   ("Argentina",        "America/Argentina/Buenos_Aires"),
    "+52":   ("Mexico",           "America/Mexico_City"),
    "+57":   ("Colombia",         "America/Bogota"),
    "+56":   ("Chile",            "America/Santiago"),
    "+51":   ("Peru",             "America/Lima"),
    "+58":   ("Venezuela",        "America/Caracas"),
    "+61":   ("Australia",        "Australia/Sydney"),
    "+64":   ("New Zealand",      "Pacific/Auckland"),
}


def _get_country_tz(phone: str) -> tuple[str, str]:
    """Detect country and timezone from phone number prefix."""
    if not phone.startswith("+"):
        phone = "+" + phone
    for length in (4, 3, 2):
        prefix = phone[:length]
        if prefix in _PREFIX_MAP:
            return _PREFIX_MAP[prefix]
    return ("Unknown", "Unknown")


def _get_client():
    try:
        import gspread
        from app.config.settings import settings
        if not settings.google_creds_path or not settings.google_sheet_id:
            return None, None
        gc = gspread.service_account(filename=settings.google_creds_path)
        sh = gc.open_by_key(settings.google_sheet_id)
        return gc, sh.sheet1
    except Exception as e:
        logger.warning(f"[user_tracker] Google Sheets not available: {e}")
        return None, None


def _ensure_header(ws):
    try:
        if ws.cell(1, 1).value != "phone":
            ws.insert_row(
                ["phone", "name", "country", "timezone", "timestamp", "language", "provider"],
                index=1
            )
    except Exception as e:
        logger.warning(f"[user_tracker] Header check failed: {e}")


def _track(sender: str, display_name: str, lang: str, provider: str):
    try:
        _, ws = _get_client()
        if ws is None:
            return

        _ensure_header(ws)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        country, tz = _get_country_tz(sender)

        ws.append_row([sender, display_name, country, tz, now, lang, provider])
        logger.info(f"[user_tracker] Row added: {sender} ({display_name}) from {country}")

    except Exception as e:
        logger.warning(f"[user_tracker] Failed to track {sender}: {e}")


def track_user(sender: str, display_name: str = "", lang: str = "en", provider: str = "unknown"):
    """Record a user interaction in Google Sheets (background thread)."""
    Thread(target=_track, args=(sender, display_name, lang, provider), daemon=True).start()
