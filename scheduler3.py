import streamlit as str_lit
import datetime
import calendar
import pandas as pd
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

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
def get_doctor_color(doc_name, doctors_list):
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


def _has_weekend_in_adjacent_week(doctor, date, schedule):
    if date.weekday() not in (5, 6):
        return False
    target_wk = _week_monday(date)
    for d, doc in schedule.items():
        if doc == doctor and d.weekday() in (5, 6):
            other_wk = _week_monday(d)
            if abs((target_wk - other_wk).days) == 7:
                return True
    return False


def _shifts_in_week(doctor, date, schedule, exclude_date=None):
    wk = _week_monday(date)
    return sum(
        1 for d, doc in schedule.items()
        if doc == doctor and d != exclude_date and _week_monday(d) == wk
    )


def _total_shifts_in_month(doctor, date, schedule, exclude_date=None):
    return sum(
        1 for d, doc in schedule.items()
        if d != exclude_date and doc == doctor
        and d.year == date.year and d.month == date.month
    )


def _special_bucket(date, holiday_dates):
    if date.weekday() == 5:
        return "sat"
    if date.weekday() == 6:
        return "sun"
    if date in holiday_dates:
        return "hol"
    return None


def _special_count_in_month(doctor, date, schedule, holiday_dates, exclude_date=None):
    bucket = _special_bucket(date, holiday_dates)
    if bucket is None:
        return 0
    return sum(
        1 for d, doc in schedule.items()
        if doc == doctor and d != exclude_date
        and d.year == date.year and d.month == date.month
        and _special_bucket(d, holiday_dates) == bucket
    )


def _month_stats(doctor, date, schedule, exclude_date=None):
    total, has_sat, has_sun = 0, False, False
    for d, doc in schedule.items():
        if d == exclude_date or doc != doctor:
            continue
        if d.year == date.year and d.month == date.month:
            total += 1
            if d.weekday() == 5:
                has_sat = True
            elif d.weekday() == 6:
                has_sun = True
    return total, has_sat, has_sun


