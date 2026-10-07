import streamlit as str_lit
import datetime
import calendar
import pandas as pd
import json
import os
import base64
import requests
from collections import defaultdict
from fpdf import FPDF

# ----------------------------
# CONSTANTS & SETUP
# ----------------------------
DEFAULT_DOCTORS = ["Χριστίνα", "Αθηνά", "Μαρία", "Έλια", "Αλέξανδρος", "Εύα", "Έλενα"]

DEFAULT_DOCTOR_COLORS = {
    "Έλενα": (255, 182, 193),
    "Εύα": (152, 251, 152),
    "Μαρία": (176, 196, 222),
    "Αθηνά": (255, 250, 205),
    "Αλέξανδρος": (221, 160, 221),
    "Έλια": (175, 238, 238),
    "Χριστίνα": (245, 222, 179),
}

EXTRA_COLORS = [
    (255, 218, 185), (230, 230, 250), (255, 228, 225),
    (240, 255, 240), (240, 248, 255), (255, 248, 220)
]

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
GREEK_WEEKDAY_LABELS = ["Δευ", "Τρι", "Τετ", "Πεμ", "Παρ", "Σαβ", "Κυρ"]

GREEK_MONTHS = [
    "", "Ιανουάριος", "Φεβρουάριος", "Μάρτιος", "Απρίλιος", "Μάιος", "Ιούνιος",
    "Ιούλιος", "Αύγουστος", "Σεπτέμβριος", "Οκτώβριος", "Νοέμβριος", "Δεκέμβριος",
]

FIXED_HOLIDAYS = [
    (1, 1, "Πρωτοχρονιά"),
    (1, 6, "Θεοφάνεια"),
    (3, 25, "Ευαγγελισμός / Εθνική Εορτή"),
    (4, 1, "Εθνική Εορτή Κύπρου"),
    (5, 1, "Πρωτομαγιά"),
    (8, 15, "Κοίμηση της Θεοτόκου"),
    (10, 1, "Ημέρα Ανεξαρτησίας Κύπρου"),
    (10, 28, "Ημέρα του Όχι"),
    (12, 24, "Παραμονή Χριστουγέννων"),
    (12, 25, "Χριστούγεννα"),
    (12, 26, "Δεύτερη μέρα Χριστουγέννων"),
    (12, 31, "Παραμονή Πρωτοχρονιάς"),
]

STATE_FILE = "last_schedule_state.json"

# ----------------------------
# STATE PERSISTENCE FUNCTIONS
# ----------------------------
def save_state_to_file(schedule, holiday_names, balance, manual_assignments, doctors, initial_week, empty_tooltips):
    data = {
        "schedule": {d.strftime("%Y-%m-%d"): doc for d, doc in schedule.items() if doc is not None} if schedule else {},
        "holiday_names": {d.strftime("%Y-%m-%d"): name for d, name in holiday_names.items()} if holiday_names else {},
        "manual_assignments": {d.strftime("%Y-%m-%d"): doc for d, doc in manual_assignments.items()} if manual_assignments else {},
        "empty_tooltips": {d.strftime("%Y-%m-%d"): t for d, t in empty_tooltips.items()} if empty_tooltips else {},
        "doctors": doctors,
        "initial_week": initial_week
    }
    
    file_content_str = json.dumps(data, ensure_ascii=False, indent=4)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(file_content_str)

def _github_settings():
    """Επιστρέφει (token, repo) από τα secrets ή (None, None) αν λείπουν."""
    try:
        if hasattr(str_lit, "secrets") and "GITHUB_TOKEN" in str_lit.secrets and "GITHUB_REPO" in str_lit.secrets:
            return str_lit.secrets["GITHUB_TOKEN"], str_lit.secrets["GITHUB_REPO"]
    except Exception:
        pass
    return None, None


