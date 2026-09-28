import streamlit as st
import datetime
import calendar
import pandas as pd
from collections import defaultdict
from fpdf import FPDF

# ----------------------------
# CONSTANTS & SETUP
# ----------------------------
DOCTORS = ["Χριστίνα", "Αθηνά", "Μαρία", "Έλια", "Αλέξανδρος", "Εύα", "Έλενα"]

DOCTOR_COLORS = {
    "Έλενα": (255, 182, 193),
    "Εύα": (152, 251, 152),
    "Μαρία": (176, 196, 222),
    "Αθηνά": (255, 250, 205),
    "Αλέξανδρος": (221, 160, 221),
    "Έλια": (175, 238, 238),
    "Χριστίνα": (245, 222, 179),
}

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

# Σειρά προτεραιότητας των 7 πακέτων για τη ρότα ανά έτος
PACKAGE_ROTATION_ORDER = {
    "Πρωτοχρονιά (1/1)": 0,
    "Χριστούγεννα (25/12)": 1,
    "Παραμονή Πρωτοχρονιάς (31/12)": 2,
    "Κυριακή του Πάσχα": 3,
    "Δευτέρα του Πάσχα": 4,
    "Μεγάλο Σάββατο + 24/12": 5,
    "Μεγάλη Παρασκευή + 26/12": 6,
}

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
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


def _within_month_cap(doctor, date, schedule, exclude_date=None):
    total, has_sat, has_sun = _month_stats(doctor, date, schedule, exclude_date)
    total += 1
    if date.weekday() == 5:
        has_sat = True
    elif date.weekday() == 6:
        has_sun = True
    limit = 4 if (has_sat and has_sun) else 5
    return total <= limit


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
    for year in range(start_date.year - 1, end_date.year + 2):
        easter = orthodox_easter(year)
        g_fri = easter - datetime.timedelta(days=2)
        s_sat = easter - datetime.timedelta(days=1)
        sun_e = easter
        mon_e = easter + datetime.timedelta(days=1)

        year_blocks = [
            ([datetime.date(year, 1, 1)], "Πρωτοχρονιά (1/1)"),
            ([datetime.date(year, 12, 25)], "Χριστούγεννα (25/12)"),
            ([datetime.date(year, 12, 31)], "Παραμονή Πρωτοχρονιάς (31/12)"),
            ([sun_e], "Κυριακή του Πάσχα"),
            ([mon_e], "Δευτέρα του Πάσχα"),
            ([s_sat, datetime.date(year, 12, 24)], "Μεγάλο Σάββατο + 24/12"),
            ([g_fri, datetime.date(year, 12, 26)], "Μεγάλη Παρασκευή + 26/12"),
        ]

        for dates, base_name in year_blocks:
            valid_dates = [d for d in dates if start_date <= d <= end_date]
            if valid_dates:
                primary_date = valid_dates[0]
                if primary_date.month >= 9:
                    cycle_id = primary_date.year
                else:
                    cycle_id = primary_date.year - 1

                blocks.append({
                    "name": f"{base_name} ({year})",
                    "base_name": base_name,
                    "dates": valid_dates,
                    "year": year,
                    "cycle_id": cycle_id,
                    "order": PACKAGE_ROTATION_ORDER.get(base_name, 99)
                })
    return blocks


def is_valid_assignment(doctor, date, schedule, holiday_dates, exclude_date=None,
                        strict_monthly=True, min_gap=3, max_special=1, avoid_consecutive_weekends=True):
    if _has_nearby_shift(doctor, date, schedule, min_gap=min_gap):
        return False
    if _shifts_in_week(doctor, date, schedule, exclude_date=exclude_date) >= 2:
        return False
    if _special_count_in_month(doctor, date, schedule, holiday_dates,
                               exclude_date=exclude_date) >= max_special:
        return False
    if avoid_consecutive_weekends and _has_weekend_in_adjacent_week(doctor, date, schedule):
        return False
    if strict_monthly:
        if not _within_month_cap(doctor, date, schedule, exclude_date=exclude_date):
            return False
    return True


def _global_weekday_total(doctor, wd, schedule, exclude_date=None):
    return sum(
        1 for d, doc in schedule.items()
        if doc == doctor and d != exclude_date and d.weekday() == wd
    )


def find_all_violations(schedule):
    return []


