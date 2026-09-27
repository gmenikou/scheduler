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

PACKAGE_ROTATION_ORDER = {
    "Χριστούγεννα": 1,
    "Κυριακή του Πάσχα": 2,
    "Παραμονή Χριστουγέννων & Μεγάλο Σάββατο": 3,
    "Πρωτοχρονιά": 4,
    "Δευτέρα του Πάσχα": 5,
    "2η Χριστουγέννων & Μεγάλη Παρασκευή": 6,
    "Παραμονή Πρωτοχρονιάς": 7,
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


def _total_shifts_in_month(doctor, date, schedule, exclude_date=None, holiday_dates=None):
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
    for year in range(start_date.year, end_date.year + 1):
        easter = orthodox_easter(year)
        s_sat = easter - datetime.timedelta(days=1)
        g_fri = easter - datetime.timedelta(days=2)
        sun_e = easter
        mon_e = easter + datetime.timedelta(days=1)

        year_blocks = [
            ([datetime.date(year, 12, 25)], "Χριστούγεννα"),
            ([sun_e], "Κυριακή του Πάσχα"),
            ([datetime.date(year, 12, 24), s_sat], "Παραμονή Χριστουγέννων & Μεγάλο Σάββατο"),
            ([datetime.date(year, 1, 1)], "Πρωτοχρονιά"),
            ([mon_e], "Δευτέρα του Πάσχα"),
            ([datetime.date(year, 12, 26), g_fri], "2η Χριστουγέννων & Μεγάλη Παρασκευή"),
            ([datetime.date(year, 12, 31)], "Παραμονή Πρωτοχρονιάς"),
        ]

        for dates, base_name in year_blocks:
            valid_dates = [d for d in dates if start_date <= d <= end_date]
            if valid_dates:
                primary_date = valid_dates[0]
                if primary_date.month < 9:
                    cycle_id = primary_date.year - 1
                else:
                    cycle_id = primary_date.year

                blocks.append({
                    "name": f"{base_name} {year}",
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

    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            schedule[d] = doc

    cycles_dict = defaultdict(list)
    for block in major_blocks:
        cycles_dict[block["cycle_id"]].append(block)

    sorted_cycles = sorted(cycles_dict.keys())
    base_doctors = list(DOCTORS)

    cycle_doctor_assignments = defaultdict(set)
    historical_package_assignments = {}

    for cycle_idx, c_id in enumerate(sorted_cycles):
        cycle_blocks = sorted(cycles_dict[c_id], key=lambda b: b["order"])
        shifted_doctors = base_doctors[cycle_idx % len(base_doctors):] + base_doctors[:cycle_idx % len(base_doctors)]
        available_doctors = list(shifted_doctors)
        
        for b_idx, block in enumerate(cycle_blocks):
            block_dates = block["dates"]
            if any(bd in schedule for bd in block_dates):
                continue
            
            base_name = block["base_name"]
            
            valid_candidates = [
                doc for doc in available_doctors 
                if doc not in cycle_doctor_assignments[c_id]
                and historical_package_assignments.get((doc, base_name)) != c_id - 1
            ]
            
            if not valid_candidates:
                valid_candidates = available_doctors

            assigned_doc = valid_candidates[0] if valid_candidates else available_doctors[0]
                
            if assigned_doc in available_doctors:
                available_doctors.remove(assigned_doc)
                
            cycle_doctor_assignments[c_id].add(assigned_doc)
            historical_package_assignments[(assigned_doc, base_name)] = c_id
            
            primary_date = block_dates[0]
            if not is_valid_assignment(assigned_doc, primary_date, schedule, holiday_dates, exclude_date=None, 
                                       strict_monthly=True, min_gap=3, max_special=1, avoid_consecutive_weekends=True):
                safe_alternatives = [
                    d for d in DOCTORS 
                    if d not in cycle_doctor_assignments[c_id] and
                    is_valid_assignment(d, primary_date, schedule, holiday_dates, exclude_date=None,
                                           strict_monthly=True, min_gap=3, max_special=1, avoid_consecutive_weekends=True)
                ]
                if safe_alternatives:
                    assigned_doc = safe_alternatives[0]
                else:
                    safe_any = [
                        d for d in DOCTORS 
                        if is_valid_assignment(d, primary_date, schedule, holiday_dates, exclude_date=None,
                                               strict_monthly=True, min_gap=3, max_special=1, avoid_consecutive_weekends=True)
                    ]
                    assigned_doc = safe_any[0] if safe_any else min(DOCTORS, key=lambda d: _total_shifts_in_month(d, primary_date, schedule, holiday_dates=holiday_dates))

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
        
        for avoid_cons in (True, False):
            for min_gap in (3, 2, 1, 0):
                for max_special in (1, 2):
                    valid = [doc for doc in DOCTORS if is_valid_assignment(
                        doc, d, schedule, holiday_dates, exclude_date=d,
                        strict_monthly=True, min_gap=min_gap, max_special=max_special, 
                        avoid_consecutive_weekends=avoid_cons)]
                    if valid:
                        chosen = min(valid, key=lambda doc: (
                            _global_weekday_total(doc, wd, schedule, exclude_date=d),
                            _minor_total(doc, d) if d in minor_dates else 0,
                            _special_count_in_month(doc, d, schedule, holiday_dates, exclude_date=d),
                            _total_shifts_in_month(doc, d, schedule, exclude_date=d, holiday_dates=holiday_dates)
                        ))
                        break
                if chosen:
                    break
            if chosen:
                break

        if chosen is None:
            chosen = min(DOCTORS, key=lambda doc: (
                _global_weekday_total(doc, wd, schedule, exclude_date=d),
                not _within_month_cap(doc, d, schedule, exclude_date=d),
                _total_shifts_in_month(doc, d, schedule, exclude_date=d, holiday_dates=holiday_dates)
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
            
            def _total_weekdays(doc_name):
                return sum(1 for dt, dc in schedule.items() if dc == doc_name and dt.weekday() in (0, 1, 2, 3))

            chosen = min(valid, key=lambda doc: (
                _total_weekdays(doc),
                _total_shifts_in_month(doc, current_date, schedule, holiday_dates=holiday_dates)
            ))
            break

        if chosen is None:
            chosen = min(DOCTORS, key=lambda doc: (
                not _within_month_cap(doc, current_date, schedule, exclude_date=current_date),
                _total_shifts_in_month(doc, current_date, schedule, exclude_date=current_date, holiday_dates=holiday_dates)))
            warnings.append(f"{current_date.strftime('%d/%m/%Y')}: καμία έγκυρη επιλογή, ανατέθηκε {chosen}")
        schedule[current_date] = chosen

    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            schedule[d] = doc

    return schedule, holiday_names, warnings


# ----------------------------
# CHRONOLOGICAL SUMMARY FUNCTIONS
# ----------------------------
def compute_major_holidays_chronological_flat(schedule, start_date, end_date):
    blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    sorted_blocks = sorted(blocks, key=lambda b: b["dates"][0])
    
    data = []
    for block in sorted_blocks:
        for d in block["dates"]:
            doc = schedule.get(d, "-")
            weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
            data.append({
                "date_obj": d,
                "Ημερομηνία": d.strftime('%d/%m/%Y'),
                "Ημέρα": weekday_str,
                "Μεγάλη Εορτή / Πακέτο": block["name"],
                "Ακτινολόγος": doc,
            })
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("date_obj").drop(columns=["date_obj"]).reset_index(drop=True)
    return df


def compute_regular_holidays_chronological(schedule, regular_holidays):
    sorted_hols = sorted(regular_holidays.keys())
    data = []
    for d in sorted_hols:
        doc = schedule.get(d, "-")
        weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
        data.append({
            "Ημερομηνία": d.strftime('%d/%m/%Y'),
            "Ημέρα": weekday_str,
            "Μικρή Αργία": regular_holidays[d],
            "Ακτινολόγος": doc,
        })
    return pd.DataFrame(data)


def compute_doctor_chronological_schedule(schedule, start_date, end_date, holiday_names):
    """Αναλυτική λίστα ομαδοποιημένη ανά ιατρό, με σπασμένα πακέτα, ημερολογιακή σειρά και στήλες: Ακτινολόγος, Ημερομηνία Αργίας, Περιγραφή Αργίας"""
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    major_lookup = {d: block["name"] for block in major_blocks for d in block["dates"]}
    
    doctor_schedules = {doc: [] for doc in DOCTORS}
    
    sorted_dates = sorted([d for d in schedule.keys() if start_date <= d <= end_date])
    for d in sorted_dates:
        doc = schedule[d]
        if doc not in doctor_schedules:
            continue
            
        weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
        
        if d in all_major_dates:
            desc = f"Μεγάλη Εορτή: {major_lookup.get(d, 'Πακέτο')}"
        elif d in holiday_names:
            desc = f"Μικρή Αργία: {holiday_names[d]}"
        elif d.weekday() == 5:
            desc = "Σάββατο"
        elif d.weekday() == 6:
            desc = "Κυριακή"
        else:
            desc = "Καθημερινή"
            
        doctor_schedules[doc].append({
            "date_obj": d,
            "Ακτινολόγος": doc,
            "Ημερομηνία Αργίας": f"{d.strftime('%d/%m/%Y')} ({weekday_str})",
            "Περιγραφή Αργίας": desc
        })
        
    formatted_doctor_schedules = {}
    for doc, items in doctor_schedules.items():
        df_doc = pd.DataFrame(items)
        if not df_doc.empty:
            df_doc = df_doc.sort_values("date_obj")
            df_doc = df_doc[["Ακτινολόγος", "Ημερομηνία Αργίας", "Περιγραφή Αργίας"]].reset_index(drop=True)
        formatted_doctor_schedules[doc] = df_doc
        
    return formatted_doctor_schedules


def compute_balance(schedule, start_date, end_date, holiday_names):
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in DOCTORS}
    for date, doc in schedule.items():
        if doc in counts:
            counts[doc][WEEKDAY_LABELS[date.weekday()]] += 1

    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]

    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    major_flat_df = compute_major_holidays_chronological_flat(schedule, start_date, end_date)
    major_counts = major_flat_df["Ακτινολόγος"].value_counts().to_dict() if not major_flat_df.empty else {}

    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    regular_df = compute_regular_holidays_chronological(schedule, regular_hols)
    regular_counts = regular_df["Ακτινολόγος"].value_counts().to_dict() if not regular_df.empty else {}

    df["Αργίες"] = df["Doctor"].apply(lambda doc: major_counts.get(doc, 0) + regular_counts.get(doc, 0))
    df["Total"] = df["Weekdays"] + df["Fri"] + df["Sat"] + df["Sun"]
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


def create_major_holidays_pdf(schedule, start_date, end_date):
    df = compute_major_holidays_chronological_flat(schedule, start_date, end_date)
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, "Ημερολογιακή Ανάλυση Μεγάλων Εορτών (Σπασμένα Πακέτα)", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    col_widths = [30, 20, 95, 45]
    headers = ["Ημερομηνία", "Ημέρα", "Μεγάλη Εορτή / Πακέτο", "Ακτινολόγος"]
    
    pdf.set_font("DejaVu", "B", 10)
    for h, w in zip(headers, col_widths):
        pdf.cell(w, 8, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("DejaVu", "", 9)
    for _, row in df.iterrows():
        pdf.cell(col_widths[0], 8, str(row["Ημερομηνία"]), border=1, align="C")
        pdf.cell(col_widths[1], 8, str(row["Ημέρα"]), border=1, align="C")
        pdf.cell(col_widths[2], 8, str(row["Μεγάλη Εορτή / Πακέτο"]), border=1, align="L")
        pdf.cell(col_widths[3], 8, str(row["Ακτινολόγος"]), border=1, align="C")
        pdf.ln()
        
    return bytes(pdf.output())


def create_calendar_pdf(schedule, holiday_names):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    months_data = defaultdict(dict)
    for date, doc in schedule.items():
        months_data[(date.year, date.month)][date] = doc

    for (year, month), month_sched in sorted(months_data.items()):
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 16)
        pdf.cell(0, 10, f"Πρόγραμμα Εφημεριών – {GREEK_MONTHS[month]} {year}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        col_w = 38
        row_h = 24
        pdf.set_font("DejaVu", "B", 11)
        for wd_label in GREEK_WEEKDAY_LABELS:
            pdf.cell(col_w, 8, wd_label, border=1, align="C")
        pdf.ln()

        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdatescalendar(year, month)

        for week in weeks:
            start_x = pdf.get_x()
            start_y = pdf.get_y()
            for i, day in enumerate(week):
                x = start_x + (i * col_w)
                y = start_y
                pdf.set_xy(x, y)
                
                if day.month == month:
                    doc = month_sched.get(day, "")
                    is_hol = day in holiday_names
                    
                    doc_color = DOCTOR_COLORS.get(doc, (245, 245, 245))
                    pdf.set_fill_color(*doc_color)
                    
                    if is_hol:
                        pdf.set_draw_color(217, 83, 79)
                        pdf.set_line_width(0.8)
                    else:
                        pdf.set_draw_color(0, 0, 0)
                        pdf.set_line_width(0.2)
                    
                    pdf.cell(col_w, row_h, "", border=1, fill=True)
                    
                    pdf.set_draw_color(0, 0, 0)
                    pdf.set_line_width(0.2)
                    
                    pdf.set_xy(x, y + 2)
                    pdf.set_font("DejaVu", "B", 10)
                    pdf.cell(col_w, 5, str(day.day), align="C", new_x="LMARGIN", new_y="NEXT")
                    
                    pdf.set_xy(x, y + 8)
                    pdf.set_font("DejaVu", "", 9)
                    pdf.cell(col_w, 5, doc, align="C", new_x="LMARGIN", new_y="NEXT")
                    
                    if is_hol:
                        pdf.set_xy(x, y + 14)
                        pdf.set_font("DejaVu", "", 7)
                        pdf.cell(col_w, 4, holiday_names[day][:18], align="C", new_x="LMARGIN", new_y="NEXT")
                else:
                    pdf.set_fill_color(240, 240, 240)
                    pdf.set_draw_color(0, 0, 0)
                    pdf.set_line_width(0.2)
                    pdf.cell(col_w, row_h, "", border=1, fill=True)
            
            pdf.set_xy(start_x, start_y + row_h)
            
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
    ("balance", None), ("initial_week", None), ("warnings", []),
    ("start_date", datetime.date.today()),
]:
    if key not in st.session_state:
        st.session_state[key] = default

left_col, right_col = st.columns([0.35, 0.65])

with left_col:
    st.subheader("📊 Κατάσταση Εφημεριών Εύρους")
    if st.session_state.start_date and st.session_state.schedule:
        manual_date = st.date_input(
            "Επιλέξτε ημερομηνία για αλλαγή",
            min_value=min(st.session_state.schedule.keys()),
            max_value=max(st.session_state.schedule.keys()),
        )
        manual_doctor = st.selectbox("Επιλογή Ακτινολόγου", DOCTORS)
        if st.button("✅ Επικύρωση"):
            st.session_state.manual_assignments[manual_date] = manual_doctor
            st.session_state.schedule[manual_date] = manual_doctor
            end_d = max(st.session_state.schedule.keys()) if st.session_state.schedule else st.session_state.start_date
            st.session_state.balance = compute_balance(
                st.session_state.schedule, st.session_state.start_date, end_d,
                st.session_state.holiday_names)
            st.session_state.warnings = find_all_violations(st.session_state.schedule)
            st.success(f"Ο/Η {manual_doctor} ανατέθηκε στις {manual_date.strftime('%d/%m/%Y')}")
            st.rerun()

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        end_d = max(st.session_state.schedule.keys()) if st.session_state.schedule else st.session_state.start_date

        st.dataframe(st.session_state.balance, use_container_width=True, height=260)

        if st.session_state.schedule:
            st.markdown("### 🎄🐣 Ημερολογιακή Ανάλυση Μεγάλων Εορτών (Σπασμένα Πακέτα)")
            major_flat_df = compute_major_holidays_chronological_flat(
                st.session_state.schedule, st.session_state.start_date, end_d)
            st.dataframe(major_flat_df, use_container_width=True, height=220)
            
            pdf_major_bytes = create_major_holidays_pdf(st.session_state.schedule, st.session_state.start_date, end_d)
            st.download_button("📄 PDF Μεγάλων Εορτών (Ημερολογιακά)", pdf_major_bytes, file_name="major_holidays_flat.pdf", mime="application/pdf")

        if st.session_state.holiday_names:
            major_blocks = get_major_holiday_blocks_in_range(st.session_state.start_date, end_d)
            all_major_dates = {d for block in major_blocks for d in block["dates"]}
            regular_hols = {d: n for d, n in st.session_state.holiday_names.items()
                            if d not in all_major_dates}
            if regular_hols:
                with st.expander("🎈 Ημερολογιακή Ανάλυση Μικρών Αργιών"):
                    regular_df = compute_regular_holidays_chronological(st.session_state.schedule, regular_hols)
                    st.dataframe(regular_df, use_container_width=True)

        # Ομαδοποιημένη προοπτική ανά ιατρό (με καρτέλες για κάθε γιατρό) και ταξινόμηση χρονολογικά
        if st.session_state.schedule:
            st.markdown("---")
            st.markdown("### 👨‍⚕️👩‍⚕️ Ομαδοποιημένο Πρόγραμμα ανά Ιατρό")
            doc_schedules = compute_doctor_chronological_schedule(
                st.session_state.schedule, st.session_state.start_date, end_d, st.session_state.holiday_names
            )
            doc_tabs = st.tabs(DOCTORS)
            for idx, doc_name in enumerate(DOCTORS):
                with doc_tabs[idx]:
                    d_df = doc_schedules.get(doc_name, pd.DataFrame())
                    if not d_df.empty:
                        st.dataframe(d_df, use_container_width=True, height=250)
                        st.caption(f"Συνολικές Εφημερίες Ιατρού: **{len(d_df)}**")
                    else:
                        st.info("Δεν υπάρχουν εφημερίες για αυτόν τον ιατρό στην επιλεγμένη περίοδο.")

        st.markdown("---")
        try:
            pdf_bytes = create_balance_pdf(st.session_state.balance, st.session_state.start_date, end_d)
            st.download_button("📄 Κατέβασε Ισορροπία σε PDF", pdf_bytes,
                               file_name="balance_summary.pdf", mime="application/pdf")
        except Exception as e:
            st.error(f"Σφάλμα δημιουργίας PDF: {e}")
            
        if st.session_state.schedule:
            try:
                pdf_cal_bytes = create_calendar_pdf(st.session_state.schedule, st.session_state.holiday_names)
                st.download_button("📅 Κατέβασε Πρόγραμμα (Landscape / 1 σελίδα ανά μήνα) σε PDF", pdf_cal_bytes,
                                   file_name="monthly_schedule_landscape.pdf", mime="application/pdf")
            except Exception as e:
                st.error(f"Σφάλμα δημιουργίας ημερολογίου PDF: {e}")

with right_col:
    selected_date = st.date_input("Ημερομηνία έναρξης:", datetime.date.today())
    week_dates = [selected_date - datetime.timedelta(days=selected_date.weekday())
                  + datetime.timedelta(days=i) for i in range(7)]

    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            initial_week[d] = st.selectbox(d.strftime("%a %d/%m"), DOCTORS, index=i % 7, key=f"doc_{d}")

    if st.button("💾 Αποθήκευση Αρχικής Ρότας"):
        st.session_state.initial_week = [initial_week[d] for d in sorted(initial_week)]
        st.session_state.start_date = week_dates[0]
        st.rerun()

    if st.session_state.initial_week:
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start date", st.session_state.start_date)
        with c2:
            end_date = st.date_input("End date", start_date)

        if st.button("🗓️ Δημιουργία Προγράμματος"):
            sch, hols, warns = generate_full_schedule(
                start_date, end_date, st.session_state.initial_week,
                manual_assignments=st.session_state.manual_assignments,
            )
            st.session_state.schedule = sch
            st.session_state.holiday_names = hols
            st.session_state.warnings = warns
            st.session_state.balance = compute_balance(sch, start_date, end_date, hols)
            st.rerun()

    if st.session_state.warnings:
        with st.expander("⚠️ Προειδοποιήσεις / Παραβάσεις Κανόνων", expanded=False):
            for w in st.session_state.warnings:
                st.warning(w)

    if st.session_state.get("schedule") is not None:
        st.markdown("---")
        st.subheader("📅 Μηνιαίο Πρόγραμμα Εφημεριών")
        display_calendar(st.session_state.schedule, st.session_state.holiday_names)