def save_state_to_github_with_status(schedule, holiday_names, manual_assignments, doctors, initial_week, empty_tooltips):
    """Αποθηκεύει το current state στο τοπικό JSON και μετά στο GitHub. Επιστρέφει (ok, μήνυμα)."""
    save_state_to_file(schedule, holiday_names, None, manual_assignments, doctors, initial_week, empty_tooltips)

    token, repo = _github_settings()
    if not token:
        return False, "Αποθηκεύτηκε μόνο τοπικά: λείπουν τα GITHUB_TOKEN / GITHUB_REPO στα secrets."

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            file_content_str = f.read()

        url = f"https://api.github.com/repos/{repo}/contents/{STATE_FILE}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        sha = None
        get_resp = requests.get(url, headers=headers, params={"ref": "main"}, timeout=15)
        if get_resp.status_code == 200:
            sha = get_resp.json().get("sha")

        payload = {
            "message": "Manual save of schedule state JSON [skip ci]",
            "content": base64.b64encode(file_content_str.encode("utf-8")).decode("utf-8"),
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
        put_resp = requests.put(url, headers=headers, json=payload, timeout=30)
        if put_resp.status_code in (200, 201):
            return True, "Η κατάσταση αποθηκεύτηκε στο GitHub."
        return False, f"Αποτυχία αποθήκευσης στο GitHub (HTTP {put_resp.status_code})."
    except Exception as e:
        return False, f"Σφάλμα αποθήκευσης στο GitHub: {e}"


def _fetch_state_from_github():
    """Διαβάζει το JSON του repo. Επιστρέφει dict ή None αν δεν είναι διαθέσιμο."""
    token, repo = _github_settings()
    if not token:
        return None
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{STATE_FILE}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.raw"
        }
        resp = requests.get(url, headers=headers, params={"ref": "main"}, timeout=15)
        if resp.status_code == 200:
            return json.loads(resp.content.decode("utf-8"))
    except Exception as e:
        print("Αποτυχία φόρτωσης από GitHub:", e)
    return None


def _parse_state_data(data):
    schedule = {datetime.datetime.strptime(d, "%Y-%m-%d").date(): doc for d, doc in data.get("schedule", {}).items()}
    holiday_names = {datetime.datetime.strptime(d, "%Y-%m-%d").date(): name for d, name in data.get("holiday_names", {}).items()}
    manual_assignments = {datetime.datetime.strptime(d, "%Y-%m-%d").date(): doc for d, doc in data.get("manual_assignments", {}).items()}
    empty_tooltips = {datetime.datetime.strptime(d, "%Y-%m-%d").date(): t for d, t in data.get("empty_tooltips", {}).items()}

    return {
        "schedule": schedule,
        "holiday_names": holiday_names,
        "manual_assignments": manual_assignments,
        "empty_tooltips": empty_tooltips,
        "doctors": data.get("doctors", DEFAULT_DOCTORS),
        "initial_week": data.get("initial_week", DEFAULT_DOCTORS[:7])
    }


def load_state_from_file():
    github_data = _fetch_state_from_github()
    if github_data is not None:
        try:
            return _parse_state_data(github_data)
        except Exception as e:
            print("Σφάλμα ανάγνωσης state από GitHub:", e)

    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _parse_state_data(data)
    except Exception as e:
        print("Σφάλμα φόρτωσης state:", e)
        return None

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
def get_doctor_color(doc_name, doctors_list):
    if not doc_name:
        return (240, 240, 240)
    if doc_name in DEFAULT_DOCTOR_COLORS:
        return DEFAULT_DOCTOR_COLORS[doc_name]
    try:
        idx = doctors_list.index(doc_name) % len(EXTRA_COLORS)
        return EXTRA_COLORS[idx]
    except ValueError:
        return (220, 220, 220)


def orthodox_easter(year):
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    julian_easter = datetime.date(year, month, day)
    return julian_easter + datetime.timedelta(days=13)


def get_cyprus_holidays(year):
    holidays = {}
    for month, day, name in FIXED_HOLIDAYS:
        holidays[datetime.date(year, month, day)] = name

    easter = orthodox_easter(year)
    movable = {
        easter - datetime.timedelta(days=48): "Καθαρά Δευτέρα",
        easter - datetime.timedelta(days=2): "Μεγάλη Παρασκευή",
        easter - datetime.timedelta(days=1): "Μεγάλο Σάββατο",
        easter: "Κυριακή του Πάσχα",
        easter + datetime.timedelta(days=1): "Δευτέρα του Πάσχα",
        easter + datetime.timedelta(days=50): "Δευτέρα Αγίου Πνεύματος",
    }
    holidays.update(movable)
    return holidays


def get_holidays_in_range(start_date, end_date):
    holidays = {}
    for year in range(start_date.year, end_date.year + 1):
        holidays.update(get_cyprus_holidays(year))
    return {d: name for d, name in holidays.items() if start_date <= d <= end_date}


def get_major_holiday_blocks_in_range(start_date, end_date, num_docs=7):
    blocks = []
    BASE_PACKAGE_ROTATION_ORDER = {
        "Πρωτοχρονιά (1/1)": 0,
        "Χριστούγεννα (25/12)": 1,
        "Παραμονή Πρωτοχρονιάς (31/12)": 2,
        "Κυριακή του Πάσχα": 3,
        "Δευτέρα του Πάσχα": 4,
        "Μεγάλο Σάββατο + 24/12": 5,
        "Μεγάλη Παρασκευή + 26/12": 6,
    }
    
    if num_docs >= 8:
        BASE_PACKAGE_ROTATION_ORDER["Θεοφάνεια (6/1)"] = 7
    if num_docs >= 9:
        BASE_PACKAGE