# ----------------------------
# SCHEDULING LOGIC
# ----------------------------
def generate_full_schedule(start_date, end_date, initial_week, manual_assignments=None):
    manual_assignments = manual_assignments or {}
    schedule = {}
    warnings = []

    total_days = (end_date - start_date).days + 1
    holiday_names = get_holidays_in_range(start_date, end_date)
    holiday_dates = set(holiday_names.keys())
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)

    if initial_week and isinstance(initial_week, (list, tuple)) and len(initial_week) >= 7:
        week_start_monday = start_date - datetime.timedelta(days=start_date.weekday())
        for i in range(7):
            d = week_start_monday + datetime.timedelta(days=i)
            if start_date <= d <= end_date:
                schedule[d] = initial_week[i]

    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            schedule[d] = doc

    cycles_dict = defaultdict(list)
    for block in major_blocks:
        cycles_dict[block["cycle_id"]].append(block)

    sorted_cycles = sorted(cycles_dict.keys())

    # Ρότα 1-προς-1 ανά έτος: Κάθε χρόνο (cycle) τα 7 πακέτα αλλάζουν γιατρό κυκλικά
    for cycle_idx, c_id in enumerate(sorted_cycles):
        cycle_blocks = sorted(cycles_dict[c_id], key=lambda b: b["order"])
        
        # Κυκλική μετατόπιση βάσει του έτους/κύκλου ώστε διαφορετικός γιατρός να παίρνει κάθε πακέτο ανά έτος
        year_shift = cycle_idx % len(DOCTORS)
        year_doctors = DOCTORS[year_shift:] + DOCTORS[:year_shift]
        
        for block_idx, block in enumerate(cycle_blocks):
            block_dates = block["dates"]
            if any(bd in schedule for bd in block_dates):
                continue
            
            # Το πακέτο (είτε μοναδική μέρα είτε αδιάσπαστο ζευγάρι) δίνεται εξ ολοκλήρου στον ίδιο γιατρό
            assigned_doc = year_doctors[block_idx % len(year_doctors)]
            for bd in block_dates:
                schedule[bd] = assigned_doc

    all_days = [start_date + datetime.timedelta(days=i) for i in range(total_days)]
    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    minor_dates = {d for d in holiday_dates if d not in all_major_dates}

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
                for max_special in (1, 2):
                    valid = [doc for doc in DOCTORS if is_valid_assignment(
                        doc, d, schedule, holiday_dates, exclude_date=d,
                        strict_monthly=True, min_gap=min_gap, max_special=max_special, 
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
            chosen = min(DOCTORS, key=lambda doc: (
                _minor_total(doc, d) if is_minor_holiday else 0,
                _global_weekday_total(doc, wd, schedule, exclude_date=d),
                not _within_month_cap(doc, d, schedule, exclude_date=d),
                _total_shifts_in_month(doc, d, schedule, exclude_date=d)
            ))
            warnings.append(f"{d.strftime('%d/%m/%Y')}: καμία έγκυρη επιλογή, ανατέθηκε {chosen}")
        schedule[d] = chosen

    for current_date in all_days:
        if current_date in schedule:
            continue

        chosen = None
        for min_gap in (3, 2, 1, 0):
            valid = [doc for doc in DOCTORS if is_valid_assignment(
                doc, current_date, schedule, holiday_dates, exclude_date=current_date,
                strict_monthly=True, min_gap=min_gap, avoid_consecutive_weekends=False)]
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
            chosen = min(DOCTORS, key=lambda doc: (
                not _within_month_cap(doc, current_date, schedule, exclude_date=current_date),
                _total_shifts_in_month(doc, current_date, schedule, exclude_date=current_date)))
            warnings.append(f"{current_date.strftime('%d/%m/%Y')}: καμία έγκυρη επιλογή, ανατέθηκε {chosen}")
        schedule[current_date] = chosen

    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            schedule[d] = doc

    return schedule, holiday_names, warnings


# ----------------------------
# CHRONOLOGICAL SUMMARY FUNCTIONS
# ----------------------------
def compute_major_holidays_by_doctor(schedule, start_date, end_date):
    blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    sorted_blocks = sorted(blocks, key=lambda b: b["dates"][0])
    
    doctor_rows = {doc: [] for doc in DOCTORS}
    
    for block in sorted_blocks:
        for d in block["dates"]:
            doc = schedule.get(d, "-")
            if doc in doctor_rows:
                weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
                doctor_rows[doc].append({
                    "date_obj": d,
                    "Ακτινολόγος": doc,
                    "Ημερομηνία & Ημέρα": f"{d.strftime('%d/%m/%Y')} ({weekday_str})",
                    "Μεγάλη Εορτή / Πακέτο": block["base_name"]
                })
                
    all_data = []
    for doc in DOCTORS:
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


def compute_balance(schedule, start_date, end_date, holiday_names):
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in DOCTORS}
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
            if doc in DOCTORS:
                major_counts[doc] += 1

    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    regular_counts = defaultdict(int)
    for d in regular_hols:
        doc = schedule.get(d)
        if doc in DOCTORS:
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
    pdf.cell(0, 10, "Doctor Balance Summary", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"Period: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
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


def create_major_holidays_pdf_by_doctor(schedule, start_date, end_date):
    blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    sorted_blocks = sorted(blocks, key=lambda b: b["dates"][0])
    
    doctor_rows = {doc: [] for doc in DOCTORS}
    for block in sorted_blocks:
        for d in block["dates"]:
            doc = schedule.get(d, "-")
            if doc in doctor_rows:
                weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
                doctor_rows[doc].append({
                    "date_obj": d,
                    "Ημερομηνία & Ημέρα": f"{d.strftime('%d/%m/%Y')} ({weekday_str})",
                    "Μεγάλη Εορτή / Πακέτο": block["base_name"]
                })

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    col_widths = [45, 125]
    headers = ["Ημερομηνία & Ημέρα", "Μεγάλη Εορτή / Πακέτο"]

    for doc in DOCTORS:
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
    blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    year_blocks = [b for b in blocks if b["year"] == year]
    sorted_blocks = sorted(year_blocks, key=lambda b: b["dates"][0])

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
    for block in sorted_blocks:
        for d in block["dates"]:
            doc = schedule.get(d, "-")
            weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
            pdf.cell(col_widths[0], 8, d.strftime('%d/%m/%Y'), border=1, align="C")
            pdf.cell(col_widths[1], 8, weekday_str, border=1, align="C")
            pdf.cell(col_widths[2], 8, block["base_name"], border=1, align="L")
            pdf.cell(col_widths[3], 8, doc, border=1, align="C")
            pdf.ln()
            found_any = True

    if not found_any:
        pdf.cell(sum(col_widths), 8, "Καμία μεγάλη εορτή καταχωρημένη για αυτό το έτος", border=1, align="C")
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


def display_calendar(schedule, holiday_names):
    manual_assignments = st.session_state.get("manual_assignments", {})
    last_month = None
    for date in sorted(schedule.keys()):
        month_key = (date.year, date.month)
        if month_key != last_month:
            st.markdown(f"## {GREEK_MONTHS[date.month]} {date.year}")
            last_month = month_key
            headers = st.columns(7)
            for i, d in enumerate(WEEKDAY_LABELS):
                headers[i].markdown(f"**{d}**")
            cal = calendar.Calendar(firstweekday=0)
            for week in cal.monthdatescalendar(date.year, date.month):
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day.month == date.month:
                        doc = schedule.get(day, "")
                        is_holiday = day in holiday_names
                        icon = " ✏️" if day in manual_assignments else ""
                        holiday_tag = (f"<br><span style='font-size:10px'>🎉 {holiday_names[day]}</span>"
                                       if is_holiday else "")
                        color = '#%02x%02x%02x' % DOCTOR_COLORS.get(doc, (220, 220, 220))
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
st.set_page_config(page_title="📅 Πρόγραμμα Εφημεριών", layout="wide")
st.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων")
st.markdown("<span style='font-size:14px; color:gray;'>© Γιώργος Μενοίκου, PhD</span>",
            unsafe_allow_html=True)

for key, default in [
    ("manual_assignments", {}), ("schedule", None), ("holiday_names", {}),
    ("balance", None), ("initial_week", [DOCTORS[i % len(DOCTORS)] for i in range(7)]), ("warnings", []),
    ("start_date", datetime.date.today()),
]:
    if key not in st.session_state:
        st.session_state[key] = default

left_col, right_col = st.columns([0.35, 0.65])

with left_col:
    st.subheader("📊 Παραμετροποίηση Εύρους")
    start_date = st.date_input("Ημερομηνία Έναρξης", value=datetime.date(2026, 1, 1))
    end_date = st.date_input("Ημερομηνία Λήξης", value=datetime.date(2026, 12, 31))
    
    st.markdown("### 📋 Αρχική Σειρά Εβδομάδας (Δευτέρα - Κυριακή)")
    initial_week_list = []
    cols_init = st.columns(7)
    for i, day_label in enumerate(GREEK_WEEKDAY_LABELS):
        with cols_init[i]:
            default_doc = st.session_state.initial_week[i] if i < len(st.session_state.initial_week) else DOCTORS[i % len(DOCTORS)]
            doc_sel = st.selectbox(day_label, DOCTORS, index=DOCTORS.index(default_doc) if default_doc in DOCTORS else 0, key=f"init_day_{i}")
            initial_week_list.append(doc_sel)
    st.session_state.initial_week = initial_week_list

    if st.button("🚀 Δημιουργία Προγράμματος"):
        st.session_state.start_date = start_date
        holiday_names = get_holidays_in_range(start_date, end_date)
        st.session_state.holiday_names = holiday_names
        
        schedule, holiday_names, warnings = generate_full_schedule(
            start_date, end_date, st.session_state.initial_week, st.session_state.manual_assignments
        )
        st.session_state.schedule = schedule
        st.session_state.warnings = warnings
        st.session_state.balance = compute_balance(schedule, start_date, end_date, holiday_names)
        st.success("Το πρόγραμμα δημιουργήθηκε επιτυχώς!")

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        end_d = max(st.session_state.schedule.keys()) if st.session_state.schedule else st.session_state.start_date
        st.dataframe(st.session_state.balance, use_container_width=True, height=260)

        pdf_balance_bytes = create_balance_pdf(st.session_state.balance, st.session_state.start_date, end_d)
        st.download_button("📄 Λήψη Ισοζυγίου σε PDF", pdf_balance_bytes, file_name="doctor_balance.pdf", mime="application/pdf")

        if st.session_state.schedule:
            st.markdown("---")
            st.markdown("### 🎄🐣 Μεγάλεs Εορτές ανά Ιατρό")
            major_doctor_df = compute_major_holidays_by_doctor(
                st.session_state.schedule, st.session_state.start_date, end_d)
            st.dataframe(major_doctor_df, use_container_width=True, height=220)
            
            pdf_major_bytes = create_major_holidays_pdf_by_doctor(st.session_state.schedule, st.session_state.start_date, end_d)
            st.download_button("📄 Λήψη Μεγάλων Εορτών ανά Ιατρό σε PDF", pdf_major_bytes, file_name="major_holidays_by_doctor.pdf", mime="application/pdf")

            st.markdown("---")
            st.markdown("### 📅 Εξαγωγή Μεγάλων Εορτών ανά Έτος")
            selected_year = st.selectbox("Επιλογή Έτους", range(start_date.year, end_date.year + 1))
            if st.button("📥 Λήψη Μεγάλων Εορτών Έτους σε PDF"):
                pdf_yearly_bytes = create_yearly_major_holidays_pdf(st.session_state.schedule, selected_year, st.session_state.start_date, end_d)
                st.download_button(
                    label=f"💾 Αποθήκευση PDF Έτους {selected_year}",
                    data=pdf_yearly_bytes,
                    file_name=f"major_holidays_{selected_year}.pdf",
                    mime="application/pdf"
                )

            st.markdown("---")
            st.markdown("### 🏛️ Μικρές Αργίες Χρονολογικά")
            major_blocks = get_major_holiday_blocks_in_range(st.session_state.start_date, end_d)
            all_major_dates = {d for block in major_blocks for d in block["dates"]}
            regular_hols = {d: n for d, n in st.session_state.holiday_names.items() if d not in all_major_dates}
            
            reg_df = compute_regular_holidays_chronological(st.session_state.schedule, regular_hols)
            st.dataframe(reg_df, use_container_width=True, height=200)

            pdf_reg_bytes = create_regular_holidays_pdf(st.session_state.schedule, st.session_state.holiday_names, st.session_state.start_date, end_d)
            st.download_button("📄 Λήψη Μικρών Αργιών σε PDF", pdf_reg_bytes, file_name="regular_holidays.pdf", mime="application/pdf")

with right_col:
    st.subheader("🗓️ Ημερολόγιο Εφημεριών")
    if st.session_state.schedule:
        display_calendar(st.session_state.schedule, st.session_state.holiday_names)
    else:
        st.info("Πατήστε «Δημιουργία Προγράμματος» για να εμφανιστεί το ημερολόγιο.")
