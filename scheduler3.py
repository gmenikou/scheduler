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
            ([datetime.date(year, 12, 25)], f"Χριστούγεννα {year}"),
            ([datetime.date(year, 1, 1)], f"Πρωτοχρονιά {year}"),
            ([sun_e], f"Κυριακή του Πάσχα {year}"),
            ([mon_e], f"Δευτέρα του Πάσχα {year}"),
            ([datetime.date(year, 12, 24), s_sat], f"Παραμονή Χριστουγέννων & Μεγάλο Σάββατο {year}"),
            ([datetime.date(year, 12, 26), g_fri], f"2η Χριστουγέννων & Μεγάλη Παρασκευή {year}"),
            ([datetime.date(year, 12, 31)], f"Παραμονή Πρωτοχρονιάς {year}"),
        ]

        for dates, name in year_blocks:
            valid_dates = [d for d in dates if start_date <= d <= end_date]
            if valid_dates:
                blocks.append({"name": name, "dates": valid_dates, "year": year})
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

    doctor_yearly_major_count = {
        doc: {y: 0 for y in range(start_date.year - 1, end_date.year + 2)} for doc in DOCTORS
    }

    for block in major_blocks:
        block_dates = block["dates"]
        if any(bd in schedule for bd in block_dates):
            continue

        block_year = block["year"]
        is_jan_1 = (len(block_dates) == 1 and block_dates[0].month == 1 and block_dates[0].day == 1)
        target_year = block_year if not is_jan_1 else block_year - 1

        eligible = [doc for doc in DOCTORS if doctor_yearly_major_count[doc][target_year] == 0]
        others = [doc for doc in DOCTORS if doc not in eligible]
        by_load = lambda d: sum(doctor_yearly_major_count[d].values())
        candidates = sorted(eligible, key=by_load) + sorted(others, key=by_load)

        best_doc = None
        for doc in candidates:
            if all(is_valid_assignment(doc, bd, schedule, holiday_dates, exclude_date=bd,
                                       strict_monthly=True, min_gap=1, avoid_consecutive_weekends=False) for bd in block_dates):
                best_doc = doc
                break

        if not best_doc:
            best_doc = min(candidates, key=lambda doc: sum(
                _special_count_in_month(doc, bd, schedule, holiday_dates) for bd in block_dates))
            warnings.append(f"{block['name']}: ανατέθηκε χωρίς πλήρη τήρηση κανόνων ({best_doc})")

        for bd in block_dates:
            schedule[bd] = best_doc
        doctor_yearly_major_count[best_doc][target_year] += 1

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
                _total_shifts_in_month(doc, current_date, schedule, holiday_dates=holiday_dates)))
            warnings.append(f"{current_date.strftime('%d/%m/%Y')}: καμία έγκυρη επιλογή, ανατέθηκε {chosen}")
        schedule[current_date] = chosen

    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            schedule[d] = doc

    return schedule, holiday_names, warnings


# ----------------------------
# BALANCE & REPORTING
# ----------------------------
def compute_major_holidays_summary(schedule, start_date, end_date):
    blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    summary = {doc: {"Count": 0, "Details": []} for doc in DOCTORS}

    for block in blocks:
        primary_date = block["dates"][0]
        doc = schedule.get(primary_date, "-")
        if doc in summary:
            summary[doc]["Count"] += 1
            dates_str = ", ".join(d.strftime('%d/%m/%Y') for d in block["dates"])
            summary[doc]["Details"].append(f"• {block['name']} ({dates_str})")

    data = []
    for doc in DOCTORS:
        data.append({
            "Ακτινολόγος": doc,
            "Σύνολο Πακέτων": summary[doc]["Count"],
            "Ανατεθειμένα Πακέτα": "\n".join(summary[doc]["Details"]) if summary[doc]["Details"] else "Κανένα",
        })
    return pd.DataFrame(data)


def compute_regular_holidays_summary(schedule, regular_holidays):
    summary = {doc: {"Count": 0, "Details": []} for doc in DOCTORS}
    for d in sorted(regular_holidays.keys()):
        doc = schedule.get(d, "-")
        if doc in summary:
            summary[doc]["Count"] += 1
            summary[doc]["Details"].append(f"{d.strftime('%d/%m/%Y')} ({regular_holidays[d]})")
    data = []
    for doc in DOCTORS:
        data.append({
            "Ακτινολόγος": doc,
            "Σύνολο": summary[doc]["Count"],
            "Ημερομηνίες & Εορτές": ", ".join(summary[doc]["Details"]) if summary[doc]["Details"] else "Καμία",
        })
    return pd.DataFrame(data)


