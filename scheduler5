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

STATE_FILE = "last_schedule_state_cyclic_1.json"

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
    try:
        if hasattr(str_lit, "secrets") and "GITHUB_TOKEN" in str_lit.secrets and "GITHUB_REPO" in str_lit.secrets:
            return str_lit.secrets["GITHUB_TOKEN"], str_lit.secrets["GITHUB_REPO"]
    except Exception:
        pass
    return None, None

def save_state_to_github_with_status(schedule, holiday_names, manual_assignments, doctors, initial_week, empty_tooltips):
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
            "message": f"Manual save of schedule state {STATE_FILE} [skip ci]",
            "content": base64.b64encode(file_content_str.encode("utf-8")).decode("utf-8"),
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
        put_resp = requests.put(url, headers=headers, json=payload, timeout=30)
        if put_resp.status_code in (200, 201):
            return True, f"Η κατάσταση αποθηκεύτηκε στο GitHub ως {STATE_FILE}."
        return False, f"Αποτυχία αποθήκευσης στο GitHub (HTTP {put_resp.status_code})."
    except Exception as e:
        return False, f"Σφάλμα αποθήκευσης στο GitHub: {e}"

def _fetch_state_from_github():
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
        BASE_PACKAGE_ROTATION_ORDER["Πρωτομαγιά (1/5)"] = 8

    for y in range(start_date.year - 1, end_date.year + 2):
        easter_next = orthodox_easter(y + 1)
        g_fri_next = easter_next - datetime.timedelta(days=2)
        s_sat_next = easter_next - datetime.timedelta(days=1)
        sun_e_next = easter_next
        mon_e_next = easter_next + datetime.timedelta(days=1)

        year_blocks = [
            ([datetime.date(y + 1, 1, 1)], "Πρωτοχρονιά (1/1)"),
            ([datetime.date(y, 12, 25)], "Χριστούγεννα (25/12)"),
            ([datetime.date(y, 12, 31)], "Παραμονή Πρωτοχρονιάς (31/12)"),
            ([sun_e_next], "Κυριακή του Πάσχα"),
            ([mon_e_next], "Δευτέρα του Πάσχα"),
            ([s_sat_next, datetime.date(y, 12, 24)], "Μεγάλο Σάββατο + 24/12"),
            ([g_fri_next, datetime.date(y, 12, 26)], "Μεγάλη Παρασκευή + 26/12"),
        ]
        if num_docs <= 5 and len(year_blocks) > num_docs:
            year_blocks = year_blocks[:num_docs]
        if num_docs >= 8:
            year_blocks.append(([datetime.date(y, 1, 6)], "Θεοφάνεια (6/1)"))
        if num_docs >= 9:
            year_blocks.append(([datetime.date(y, 5, 1)], "Πρωτομαγιά (1/5)"))

        for dates, base_name in year_blocks:
            valid_dates = [d for d in dates if start_date <= d <= end_date]
            if valid_dates:
                blocks.append({
                    "name": f"{base_name} ({y}-{y+1})" if "+" in base_name else f"{base_name} ({valid_dates[0].year})",
                    "base_name": base_name,
                    "dates": valid_dates,
                    "cycle_id": y,
                    "order": BASE_PACKAGE_ROTATION_ORDER.get(base_name, 99)
                })
    return blocks

# ----------------------------
# STRICT CONTINUOUS 7-DAY ROTATION LOGIC (UPDATED STEP = 6)
# ----------------------------
def generate_full_schedule(start_date, end_date, doctors_list, initial_week, manual_entries=None):
    return generate_full_schedule_with_balance(start_date, end_date, doctors_list, initial_week, manual_entries, initial_balance=None)

def generate_full_schedule_with_balance(start_date, end_date, doctors_list, initial_week, manual_entries=None, initial_balance=None):
    manual_entries = manual_entries or {}
    schedule = {}
    warnings = []
    empty_tooltips = {}

    total_days = (end_date - start_date).days + 1
    holiday_names = get_holidays_in_range(start_date, end_date)
    num_docs = len(doctors_list)

    if not doctors_list:
        return schedule, holiday_names, ["Δεν υπάρχουν ενεργοί ιατροί."]

    all_days = [start_date + datetime.timedelta(days=i) for i in range(total_days)]
    
    start_weekday = start_date.weekday()
    anchor_monday = start_date - datetime.timedelta(days=start_weekday)

    for d in all_days:
        if d in manual_entries and manual_entries[d] in doctors_list:
            schedule[d] = manual_entries[d]
        else:
            wd = d.weekday()  # 0=Δευτέρα έως 6=Κυριακή
            current_monday = d - datetime.timedelta(days=wd)
            week_num = (current_monday - anchor_monday).days // 7

            if initial_week and len(initial_week) > wd and initial_week[wd] in doctors_list:
                base_doc = initial_week[wd]
            else:
                base_doc = doctors_list[wd % num_docs]
            
            base_idx = doctors_list.index(base_doc) if base_doc in doctors_list else 0

            # ΕΔΩ ΕΓΙΝΕ Η ΑΛΛΑΓΗ ΤΟΥ ΒΗΜΑΤΟΣ ΑΠΟ 5 ΣΕ 6
            doc_idx = (base_idx - week_num * 6) % num_docs
            schedule[d] = doctors_list[doc_idx]

    str_lit.session_state.empty_tooltips = empty_tooltips
    return schedule, holiday_names, warnings