def _within_dynamic_month_cap(doctor, date, schedule, num_docs, exclude_date=None):
    total, _, _ = _month_stats(doctor, date, schedule, exclude_date)
    total += 1
    _, days_in_month = calendar.monthrange(date.year, date.month)
    base_limit = (days_in_month // num_docs) + 2
    return total <= base_limit


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


def get_major_holiday_blocks_in_range(start_date, end_date):
    blocks = []
    PACKAGE_ROTATION_ORDER = {
        "Πρωτοχρονιά (1/1)": 0,
        "Χριστούγεννα (25/12)": 1,
        "Παραμονή Πρωτοχρονιάς (31/12)": 2,
        "Κυριακή του Πάσχα": 3,
        "Δευτέρα του Πάσχα": 4,
        "Μεγάλο Σάββατο + 24/12": 5,
        "Μεγάλη Παρασκευή + 26/12": 6,
    }
    
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

        for dates, base_name in year_blocks:
            valid_dates = [d for d in dates if start_date <= d <= end_date]
            if valid_dates:
                blocks.append({
                    "name": f"{base_name} ({y}-{y+1})",
                    "base_name": base_name,
                    "dates": valid_dates,
                    "cycle_id": y,
                    "order": PACKAGE_ROTATION_ORDER.get(base_name, 99)
                })
    return blocks


def is_valid_assignment(doctor, date, schedule, holiday_dates, num_docs, exclude_date=None,
                        min_gap=3, max_special=1, avoid_consecutive_weekends=True):
    effective_gap = min(min_gap, 1 if num_docs <= 4 else 2 if num_docs == 5 else 3)
    
    if _has_nearby_shift(doctor, date, schedule, min_gap=effective_gap):
        return False
    if _shifts_in_week(doctor, date, schedule, exclude_date=exclude_date) >= (2 if num_docs > 4 else 3):
        return False
    if _special_count_in_month(doctor, date, schedule, holiday_dates, exclude_date=exclude_date) >= max_special:
        return False
    if avoid_consecutive_weekends and num_docs > 4 and _has_weekend_in_adjacent_week(doctor, date, schedule):
        return False
    if not _within_dynamic_month_cap(doctor, date, schedule, num_docs, exclude_date=exclude_date):
        return False
    return True


def _global_weekday_total(doctor, wd, schedule, exclude_date=None):
    return sum(
        1 for d, doc in schedule.items()
        if doc == doctor and d != exclude_date and d.weekday() == wd
    )


# ----------------------------
# SCHEDULING LOGIC
# ----------------------------
def generate_full_schedule(start_date, end_date, doctors_list, initial_week, manual_entries=None):
    manual_entries = manual_entries or {}
    schedule = {}
    warnings = []

    total_days = (end_date - start_date).days + 1
    holiday_names = get_holidays_in_range(start_date, end_date)
    holiday_dates = set(holiday_names.keys())
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)

    num_docs = len(doctors_list)

    if initial_week and isinstance(initial_week, (list, tuple)) and len(initial_week) >= 7:
        week_start_monday = start_date - datetime.timedelta(days=start_date.weekday())
        for i in range(7):
            d = week_start_monday + datetime.timedelta(days=i)
            if start_date <= d <= end_date:
                schedule[d] = initial_week[i]

    # Έλεγχος και ενσωμάτωση χειροκίνητων αναθέσεων με προειδοποιήσεις
    for d, doc in manual_entries.items():
        if start_date <= d <= end_date and doc in doctors_list:
            if _has_nearby_shift(doc, d, schedule, min_gap=2):
                warnings.append(f"⚠️️ [Χειροκίνητη Ανάθεση] {d.strftime('%d/%m/%Y')}: Ο/Η {doc} έχει κοντινή εφημερίδα (παραβίαση κενού ασφαλείας).")
            schedule[d] = doc

    major_blocks.sort(key=lambda b: b["dates"][0])
    assigned_major_dates = {}

    for block in major_blocks:
        block_already_assigned = any(d in schedule for d in block["dates"])
        if block_already_assigned:
            for d in block["dates"]:
                if d in schedule:
                    assigned_major_dates[d] = schedule[d]
            continue

        cycle_y = block["cycle_id"]
        order_idx = block["order"]
        base_idx = (order_idx + cycle_y) % num_docs
        
        best_doc = None
        for offset in range(num_docs):
            doc_idx = (base_idx + offset) % num_docs
            doc = doctors_list[doc_idx]
            
            has_conflict = False
            for d_existing, d_doc in assigned_major_dates.items():
                if d_doc == doc:
                    for b_date in block["dates"]:
                        if abs((b_date - d_existing).days) < (7 if num_docs <= 4 else 14):
                            has_conflict = True
                            break
                if has_conflict:
                    break
            
            if not has_conflict:
                best_doc = doc
                break
        
        if best_doc is None:
            best_doc = doctors_list[base_idx]
            
        for d in block["dates"]:
            if start_date <= d <= end_date and d not in schedule:
                schedule[d] = best_doc
                assigned_major_dates[d] = best_doc

    all_days = [start_date + datetime.timedelta(days=i) for i in range(total_days)]
    minor_dates = {d for d in holiday_dates if d not in {bd for block in major_blocks for bd in block["dates"]}}

    def _minor_total(doc, exclude):
        return sum(1 for dd, dc in schedule.items()
                   if dc == doc and dd in minor_dates and dd != exclude)

    special_dates = [
        d for d in all_days
        if d not in schedule and (d.weekday() in (4, 5, 6) or d in holiday_dates)
    ]
    special_dates.sort(key=lambda d: (0 if d in minor_dates else 1 if d.weekday() in (5, 6) else 2, d))

    for d in special_dates:
        chosen = None
        wd = d.weekday()
        is_minor_holiday = d in minor_dates
        
        for avoid_cons in (True, False):
            for min_gap in (3, 2, 1, 0):
                for max_special in (1, 2, 3):
                    valid = [doc for doc in doctors_list if is_valid_assignment(
                        doc, d, schedule, holiday_dates, num_docs, exclude_date=d,
                        min_gap=min_gap, max_special=max_special, 
                        avoid_consecutive_weekends=avoid_cons)]
                    if valid:
                        chosen = min(valid, key=lambda doc: (
                            _minor_total(doc, d) if is_minor_holiday else 0,
                            _global_weekday_total(doc, wd, schedule, exclude_date=d),
                            _special_count_in_month(doc, d, schedule, holiday_dates, exclude_date=d),
                            _total_shifts_in_month(doc, d, schedule, exclude_date=d)
                        ))
                        break
                if chosen:
                    break
            if chosen:
                break

        if chosen is None:
            chosen = min(doctors_list, key=lambda doc: (
                _minor_total(doc, d) if is_minor_holiday else 0,
                _global_weekday_total(doc, wd, schedule, exclude_date=d),
                not _within_dynamic_month_cap(doc, d, schedule, num_docs, exclude_date=d),
                _total_shifts_in_month(doc, d, schedule, exclude_date=d)
            ))
            warnings.append(f"{d.strftime('%d/%m/%Y')}: καμία έγκυρη επιλογή, ανατέθηκε {chosen}")
        schedule[d] = chosen

    for current_date in all_days:
        if current_date in schedule:
            continue

        chosen = None
        for min_gap in (3, 2, 1, 0):
            valid = [doc for doc in doctors_list if is_valid_assignment(
                doc, current_date, schedule, holiday_dates, num_docs, exclude_date=current_date,
                min_gap=min_gap, avoid_consecutive_weekends=False)]
            if not valid:
                continue
            
            def _total_overall_shifts(doc_name):
                return sum(1 for dt, dc in schedule.items() if dc == doc_name)

            def _total_weekdays(doc_name):
                return sum(1 for dt, dc in schedule.items() if dc == doc_name and dt.weekday() in (0, 1, 2, 3))

            chosen = min(valid, key=lambda doc: (
                _total_overall_shifts(doc),
                _total_weekdays(doc),
                _total_shifts_in_month(doc, current_date, schedule, exclude_date=current_date)
            ))
            break

        if chosen is None:
            chosen = min(doctors_list, key=lambda doc: (
                not _within_dynamic_month_cap(doc, current_date, schedule, num_docs, exclude_date=current_date),
                _total_shifts_in_month(doc, current_date, schedule, exclude_date=current_date)))
            warnings.append(f"{current_date.strftime('%d/%m/%Y')}: καμία έγκυρη επιλογή, ανατέθηκε {chosen}")
        schedule[current_date] = chosen

    for d, doc in manual_entries.items():
        if start_date <= d <= end_date and doc in doctors_list:
            schedule[d] = doc

    return schedule, holiday_names, warnings


