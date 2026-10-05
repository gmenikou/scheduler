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
DEFAULT_DOCTORS = ["Χριστίνα", "Αθηνά", "Μαρία", "Ηλία", "Αλέξανδρος", "Εύα", "Έλενα"]

DEFAULT_DOCTOR_COLORS = {
    "Έλενα": (255, 182, 193),
    "Εύα": (152, 251, 152),
    "Μαρία": (176, 196, 222),
    "Αθηνά": (255, 250, 205),
    "Αλέξανδρος": (221, 160, 221),
    "Ηλία": (175, 238, 238),
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

def sync_state_to_github():
    if not os.path.exists(STATE_FILE):
        return False, "Το τοπικό αρχείο κατάστασης δεν υπάρχει."
    try:
        if hasattr(str_lit, "secrets") and "GITHUB_TOKEN" in str_lit.secrets and "GITHUB_REPO" in str_lit.secrets:
            token = str_lit.secrets["GITHUB_TOKEN"]
            repo = str_lit.secrets["GITHUB_REPO"]
            path = STATE_FILE
            url = f"https://api.github.com/repos/{repo}/contents/{path}"
            
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                file_content_str = f.read()
                
            sha = None
            get_resp = requests.get(url, headers=headers)
            if get_resp.status_code == 200:
                sha = get_resp.json().get("sha")
                
            encoded_content = base64.b64encode(file_content_str.encode("utf-8")).decode("utf-8")
            payload = {
                "message": "Χειροκίνητη αποθήκευση κατάστασης & συγχρονισμός με GitHub [skip ci]",
                "content": encoded_content,
                "branch": "main"
            }
            if sha:
                payload["sha"] = sha
                
            put_resp = requests.put(url, headers=headers, json=payload)
            if put_resp.status_code in (200, 201):
                return True, "Επιτυχής συγχρονισμός με το GitHub!"
            else:
                return False, f"Σφάλμα GitHub API: {put_resp.status_code}"
        else:
            return False, "Δεν βρέθηκαν τα μυστικά του GitHub (secrets) στο Streamlit."
    except Exception as e:
        return False, f"Σφάλμα συγχρονισμού: {e}"

def load_state_from_file():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
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
    except Exception as e:
        print("Σφάλμα φόρτωσης κατάστασης:", e)
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


def _week_monday(date):
    return date - datetime.timedelta(days=date.weekday())


def _has_nearby_shift(doctor, date, schedule, min_gap=3):
    for d, doc in schedule.items():
        if doc == doctor and d != date and abs((d - date).days) <= min_gap:
            return True
    return False


def _has_fri_sun_same_weekend(doctor, date, schedule, exclude_date=None):
    if date.weekday() not in (4, 6):
        return False
    target_wk = _week_monday(date)
    
    all_shifts = [(d, doc) for d, doc in schedule.items() if d != exclude_date and doc is not None]
    if exclude_date and exclude_date.weekday() in (4, 6):
        all_shifts.append((exclude_date, doctor))
        
    for d, doc in all_shifts:
        if doc == doctor and _week_monday(d) == target_wk:
            if (date.weekday() == 4 and d.weekday() == 6) or (date.weekday() == 6 and d.weekday() == 4):
                return True
    return False


def _has_weekend_in_adjacent_week(doctor, date, schedule, exclude_date=None):
    if date.weekday() not in (4, 5, 6):
        return False
    target_wk = _week_monday(date)
    
    all_shifts = [(d, doc) for d, doc in schedule.items() if d != exclude_date and doc is not None]
    if exclude_date and exclude_date.weekday() in (4, 5, 6):
        all_shifts.append((exclude_date, doctor))
        
    for d, doc in all_shifts:
        if doc == doctor and d.weekday() in (4, 5, 6) and d != date:
            other_wk = _week_monday(d)
            if abs((target_wk - other_wk).days) == 7:
                return True
    return False


def _shifts_in_week(doctor, date, schedule, exclude_date=None):
    wk = _week_monday(date)
    return sum(
        1 for d, doc in schedule.items()
        if doc == doctor and d != exclude_date and _week_monday(d) == wk and doc is not None
    )


def _month_stats(doctor, date, schedule, exclude_date=None):
    total = 0
    weekend_fri_sat_sun_count = 0
    weekdays_in_month = []
    
    month_shifts = [d for d, doc in schedule.items() if doc == doctor and d.year == date.year and d.month == date.month and d != exclude_date and doc is not None]
    if exclude_date and exclude_date.year == date.year and exclude_date.month == date.month:
        month_shifts.append(exclude_date)
        
    for d in month_shifts:
        total += 1
        weekdays_in_month.append(d.weekday())
        if d.weekday() in (4, 5, 6):
            weekend_fri_sat_sun_count += 1
            
    return total, weekend_fri_sat_sun_count, weekdays_in_month


def _within_dynamic_month_cap(doctor, date, schedule, num_docs, holiday_dates, exclude_date=None):
    total, weekend_count, weekdays_in_month = _month_stats(doctor, date, schedule, exclude_date)
    
    if weekend_count > 2:
        return False
        
    if weekdays_in_month.count(4) > 1 or weekdays_in_month.count(5) > 1 or weekdays_in_month.count(6) > 1:
        return False
        
    has_sat = (5 in weekdays_in_month)
    has_sun = (6 in weekdays_in_month)
    if has_sat and has_sun:
        weekdays_count = sum(1 for w in weekdays_in_month if w in (0, 1, 2, 3))
        if total > 5:
            return False
        if total == 5 and weekdays_count < 3:
            return False
            
    return total <= 5


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


def is_valid_assignment(doctor, date, schedule, holiday_dates, num_docs, exclude_date=None,
                        min_gap=3, avoid_consecutive_weekends=True):
    effective_gap = max(3, min_gap) if num_docs > 5 else max(2, min_gap)
    
    if _has_nearby_shift(doctor, date, schedule, min_gap=effective_gap):
        return False
        
    if _has_fri_sun_same_weekend(doctor, date, schedule, exclude_date=exclude_date):
        return False
        
    max_shifts_per_week = 3 if num_docs <= 5 else 2
    if _shifts_in_week(doctor, date, schedule, exclude_date=exclude_date) >= max_shifts_per_week:
        return False
        
    if date.weekday() in (4, 5, 6):
        if avoid_consecutive_weekends and _has_weekend_in_adjacent_week(doctor, date, schedule, exclude_date=exclude_date):
            return False

    if not _within_dynamic_month_cap(doctor, date, schedule, num_docs, holiday_dates, exclude_date=exclude_date):
        return False

    return True


def _global_weekday_total(doctor, wd, schedule, exclude_date=None):
    return sum(
        1 for d, doc in schedule.items()
        if doc == doctor and d != exclude_date and d.weekday() == wd and doc is not None
    )


# ----------------------------
# SCHEDULING LOGIC
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
    holiday_dates = set(holiday_names.keys())
    num_docs = len(doctors_list)
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date, num_docs)

    if initial_week and isinstance(initial_week, (list, tuple)) and len(initial_week) >= 7:
        week_start_monday = start_date - datetime.timedelta(days=start_date.weekday())
        for i in range(7):
            d = week_start_monday + datetime.timedelta(days=i)
            if start_date <= d <= end_date:
                schedule[d] = initial_week[i]

    for d, doc in manual_entries.items():
        if start_date <= d <= end_date and doc in doctors_list:
            schedule[d] = doc

    major_blocks.sort(key=lambda b: b["dates"][0])
    assigned_major_dates = {d: doc for d, doc in schedule.items() if doc is not None}

    doctor_done_packages = defaultdict(set)

    for block in major_blocks:
        block_doc = None
        for d in block["dates"]:
            if d in schedule and schedule[d] is not None:
                block_doc = schedule[d]
                break

        if block_doc:
            for d in block["dates"]:
                if start_date <= d <= end_date and d not in schedule:
                    schedule[d] = block_doc
                if d in schedule and schedule[d] is not None:
                    assigned_major_dates[d] = schedule[d]
            doctor_done_packages[block_doc].add(block["base_name"])

    doctors_with_package_in_cycle = defaultdict(set)
    for block in major_blocks:
        cycle_y = block["cycle_id"]
        for d in block["dates"]:
            if d in schedule and schedule[d] is not None:
                doctors_with_package_in_cycle[cycle_y].add(schedule[d])

    for block in major_blocks:
        cycle_y = block["cycle_id"]
        base_name = block["base_name"]
        
        already_assigned = all(d in schedule and schedule[d] is not None for d in block["dates"])
        if already_assigned:
            continue

        eligible_doctors = [
            doc for doc in doctors_list 
            if doc not in doctors_with_package_in_cycle[cycle_y] 
            and base_name not in doctor_done_packages[doc]
        ]
        
        if not eligible_doctors:
            eligible_doctors = [
                doc for doc in doctors_list 
                if base_name not in doctor_done_packages[doc]
            ]
        if not eligible_doctors:
            eligible_doctors = doctors_list

        best_doc = None
        min_packages_count = float('inf')

        for doc in eligible_doctors:
            pkg_count = len(doctor_done_packages[doc])
            if pkg_count < min_packages_count:
                min_packages_count = pkg_count
                best_doc = doc

        if best_doc is None:
            best_doc = eligible_doctors[0]
            
        for d in block["dates"]:
            if start_date <= d <= end_date and d not in schedule:
                schedule[d] = best_doc
                assigned_major_dates[d] = best_doc
                
        doctors_with_package_in_cycle[cycle_y].add(best_doc)
        doctor_done_packages[best_doc].add(base_name)

    all_days = [start_date + datetime.timedelta(days=i) for i in range(total_days)]
    minor_dates = {d for d in holiday_dates if d not in {bd for block in major_blocks for bd in block["dates"]}}

    def _minor_total(doc, exclude):
        base_v = initial_balance.get(doc, 0) if initial_balance else 0
        real_count = sum(1 for dd, dc in schedule.items() if dc == doc and dd in minor_dates and dd != exclude and dc is not None)
        return base_v + real_count

    special_dates = [
        d for d in all_days
        if d not in schedule and (d.weekday() in (4, 5, 6) or d in holiday_dates)
    ]
    special_dates.sort(key=lambda d: (0 if d in minor_dates else 1 if d.weekday() in (4, 5, 6) else 2, d))

    for d in special_dates:
        chosen = None
        wd = d.weekday()
        is_minor_holiday = d in minor_dates
        
        min_gap_val = 3 if num_docs > 5 else 2
        valid = [doc for doc in doctors_list if is_valid_assignment(
            doc, d, schedule, holiday_dates, num_docs, exclude_date=d,
            min_gap=min_gap_val, avoid_consecutive_weekends=True)]
        
        if valid:
            chosen = min(valid, key=lambda doc: (
                1 if _month_stats(doc, d, schedule, exclude_date=d)[1] >= 2 else 0,
                _minor_total(doc, d) if is_minor_holiday else 0,
                _global_weekday_total(doc, wd, schedule, exclude_date=d),
                _month_stats(doc, d, schedule, exclude_date=d)[0]
            ))

        if chosen is None:
            reasons = []
            for doc in doctors_list:
                doc_reasons = []
                if _has_nearby_shift(doc, d, schedule, min_gap=min_gap_val):
                    doc_reasons.append("Ελάχιστη απόσταση ημερών")
                if _has_fri_sun_same_weekend(doc, d, schedule, exclude_date=d):
                    doc_reasons.append("Παρασκευή-Κυριακή ίδιου Σ/Κ")
                if _shifts_in_week(doc, d, schedule, exclude_date=d) >= (3 if num_docs <= 5 else 2):
                    doc_reasons.append("Όριο εφημεριών εβδομάδας")
                if d.weekday() in (4, 5, 6) and _has_weekend_in_adjacent_week(doc, d, schedule, exclude_date=d):
                    doc_reasons.append("Συνεχόμενα Σαββατοκύριακα")
                if not _within_dynamic_month_cap(doc, d, schedule, num_docs, holiday_dates, exclude_date=d):
                    doc_reasons.append("Μηνιαίο όριο / cap")
                
                if doc_reasons:
                    reasons.append(f"{doc}: {', '.join(doc_reasons)}")
                else:
                    reasons.append(f"{doc}: Γενικός περιορισμός")
            
            tooltip_text = " | ".join(reasons)
            warnings.append(f"{d.strftime('%d/%m/%Y')}: Καμία έγκυρη επιλογή. Έμεινε κενό.")
            empty_tooltips[d] = tooltip_text
            schedule[d] = None
        else:
            schedule[d] = chosen

    for current_date in all_days:
        if current_date in schedule:
            continue

        chosen = None
        min_gap_val = 3 if num_docs > 5 else 2
        valid = [doc for doc in doctors_list if is_valid_assignment(
            doc, current_date, schedule, holiday_dates, num_docs, exclude_date=current_date,
            min_gap=min_gap_val, avoid_consecutive_weekends=True)]
        
        if valid:
            def _total_overall_shifts(doc_name):
                base_v = initial_balance.get(doc_name, 0) if initial_balance else 0
                real_count = sum(1 for dt, dc in schedule.items() if dc == doc_name and dc is not None)
                return base_v + real_count

            def _total_weekdays(doc_name):
                return sum(1 for dt, dc in schedule.items() if dc == doc_name and dt.weekday() in (0, 1, 2, 3) and dc is not None)

            chosen = min(valid, key=lambda doc: (
                _total_overall_shifts(doc),
                _total_weekdays(doc),
                _month_stats(doc, current_date, schedule, exclude_date=current_date)[0]
            ))

        if chosen is None:
            reasons = []
            for doc in doctors_list:
                doc_reasons = []
                if _has_nearby_shift(doc, current_date, schedule, min_gap=min_gap_val):
                    doc_reasons.append("Ελάχιστη απόσταση ημερών")
                if _shifts_in_week(doc, current_date, schedule, exclude_date=current_date) >= (3 if num_docs <= 5 else 2):
                    doc_reasons.append("Όριο εφημεριών εβδομάδας")
                if not _within_dynamic_month_cap(doc, current_date, schedule, num_docs, holiday_dates, exclude_date=current_date):
                    doc_reasons.append("Μηνιαίο όριο / cap")
                
                if doc_reasons:
                    reasons.append(f"{doc}: {', '.join(doc_reasons)}")
                else:
                    reasons.append(f"{doc}: Γενικός περιορισμός")
            
            tooltip_text = " | ".join(reasons)
            warnings.append(f"{current_date.strftime('%d/%m/%Y')}: Καμία έγκυρη επιλογή καθημερινής. Έμεινε κενό.")
            empty_tooltips[current_date] = tooltip_text
            schedule[current_date] = None
        else:
            schedule[current_date] = chosen

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
    for date, doc in schedule.items():
        if doc in counts and doc is not None:
            counts[doc][WEEKDAY_LABELS[date.weekday()]] += 1

    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]

    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date, len(doctors_list))
    
    major_counts = defaultdict(int)
    for block in major_blocks:
        for d in block["dates"]:
            doc = schedule.get(d)
            if doc in doctors_list and doc is not None:
                major_counts[doc] += 1

    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    regular_counts = defaultdict(int)
    for d in regular_hols:
        doc = schedule.get(d)
        if doc in doctors_list and doc is not None:
            regular_counts[doc] += 1

    df["Argies"] = df["Doctor"].apply(lambda doc: major_counts.get(doc, 0) + regular_counts.get(doc, 0))
    df["Total"] = df["Weekdays"] + df["Fri"] + df["Sat"] + df["Sun"] + df["Argies"]
    return df[["Doctor", "Weekdays", "Fri", "Sat", "Sun", "Argies", "Total"]]


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
                        "Ακτινολόγος": doc_str,
                        "Ημερομηνία & Ημέρα": f"{d.strftime('%d/%m/%Y')} ({weekday_str})",
                        "Μεγάλη Εορτή / Πακέτο": package_name
                    })
                
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Κατανομή Μεγάλων Εορτών / Πακέτων ανά Ακτινολόγο", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    for doc in doctors_list:
        pdf.set_font("DejaVu", "B", 13)
        pdf.cell(0, 8, f"Ακτινολόγος: {doc}", align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVu", "B", 10)
        
        col_widths = [50, 45, 95]
        headers = ["Ακτινολόγος", "Ημερομηνία & Ημέρα", "Μεγάλη Εορτή / Πακέτο"]
        for h, w in zip(headers, col_widths):
            pdf.cell(w, 7, h, border=1, align="C")
        pdf.ln()
        
        pdf.set_font("DejaVu", "", 10)
        sorted_items = sorted(doctor_rows[doc], key=lambda x: x["date_obj"])
        if not sorted_items:
            pdf.cell(sum(col_widths), 7, "Δεν υπάρχουν αναθέσεις", border=1, align="C")
            pdf.ln()
        else:
            for item in sorted_items:
                pdf.cell(col_widths[0], 7, str(item["Ακτινολόγος"]), border=1, align="C")
                pdf.cell(col_widths[1], 7, str(item["Ημερομηνία & Ημέρα"]), border=1, align="C")
                pdf.cell(col_widths[2], 7, str(item["Μεγάλη Εορτή / Πακέτο"]), border=1, align="L")
                pdf.ln()
        pdf.ln(4)
        
    return bytes(pdf.output())


def create_regular_holidays_pdf(df):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Χρονολογική Κατανομή Μικρών Αργιών", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    col_widths = [30, 25, 75, 60]
    headers = ["Ημερομηνία", "Ημέρα", "Μικρή Αργία", "Ακτινολόγος"]
    
    pdf.set_font("DejaVu", "B", 11)
    for h, w in zip(headers, col_widths):
        pdf.cell(w, 8, h, border=1, align="C")
    pdf.ln()
    
    pdf.set_font("DejaVu", "", 10)
    if df.empty:
        pdf.cell(sum(col_widths), 8, "Δεν βρέθηκαν μικρές αργίες στην περίοδο", border=1, align="C")
        pdf.ln()
    else:
        for _, row in df.iterrows():
            pdf.cell(col_widths[0], 7, str(row["Ημερομηνία"]), border=1, align="C")
            pdf.cell(col_widths[1], 7, str(row["Ημέρα"], border=1, align="C") if "Ημέρα" in row else pdf.cell(col_widths[1], 7, "", border=1), align="C")
            pdf.cell(col_widths[2], 7, str(row["Μικρή Αργία"]), border=1, align="L")
            pdf.cell(col_widths[3], 7, str(row["Ακτινολόγος"]), border=1, align="C")
            pdf.ln()
            
    return bytes(pdf.output())


# ----------------------------
# STREAMLIT UI APP
# ----------------------------
def main():
    str_lit.set_page_config(page_title="Πρόγραμμα Εφημεριών", layout="wide")
    
    if "doctors" not in str_lit.session_state:
        str_lit.session_state.doctors = DEFAULT_DOCTORS.copy()
    if "initial_week" not in str_lit.session_state:
        str_lit.session_state.initial_week = DEFAULT_DOCTORS[:7]
    if "manual_assignments" not in str_lit.session_state:
        str_lit.session_state.manual_assignments = {}
    if "empty_tooltips" not in str_lit.session_state:
        str_lit.session_state.empty_tooltips = {}
        
    # Αυτόματη φόρτωση κατάστασης αν υπάρχει
    if "schedule" not in str_lit.session_state:
        saved_data = load_state_from_file()
        if saved_data:
            str_lit.session_state.schedule = saved_data["schedule"]
            str_lit.session_state.holiday_names = saved_data["holiday_names"]
            str_lit.session_state.manual_assignments = saved_data["manual_assignments"]
            str_lit.session_state.empty_tooltips = saved_data["empty_tooltips"]
            str_lit.session_state.doctors = saved_data["doctors"]
            str_lit.session_state.initial_week = saved_data["initial_week"]
        else:
            str_lit.session_state.schedule = {}
            str_lit.session_state.holiday_names = {}

    str_lit.title("Σύστημα Αυτόματης Δημιουργίας Προγράμματος Εφημεριών")
    
    with str_lit.sidebar:
        str_lit.header("Ρυθμίσεις & Δεδομένα")
        
        # Κουμπί Αποθήκευσης σε Github
        if str_lit.button("Αποθήκευση σε Github"):
            if "schedule" in str_lit.session_state:
                save_state_to_file(
                    str_lit.session_state.schedule,
                    str_lit.session_state.get("holiday_names", {}),
                    None,
                    str_lit.session_state.manual_assignments,
                    str_lit.session_state.doctors,
                    str_lit.session_state.initial_week,
                    str_lit.session_state.empty_tooltips
                )
                success, msg = sync_state_to_github()
                if success:
                    str_lit.success(msg)
                else:
                    str_lit.error(msg)
            else:
                str_lit.warning("Δεν υπάρχει ενεργό πρόγραμμα για αποθήκευση.")

        str_lit.markdown("---")
        str_lit.subheader("Επιλογή Περιόδου")
        today = datetime.date.today()
        default_start = datetime.date(today.year, today.month, 1)
        if default_start.month == 12:
            default_end = datetime.date(default_start.year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            default_end = datetime.date(default_start.year, default_start.month + 1, 1) - datetime.timedelta(days=1)
            
        start_date = str_lit.date_input("Ημερομηνία Έναρξης", value=default_start)
        end_date = str_lit.date_input("Ημερομηνία Λήξης", value=default_end)

        str_lit.subheader("Διαχείριση Ιατρών")
        doctors_input = str_lit.text_area("Λίστα Ιατρών (ένας ανά γραμμή)", value="\n".join(str_lit.session_state.doctors))
        new_doctors = [doc.strip() for doc in doctors_input.split("\n") if doc.strip()]
        if new_doctors != str_lit.session_state.doctors:
            str_lit.session_state.doctors = new_doctors
            
        if str_lit.button("Δημιουργία / Ενημέρωση Προγράμματος"):
            if start_date > end_date:
                str_lit.error("Η ημερομηνία έναρξης πρέπει να είναι πριν τη λήξη.")
            else:
                schedule, holiday_names, warnings = generate_full_schedule(
                    start_date, end_date, str_lit.session_state.doctors, str_lit.session_state.initial_week, str_lit.session_state.manual_assignments
                )
                str_lit.session_state.schedule = schedule
                str_lit.session_state.holiday_names = holiday_names
                str_lit.session_state.warnings = warnings
                
                # Αυτόματη αποθήκευση τοπικά
                save_state_to_file(
                    schedule, holiday_names, None, str_lit.session_state.manual_assignments,
                    str_lit.session_state.doctors, str_lit.session_state.initial_week, str_lit.session_state.empty_tooltips
                )
                str_lit.success("Το πρόγραμμα δημιουργήθηκε με επιτυχία!")

    # Κύριο περιεχόμενο εφαρμογής
    if "schedule" in str_lit.session_state and str_lit.session_state.schedule:
        str_lit.subheader("Προβολή Προγράμματος & Ισοζυγίου")
        
        tab1, tab2, tab3 = str_lit.tabs(["Ημερολόγιο", "Ισοζύγιο Εφημεριών", "Αναθέσεις & Εορτές"])
        
        with tab1:
            str_lit.write("### Μηνιαίο Ημερολόγιο Εφημεριών")
            # Εμφάνιση προγράμματος σε μορφή πίνακα/ημερολογίου
            sched = str_lit.session_state.schedule
            if sched:
                df_sched = pd.DataFrame(list(sched.items()), columns=["Ημερομηνία", "Ακτινολόγος"])
                df_sched["Ακτινολόγος"] = df_sched["Ακτινολόγος"].fillna("Κενό")
                df_sched["Ημερομηνία"] = pd.to_datetime(df_sched["Ημερομηνία"]).dt.strftime('%d/%m/%Y')
                str_lit.dataframe(df_sched, use_container_width=True)
                
        with tab2:
            str_lit.write("### Ισοζύγιο Εφημεριών ανά Ιατρό")
            balance_df = compute_balance(
                str_lit.session_state.schedule, start_date, end_date, 
                str_lit.session_state.get("holiday_names", {}), str_lit.session_state.doctors
            )
            str_lit.dataframe(balance_df, use_container_width=True)
            
            pdf_bytes = create_balance_pdf(balance_df, start_date, end_date)
            str_lit.download_button(
                label="Λήψη Ισοζυγίου σε PDF",
                data=pdf_bytes,
                file_name="isozigio_efimerion.pdf",
                mime="application/pdf"
            )
            
        with tab3:
            str_lit.write("### Μεγάλες Εορτές / Πακέτα ανά Ιατρό")
            major_df = compute_major_holidays_by_doctor(
                str_lit.session_state.schedule, start_date, end_date, str_lit.session_state.doctors
            )
            str_lit.dataframe(major_df, use_container_width=True)
            
            major_pdf_bytes = create_major_holidays_pdf_by_doctor(
                str_lit.session_state.schedule, start_date, end_date, str_lit.session_state.doctors
            )
            str_lit.download_button(
                label="Λήψη Μεγάλων Εορτών σε PDF",
                data=major_pdf_bytes,
                file_name="megales_eortes.pdf",
                mime="application/pdf"
            )
    else:
        str_lit.info("Παρακαλώ επιλέξτε περίοδο και πατήστε 'Δημιουργία / Ενημέρωση Προγράμματος' από το πλαϊνό μενού.")

if __name__ == "__main__":
    main()