def compute_balance(schedule, start_date, end_date, holiday_names):
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in DOCTORS}
    for date, doc in schedule.items():
        if doc in counts:
            counts[doc][WEEKDAY_LABELS[date.weekday()]] += 1

    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]

    major_df = compute_major_holidays_summary(schedule, start_date, end_date)
    major_dict = dict(zip(major_df["Ακτινολόγος"], major_df["Σύνολο Πακέτων"]))

    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    regular_df = compute_regular_holidays_summary(schedule, regular_hols)
    regular_dict = dict(zip(regular_df["Ακτινολόγος"], regular_df["Σύνολο"]))

    df["Αργίες"] = df["Doctor"].apply(lambda doc: major_dict.get(doc, 0) + regular_dict.get(doc, 0))
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
    df = compute_major_holidays_summary(schedule, start_date, end_date)
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Κατάσταση Μεγάλων Πακέτων Εορτών", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 11)
    pdf.cell(0, 8, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    col_widths = [35, 25, 130]
    pdf.set_font("DejaVu", "B", 11)
    for h, w in zip(df.columns, col_widths):
        pdf.cell(w, 8, str(h), border=1, align="C")
    pdf.ln()

    pdf.set_font("DejaVu", "", 10)
    for _, row in df.iterrows():
        pdf.cell(col_widths[0], 12, str(row["Ακτινολόγος"]), border=1, align="C")
        pdf.cell(col_widths[1], 12, str(row["Σύνολο Πακέτων"]), border=1, align="C")
        
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.multi_cell(col_widths[2], 6, str(row["Ανατεθειμένα Πακέτα"]), border=1)
        pdf.set_xy(x + col_widths[0] + col_widths[1], y)
        pdf.ln(12)
    return bytes(pdf.output())


def create_regular_holidays_pdf(schedule, holiday_names, start_date, end_date):
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    
    df = compute_regular_holidays_summary(schedule, regular_hols)
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Κατάσταση Μικρών Αργιών", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 11)
    pdf.cell(0, 8, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    col_widths = [35, 20, 135]
    pdf.set_font("DejaVu", "B", 11)
    for h, w in zip(df.columns, col_widths):
        pdf.cell(w, 8, str(h), border=1, align="C")
    pdf.ln()

    pdf.set_font("DejaVu", "", 10)
    for _, row in df.iterrows():
        pdf.cell(col_widths[0], 12, str(row["Ακτινολόγος"]), border=1, align="C")
        pdf.cell(col_widths[1], 12, str(row["Σύνολο"]), border=1, align="C")
        
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.multi_cell(col_widths[2], 6, str(row["Ημερομηνίες & Εορτές"]), border=1)
        pdf.set_xy(x + col_widths[0] + col_widths[1], y)
        pdf.ln(12)
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
        pdf.set_font("DejaVu", "B", 11)
        for wd_label in GREEK_WEEKDAY_LABELS:
            pdf.cell(col_w, 8, wd_label, border=1, align="C")
        pdf.ln()

        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdatescalendar(year, month)

        for week in weeks:
            start_y = pdf.get_y()
            for day in week:
                if day.month == month:
                    doc = month_sched.get(day, "-")
                    is_hol = day in holiday_names
                    cell_str = f"{day.day}\n{doc}"
                    if is_hol:
                        pdf.set_fill_color(255, 220, 220)
                    else:
                        pdf.set_fill_color(250, 250, 250)
                    pdf.multi_cell(col_w, 10, cell_str, border=1, align="C", fill=True)
                    pdf.set_xy(pdf.get_x() + col_w, start_y)
                else:
                    pdf.cell(col_w, 20, "", border=1)
            pdf.ln(20)
            
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
            "Επιλέξετε ημερομηνία για αλλαγή",
            min_value=min(st.session_state.schedule.keys()),
            max_value=max(st.session_state.schedule.keys()),
        )
        manual_doctor = st.selectbox("Επιλογή Ακτινολόγου", DOCTORS)
        if st.button("✅ Επικύρωση"):
            st.session_state.manual_assignments[manual_date] = manual_doctor
            st.session_state.schedule[manual_date] = manual_doctor
            end_d = max(st.session_state.schedule.keys())
            st.session_state.balance = compute_balance(
                st.session_state.schedule, st.session_state.start_date, end_d,
                st.session_state.holiday_names)
            st.session_state.warnings = find_all_violations(st.session_state.schedule)
            st.success(f"Ο/Η {manual_doctor} ανατέθηκε στις {manual_date.strftime('%d/%m/%Y')}")
            st.rerun()

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        st.dataframe(st.session_state.balance, use_container_width=True, height=260)

        if st.session_state.schedule:
            end_d = max(st.session_state.schedule.keys())
            st.markdown("### 🎄🐣 Κατάσταση 7 Πακέτων Μεγάλων Εορτών")
            major_df = compute_major_holidays_summary(
                st.session_state.schedule, st.session_state.start_date, end_d)
            st.dataframe(major_df, use_container_width=True, height=200)
            
            pdf_major_bytes = create_major_holidays_pdf(st.session_state.schedule, st.session_state.start_date, end_d)
            st.download_button("📄 PDF Μεγάλων Εορτών", pdf_major_bytes, file_name="major_holidays.pdf", mime="application/pdf")

        if st.session_state.holiday_names:
            major_blocks = get_major_holiday_blocks_in_range(st.session_state.start_date, end_d)
            all_major_dates = {d for block in major_blocks for d in block["dates"]}
            regular_hols = {d: n for d, n in st.session_state.holiday_names.items()
                            if d not in all_major_dates}
            if regular_hols:
                with st.expander("🎈 Ανάλυση Μικρών Αργιών"):
                    regular_df = compute_regular_holidays_summary(st.session_state.schedule, regular_hols)
                    st.dataframe(regular_df, use_container_width=True)
                    
                    pdf_reg_bytes = create_regular_holidays_pdf(st.session_state.schedule, st.session_state.holiday_names, st.session_state.start_date, end_d)
                    st.download_button("📄 PDF Μικρών Αργιών", pdf_reg_bytes, file_name="regular_holidays.pdf", mime="application/pdf")

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
            end_date = st.date_input("End date", start_date + datetime.timedelta(days=30))

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

    for w in st.session_state.get("warnings", []):
        st.warning(w)

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule, st.session_state.holiday_names)