# ----------------------------
# CHRONOLOGICAL SUMMARY FUNCTIONS
# ----------------------------
def compute_major_holidays_by_doctor(schedule, start_date, end_date, doctors_list):
    doctor_rows = {doc: [] for doc in doctors_list}
    
    for y in range(start_date.year, end_date.year + 1):
        easter = orthodox_easter(y)
        g_fri = easter - datetime.timedelta(days=2)
        s_sat = easter - datetime.timedelta(days=1)
        sun_e = easter
        mon_e = easter + datetime.timedelta(days=1)
        
        individual_hols = [
            (datetime.date(y, 1, 1), "Πρωτοχρονιά (1/1)"),
            (datetime.date(y, 12, 25), "Χριστούγεννα (25/12)"),
            (datetime.date(y, 12, 31), "Παραμονή Πρωτοχρονιάς (31/12)"),
            (sun_e, "Κυριακή του Πάσχα"),
            (mon_e, "Δευτέρα του Πάσχα"),
            (s_sat, "Μεγάλο Σάββατο"),
            (datetime.date(y, 12, 24), "Παραμονή Χριστουγέννων"),
            (g_fri, "Μεγάλη Παρασκευή"),
            (datetime.date(y, 12, 26), "Δεύτερη μέρα Χριστουγέννων"),
        ]
        
        for d, name in individual_hols:
            if start_date <= d <= end_date:
                doc = schedule.get(d, "-")
                if doc in doctor_rows:
                    weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
                    doctor_rows[doc].append({
                        "date_obj": d,
                        "Ακτινολόγος": doc,
                        "Ημερομηνία & Ημέρα": f"{d.strftime('%d/%m/%Y')} ({weekday_str})",
                        "Μεγάλη Εορτή / Πακέτο": name
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
        doc = schedule.get(d, "-")
        weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
        data.append({
            "date_obj": d,
            "Ημερομηνία": d.strftime('%d/%m/%Y'),
            "Ημέρα": weekday_str,
            "Μικρή Αργία": regular_holidays[d],
            "Ακτινολόγος": doc,
        })
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("date_obj").drop(columns=["date_obj"]).reset_index(drop=True)
    return df


def compute_balance(schedule, start_date, end_date, holiday_names, doctors_list):
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in doctors_list}
    for date, doc in schedule.items():
        if doc in counts:
            counts[doc][WEEKDAY_LABELS[date.weekday()]] += 1

    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]

    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    
    major_counts = defaultdict(int)
    for block in major_blocks:
        for d in block["dates"]:
            doc = schedule.get(d)
            if doc in doctors_list:
                major_counts[doc] += 1

    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    regular_counts = defaultdict(int)
    for d in regular_hols:
        doc = schedule.get(d)
        if doc in doctors_list:
            regular_counts[doc] += 1

    df["Αργίες"] = df["Doctor"].apply(lambda doc: major_counts.get(doc, 0) + regular_counts.get(doc, 0))
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
    
    for y in range(start_date.year, end_date.year + 1):
        easter = orthodox_easter(y)
        g_fri = easter - datetime.timedelta(days=2)
        s_sat = easter - datetime.timedelta(days=1)
        sun_e = easter
        mon_e = easter + datetime.timedelta(days=1)
        
        individual_hols = [
            (datetime.date(y, 1, 1), "Πρωτοχρονιά (1/1)"),
            (datetime.date(y, 12, 25), "Χριστούγεννα (25/12)"),
            (datetime.date(y, 12, 31), "Παραμονή Πρωτοχρονιάς (31/12)"),
            (sun_e, "Κυριακή του Πάσχα"),
            (mon_e, "Δευτέρα του Πάσχα"),
            (s_sat, "Μεγάλο Σάββατο"),
            (datetime.date(y, 12, 24), "Παραμονή Χριστουγέννων"),
            (g_fri, "Μεγάλη Παρασκευή"),
            (datetime.date(y, 12, 26), "Δεύτερη μέρα Χριστουγέννων"),
        ]
        
        for d, name in individual_hols:
            if start_date <= d <= end_date:
                doc = schedule.get(d, "-")
                if doc in doctor_rows:
                    weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
                    doctor_rows[doc].append({
                        "date_obj": d,
                        "Ημερομηνία & Ημέρα": f"{d.strftime('%d/%m/%Y')} ({weekday_str})",
                        "Μεγάλη Εορτή / Πακέτο": name
                    })

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    col_widths = [45, 125]
    headers = ["Ημερομηνία & Ημέρα", "Μεγάλη Εορτή / Πακέτο"]

    for doc in doctors_list:
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 14)
        pdf.cell(0, 10, f"Κατάσταση Μεγάλων Εορτών - {doc}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVu", "", 10)
        pdf.cell(0, 6, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
                 align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

        pdf.set_font("DejaVu", "B", 10)
        for h, w in zip(headers, col_widths):
            pdf.cell(w, 8, h, border=1, align="C")
        pdf.ln()

        pdf.set_font("DejaVu", "", 9)
        items = sorted(doctor_rows[doc], key=lambda x: x["date_obj"])
        if items:
            for item in items:
                pdf.cell(col_widths[0], 8, item["Ημερομηνία & Ημέρα"], border=1, align="C")
                pdf.cell(col_widths[1], 8, item["Μεγάλη Εορτή / Πακέτο"], border=1, align="L")
                pdf.ln()
        else:
            pdf.cell(col_widths[0] + col_widths[1], 8, "Καμία μεγάλη εορτή", border=1, align="C")
            pdf.ln()

    return bytes(pdf.output())


def create_yearly_major_holidays_pdf(schedule, year, start_date, end_date):
    easter = orthodox_easter(year)
    g_fri = easter - datetime.timedelta(days=2)
    s_sat = easter - datetime.timedelta(days=1)
    sun_e = easter
    mon_e = easter + datetime.timedelta(days=1)
    
    individual_hols = [
        (datetime.date(year, 1, 1), "Πρωτοχρονιά (1/1)"),
        (datetime.date(year, 12, 25), "Χριστούγεννα (25/12)"),
        (datetime.date(year, 12, 31), "Παραμονή Πρωτοχρονιάς (31/12)"),
        (sun_e, "Κυριακή του Πάσχα"),
        (mon_e, "Δευτέρα του Πάσχα"),
        (s_sat, "Μεγάλο Σάββατο"),
        (datetime.date(year, 12, 24), "Παραμονή Χριστουγέννων"),
        (g_fri, "Μεγάλη Παρασκευή"),
        (datetime.date(year, 12, 26), "Δεύτερη μέρα Χριστουγέννων"),
    ]
    
    valid_hols = [(d, name) for d, name in individual_hols if start_date <= d <= end_date]
    sorted_hols = sorted(valid_hols, key=lambda x: x[0])

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, f"Πρόγραμμα Μεγάλων Εορτών – Έτος {year}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, f"Συγκεντρωτική Κατάσταση Έτους", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    col_widths = [30, 20, 75, 45]
    headers = ["Ημερομηνία", "Ημέρα", "Μεγάλη Εορτή", "Ακτινολόγος"]

    pdf.set_font("DejaVu", "B", 10)
    for h, w in zip(headers, col_widths):
        pdf.cell(w, 8, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("DejaVu", "", 9)
    found_any = False
    for d, name in sorted_hols:
        doc = schedule.get(d, "-")
        weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
        pdf.cell(col_widths[0], 8, d.strftime('%d/%m/%Y'), border=1, align="C")
        pdf.cell(col_widths[1], 8, weekday_str, border=1, align="C")
        pdf.cell(col_widths[2], 8, name, border=1, align="L")
        pdf.cell(col_widths[3], 8, doc, border=1, align="C")
        pdf.ln()
        found_any = True

    if not found_any:
        pdf.cell(sum(col_widths), 8, "Καμία μεγάλη εορτή", border=1, align="C")
        pdf.ln()

    return bytes(pdf.output())


def create_regular_holidays_pdf(schedule, holiday_names, start_date, end_date):
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    
    df = compute_regular_holidays_chronological(schedule, regular_hols)
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, "Κατάσταση Μικρών Αργιών", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    col_widths = [30, 20, 105, 45]
    headers = ["Ημερομηνία", "Ημέρα", "Μικρή Αργία", "Ακτινολόγος"]
    
    pdf.set_font("DejaVu", "B", 10)
    for h, w in zip(headers, col_widths):
        pdf.cell(w, 8, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("DejaVu", "", 9)
    for _, row in df.iterrows():
        pdf.cell(col_widths[0], 8, str(row["Ημερομηνία"]), border=1, align="C")
        pdf.cell(col_widths[1], 8, str(row["Ημέρα"]), border=1, align="C")
        pdf.cell(col_widths[2], 8, str(row["Μικρή Αργία"]), border=1, align="L")
        pdf.cell(col_widths[3], 8, str(row["Ακτινολόγος"]), border=1, align="C")
        pdf.ln()
        
    return bytes(pdf.output())


def create_calendar_pdf(schedule, start_date, end_date, holiday_names, doctors_list):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")
    
    months_to_print = []
    curr = datetime.date(start_date.year, start_date.month, 1)
    while curr <= end_date:
        months_to_print.append((curr.year, curr.month))
        if curr.month == 12:
            curr = datetime.date(curr.year + 1, 1, 1)
        else:
            curr = datetime.date(curr.year, curr.month + 1, 1)
            
    for year, month in months_to_print:
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 16)
        month_name = GREEK_MONTHS[month]
        pdf.cell(0, 10, f"{month_name} {year}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        
        col_width = 38
        row_height = 24
        
        pdf.set_font("DejaVu", "B", 11)
        for d_label in GREEK_WEEKDAY_LABELS:
            pdf.cell(col_width, 8, d_label, border=1, align="C")
        pdf.ln()
        
        cal = calendar.Calendar(firstweekday=0)
        month_weeks = cal.monthdatescalendar(year, month)
        
        for week in month_weeks:
            for day in week:
                x_pos = pdf.get_x()
                y_pos = pdf.get_y()
                
                is_hol = day in holiday_names
                
                if day.month == month and day in schedule:
                    doc = schedule[day]
                    rgb = get_doctor_color(doc, doctors_list)
                    pdf.set_fill_color(rgb[0], rgb[1], rgb[2])
                else:
                    pdf.set_fill_color(255, 255, 255)
                    
                pdf.rect(x_pos, y_pos, col_width, row_height, style="FD")
                
                if day.month == month:
                    pdf.set_xy(x_pos, y_pos + 1.5)
                    pdf.set_font("DejaVu", "B", 10)
                    pdf.cell(col_width, 5, str(day.day), align="C", new_x="LMARGIN", new_y="NEXT")
                    
                    pdf.set_x(x_pos)
                    pdf.set_font("DejaVu", "", 9)
                    doc_str = schedule.get(day, "")
                    pdf.cell(col_width, 5, doc_str, align="C", new_x="LMARGIN", new_y="NEXT")
                    
                    if is_hol:
                        pdf.set_x(x_pos)
                        pdf.set_font("DejaVu", "", 7)
                        hol_name = holiday_names[day]
                        h_short = hol_name[:18] + "..." if len(hol_name) > 18 else hol_name
                        pdf.cell(col_width, 4, h_short, align="C", new_x="LMARGIN", new_y="NEXT")
                
                pdf.set_xy(x_pos + col_width, y_pos)
            pdf.ln(row_height)
            
    return bytes(pdf.output())


def display_calendar(schedule, holiday_names, doctors_list):
    manual_assignments = str_lit.session_state.get("manual_assignments", {})
    last_month = None
    for date in sorted(schedule.keys()):
        month_key = (date.year, date.month)
        if month_key != last_month:
            str_lit.markdown(f"## {GREEK_MONTHS[date.month]} {date.year}")
            last_month = month_key
            headers = str_lit.columns(7)
            for i, d in enumerate(WEEKDAY_LABELS):
                headers[i].markdown(f"**{d}**")
            cal = calendar.Calendar(firstweekday=0)
            for week in cal.monthdatescalendar(date.year, date.month):
                cols = str_lit.columns(7)
                for i, day in enumerate(week):
                    if day.month == date.month:
                        doc = schedule.get(day, "")
                        is_holiday = day in holiday_names
                        icon = " ✏️" if day in manual_assignments else ""
                        holiday_tag = (f"<br><span style='font-size:10px'>🎉 {holiday_names[day]}</span>"
                                       if is_holiday else "")
                        rgb = get_doctor_color(doc, doctors_list)
                        color = '#%02x%02x%02x' % rgb
                        border = "border:2px solid #d9534f;" if is_holiday else ""
                        cols[i].markdown(
                            f"<div style='background-color:{color}; {border} padding:6px; "
                            f"border-radius:4px; text-align:center'>"
                            f"<b>{day.day}</b><br>{doc}{icon}{holiday_tag}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        cols[i].markdown("")


# ----------------------------
# STREAMLIT UI
# ----------------------------
str_lit.set_page_config(page_title="📅 Πρόγραμμα Εφημεριών", layout="wide")
str_lit.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων")
str_lit.markdown("<span style='font-size:14px; color:gray;'>© Γιώργος Μενοίκου, PhD</span>",
            unsafe_allow_html=True)

for key, default in [
    ("manual_assignments", {}), ("schedule", None), ("holiday_names", {}),
    ("balance", None), ("doctors", DEFAULT_DOCTORS),
    ("initial_week", [DEFAULT_DOCTORS[i % len(DEFAULT_DOCTORS)] for i in range(7)]),
    ("warnings", []), ("start_date", datetime.date.today()),
]:
    if key not in str_lit.session_state:
        str_lit.session_state[key] = default

left_col, right_col = str_lit.columns([0.35, 0.65])

with left_col:
    str_lit.subheader("📊 Παραμετροποίηση Εύρους & Ιατρών")
    start_date = str_lit.date_input("Ημερομηνία Έναρξης", value=datetime.date(2026, 2, 2))
    end_date = str_lit.date_input("Ημερομηνία Λήξης", value=datetime.date(2033, 2, 2))

    str_lit.markdown("### 👥 Διαχείριση Ομάδας Ιατρών")
    current_doctors = str_lit.multiselect(
        "Επιλογή & Σειρά Ιατρών",
        options=list(DEFAULT_DOCTOR_COLORS.keys()) + ["Νέος Γιατρός 1", "Νέος Γιατρός 2"],
        default=str_lit.session_state.doctors
    )
    if current_doctors:
        str_lit.session_state.doctors = current_doctors
    else:
        str_lit.warning("Πρέπει να επιλέξετε τουλάχιστον έναν ιατρό.")
        str_lit.stop()

    active_doctors = str_lit.session_state.doctors

    str_lit.markdown("### 📋 Αρχική Σειρά Εβδομάδας (Δευτέρα - Κυριακή)")
    initial_week_list = []
    cols_init = str_lit.columns(7)
    for i, day_label in enumerate(GREEK_WEEKDAY_LABELS):
        with cols_init[i]:
            default_doc = str_lit.session_state.initial_week[i] if i < len(str_lit.session_state.initial_week) else active_doctors[0]
            if default_doc not in active_doctors:
                default_doc = active_doctors[0]
            doc_sel = str_lit.selectbox(day_label, active_doctors, index=active_doctors.index(default_doc), key=f"init_day_{i}")
            initial_week_list.append(doc_sel)
    str_lit.session_state.initial_week = initial_week_list

    # --- ΧΕΙΡΟΚΙΝΗΤΕΣ ΑΝΑΘΕΣΕΙΣ (ΕΝΣΩΜΑΤΩΜΕΝΟ) ---
    str_lit.markdown("### ✏️ Χειροκίνητη Ανάθεση Ημερομηνίας")
    with str_lit.expander("Προσθήκη / Επεξεργασία Χειροκίνητης Εφημερίας"):
        manual_date = str_lit.date_input("Επιλογή Ημερομηνίας", value=datetime.date(2026, 12, 25))
        manual_doc = str_lit.selectbox("Επιλογή Ιατρού", active_doctors, key="manual_doc_sel")
        
        col_m1, col_m2 = str_lit.columns(2)
        with col_m1:
            if str_lit.button("➕ Προσθήκη / Κλείδωμα"):
                str_lit.session_state.manual_assignments[manual_date] = manual_doc
                str_lit.success(f"Κλειδώθηκε: {manual_date.strftime('%d/%m/%Y')} -> {manual_doc}")
        with col_m2:
            if str_lit.button("🗑️ Καθαρισμός Ημερομηνίας"):
                if manual_date in str_lit.session_state.manual_assignments:
                    del str_lit.session_state.manual_assignments[manual_date]
                    str_lit.info(f"Αφαιρέθηκε η χειροκίνητη ανάθεση για {manual_date.strftime('%d/%m/%Y')}")

        if str_lit.session_state.manual_assignments:
            str_lit.markdown("**Τρέχουσες Χειροκίνητες Αναθέσεις:**")
            for d, doc in sorted(str_lit.session_state.manual_assignments.items()):
                str_lit.write(f"- {d.strftime('%d/%m/%Y')}: **{doc}**")

    if str_lit.button("🚀 Δημιουργία Προγράμματος"):
        str_lit.session_state.start_date = start_date
        holiday_names = get_holidays_in_range(start_date, end_date)
        str_lit.session_state.holiday_names = holiday_names
        
        schedule, holiday_names, warnings = generate_full_schedule(
            start_date, end_date, active_doctors, str_lit.session_state.initial_week, str_lit.session_state.manual_assignments
        )
        str_lit.session_state.schedule = schedule
        str_lit.session_state.warnings = warnings
        str_lit.session_state.balance = compute_balance(schedule, start_date, end_date, holiday_names, active_doctors)
        str_lit.success("Το πρόγραμμα δημιουργήθηκε επιτυχώς!")
        
        if warnings:
            str_lit.warning("⚠️ Προειδοποιήσεις συστήματος (συμπεριλαμβανομένων πιθανών παραβιάσεων από χειροκίνητες αναθέσεις):")
            for w in warnings:
                str_lit.write(f"- {w}")

    if str_lit.session_state.balance is not None and not str_lit.session_state.balance.empty:
        end_d = max(str_lit.session_state.schedule.keys()) if str_lit.session_state.schedule else str_lit.session_state.start_date
        
        str_lit.markdown("---")
        str_lit.markdown("### 📥 Επιλογές Εξαγωγής PDF")
        
        pdf_balance_bytes = create_balance_pdf(str_lit.session_state.balance, str_lit.session_state.start_date, end_d)
        str_lit.download_button("📄 Λήψη Ισοζυγίου σε PDF", pdf_balance_bytes, file_name="doctor_balance.pdf", mime="application/pdf")

        if str_lit.session_state.schedule:
            pdf_major_bytes = create_major_holidays_pdf_by_doctor(str_lit.session_state.schedule, str_lit.session_state.start_date, end_d, active_doctors)
            str_lit.download_button("📄 Λήψη Μεγάλων Εορτών ανά Ιατρό σε PDF", pdf_major_bytes, file_name="major_holidays_by_doctor.pdf", mime="application/pdf")

            selected_year = str_lit.selectbox("Επιλογή Έτους για Μεγάλες Εορτές", range(start_date.year, end_date.year + 1))
            if str_lit.button("📥 Λήψη Μεγάλων Εορτών Έτους σε PDF"):
                pdf_yearly_bytes = create_yearly_major_holidays_pdf(str_lit.session_state.schedule, selected_year, str_lit.session_state.start_date, end_d)
                str_lit.download_button(
                    label=f"💾 Αποθήκευση PDF Έτους {selected_year}",
                    data=pdf_yearly_bytes,
                    file_name=f"major_holidays_{selected_year}.pdf",
                    mime="application/pdf"
                )

            major_blocks = get_major_holiday_blocks_in_range(str_lit.session_state.start_date, end_d)
            all_major_dates = {d for block in major_blocks for d in block["dates"]}
            regular_hols = {d: n for d, n in str_lit.session_state.holiday_names.items() if d not in all_major_dates}
            
            pdf_reg_bytes = create_regular_holidays_pdf(str_lit.session_state.schedule, str_lit.session_state.holiday_names, str_lit.session_state.start_date, end_d)
            str_lit.download_button("📄 Λήψη Μικρών Αργιών σε PDF", pdf_reg_bytes, file_name="regular_holidays.pdf", mime="application/pdf")

            pdf_calendar_bytes = create_calendar_pdf(
                str_lit.session_state.schedule,
                str_lit.session_state.start_date,
                end_d,
                str_lit.session_state.holiday_names,
                active_doctors
            )
            str_lit.download_button(
                "📥 Λήψη Πλήρους Ημερολογίου σε Landscape PDF (Ανά Μήνα)",
                pdf_calendar_bytes,
                file_name="calendar_landscape.pdf",
                mime="application/pdf"
            )

        str_lit.markdown("---")
        str_lit.markdown("### 📊 Πίνακας Ισοζυγίου")
        str_lit.dataframe(str_lit.session_state.balance, use_container_width=True, height=260)

        str_lit.markdown("---")
        str_lit.markdown("### 🎄🐣 Μεγάλες Εορτές ανά Ιατρό")
        major_doctor_df = compute_major_holidays_by_doctor(
            str_lit.session_state.schedule, str_lit.session_state.start_date, end_d, active_doctors)
        str_lit.dataframe(major_doctor_df, use_container_width=True, height=220)

        str_lit.markdown("---")
        str_lit.markdown("### 🏛️ Μικρές Αργίες Χρονολογικά")
        reg_df = compute_regular_holidays_chronological(str_lit.session_state.schedule, regular_hols)
        str_lit.dataframe(reg_df, use_container_width=True, height=200)

with right_col:
    str_lit.subheader("🗓️ Ημερολόγιο Εφημεριών")
    if str_lit.session_state.schedule:
        display_calendar(str_lit.session_state.schedule, str_lit.session_state.holiday_names, active_doctors)
    else:
        str_lit.info("Πατήστε «Δημιουργία Προγράμματος» για να εμφανιστεί το ημερολόγιο.")