# ----------------------------
# CHRONOLOGICAL SUMMARY FUNCTIONS
# ----------------------------
def compute_major_holidays_by_doctor(schedule, start_date, end_date, doctors_list):
    doctor_rows = {doc: [] for doc in doctors_list}
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date, len(doctors_list))
    for block in major_blocks:
        package_name = block["base_name"]
        for d in block["dates"]:
            if start_date <= d <= end_date:
                doc = schedule.get(d)
                doc_str = doc if doc else "-"
                if doc in doctor_rows:
                    weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
                    doctor_rows[doc].append({
                        "date_obj": d,
                        "Ακτινολόγος": doc_str,
                        "Ημερομηνία & Ημέρα": f"{d.strftime('%d/%m/%Y')} ({weekday_str})",
                        "Μεγάλη Εορτή / Πακέτο": package_name
                    })
    all_data = []
    for doc in doctors_list:
        sorted_items = sorted(doctor_rows[doc], key=lambda x: x["date_obj"])
        for item in sorted_items:
            all_data.append({
                "Ακτινολόγος": item["Ακτινολόγος"],
                "Ημερομηνία & Ημέρα": item["Ημερομηνία & Ημέρα"],
                "Μεγάλη Εορτή / Πακέτο": item["Μεγάλη Εορτή / Πακέτο"]
            })
    return pd.DataFrame(all_data)

def compute_regular_holidays_chronological(schedule, regular_holidays):
    sorted_hols = sorted(regular_holidays.keys())
    data = []
    for d in sorted_hols:
        doc = schedule.get(d)
        doc_str = doc if doc else "-"
        weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
        data.append({
            "date_obj": d,
            "Ημερομηνία": d.strftime('%d/%m/%Y'),
            "Ημέρα": weekday_str,
            "Μικρή Αργία": regular_holidays[d],
            "Ακτινολόγος": doc_str,
        })
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("date_obj").drop(columns=["date_obj"]).reset_index(drop=True)
    return df

def compute_balance(schedule, start_date, end_date, holiday_names, doctors_list):
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in doctors_list}
    holiday_counts = {doc: 0 for doc in doctors_list}
    
    for date, doc in schedule.items():
        if doc in doctors_list and doc is not None:
            if start_date <= date <= end_date:
                wd_idx = date.weekday()
                counts[doc][WEEKDAY_LABELS[wd_idx]] += 1
                if date in holiday_names:
                    holiday_counts[doc] += 1

    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]
    df["Αργίες"] = df["Doctor"].apply(lambda doc: holiday_counts.get(doc, 0))
    df["Total"] = df["Weekdays"] + df["Fri"] + df["Sat"] + df["Sun"] + df["Αργίες"]
    return df[["Doctor", "Weekdays", "Fri", "Sat", "Sun", "Αργίες", "Total"]]

# ----------------------------
# PDF EXPORT HELPERS
# ----------------------------
def create_balance_pdf(df, start_date, end_date):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Ισοζύγιο Εφημεριών", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    col_widths = [45, 25, 18, 18, 18, 22, 22]
    pdf.set_font("DejaVu", "B", 12)
    for h, w in zip(df.columns, col_widths):
        pdf.cell(w, 8, str(h), border=1, align="C")
    pdf.ln()
    pdf.set_font("DejaVu", "", 12)
    for _, row in df.iterrows():
        for val, w in zip(row, col_widths):
            pdf.cell(w, 8, str(val), border=1, align="C")
        pdf.ln()
    return bytes(pdf.output())

def create_major_holidays_pdf_by_doctor(schedule, start_date, end_date, doctors_list):
    doctor_rows = {doc: [] for doc in doctors_list}
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date, len(doctors_list))
    for block in major_blocks:
        package_name = block["base_name"]
        for d in block["dates"]:
            if start_date <= d <= end_date:
                doc = schedule.get(d)
                doc_str = doc if doc else "-"
                if doc in doctor_rows:
                    weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
                    doctor_rows[doc].append({
                        "date_obj": d,
                        "Ημερομηνία & Ημέρα": f"{d.strftime('%d/%m/%Y')} ({weekday_str})",
                        "Μεγάλη Εορτή / Πακέτο": package_name
                    })
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")
    col_widths = [45, 125]
    headers = ["Ημερομηνία & Ημέρα", "Μεγάλη Εορτή / Πακέτο"]
