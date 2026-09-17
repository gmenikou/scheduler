import streamlit as st
import datetime
import calendar
import pandas as pd
from fpdf import FPDF
from collections import deque

# ----------------------------
# CONSTANTS
# ----------------------------
DOCTORS = ["Χριστίνα", "Αθηνά", "Μαρία", "Έλια", "Αλέξανδρος", "Εύα", "Έλενα"]

DOCTOR_COLORS = {
    "Έλενα": (255, 200, 200),
    "Εύα": (200, 255, 200),
    "Μαρία": (200, 200, 255),
    "Αθηνά": (255, 255, 200),
    "Αλέξανδρος": (255, 200, 255),
    "Έλια": (200, 255, 255),
    "Χριστίνα": (220, 220, 220)
}

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

FIXED_HOLIDAYS = [
    (1, 1, "Πρωτοχρονιά"),
    (1, 6, "Θεοφάνεια"),
    (3, 25, "Ευαγγελισμός / Εθνική Εορτή"),
    (4, 1, "Εθνική Εορτή Κύπρου"),
    (5, 1, "Πρωτομαγιά"),
    (8, 15, "Κοίμηση της Θεοτόκου"),
    (10, 1, "Ημέρα Ανεξαρτησίας Κύπρου"),
    (10, 28, "Ημέρα του Όχι"),
    (12, 25, "Χριστούγεννα"),
    (12, 26, "Δεύτερη μέρα Χριστουγέννων"),
]

# ----------------------------
# HOLIDAY HELPERS
# ----------------------------
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

def get_major_holidays_in_range(start_date, end_date):
    target_dates = {}
    for year in range(start_date.year, end_date.year + 1):
        c_dates = [
            (datetime.date(year, 12, 24), "Παραμονή Χριστουγέννων"),
            (datetime.date(year, 12, 25), "Χριστούγεννα"),
            (datetime.date(year, 12, 26), "Δεύτερη μέρα Χριστουγέννων"),
            (datetime.date(year, 12, 31), "Παραμονή Πρωτοχρονιάς"),
            (datetime.date(year + 1, 1, 1), "Πρωτοχρονιά"),
        ]
        for d, name in c_dates:
            if start_date <= d <= end_date:
                target_dates[d] = name
        
        try:
            easter = orthodox_easter(year)
            e_dates = [
                (easter - datetime.timedelta(days=2), "Μεγάλη Παρασκευή"),
                (easter - datetime.timedelta(days=1), "Μεγάλο Σάββατο"),
                (easter, "Κυριακή του Πάσχα"),
                (easter + datetime.timedelta(days=1), "Δευτέρα του Πάσχα"),
            ]
            for d, name in e_dates:
                if start_date <= d <= end_date:
                    target_dates[d] = name
        except Exception:
            pass
            
    return dict(sorted(target_dates.items()))

def compute_major_holidays_summary(schedule, major_holidays):
    summary = {doc: {"Count": 0, "Details": []} for doc in DOCTORS}
    for d in sorted(major_holidays.keys()):
        doc = schedule.get(d, "-")
        if doc in summary:
            summary[doc]["Count"] += 1
            summary[doc]["Details"].append(f"{d.strftime('%d/%m/%Y')} ({major_holidays[d]})")
    
    data = []
    for doc in DOCTORS:
        data.append({
            "Ακτινολόγος": doc,
            "Σύνολο": summary[doc]["Count"],
            "Ημερομηνίες & Εορτές": ", ".join(summary[doc]["Details"]) if summary[doc]["Details"] else "Καμία"
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
            "Ημερομηνίες & Εορτές": ", ".join(summary[doc]["Details"]) if summary[doc]["Details"] else "Καμία"
        })
    return pd.DataFrame(data)

def _week_monday(date):
    return date - datetime.timedelta(days=date.weekday())

def _has_nearby_shift(doctor, date, schedule, max_gap=2):
    for d, doc in schedule.items():
        if doc == doctor and d != date and abs((d - date).days) <= max_gap:
            return True
    return False

def _shifts_in_week(doctor, date, schedule, exclude_date=None):
    wk = _week_monday(date)
    return sum(
        1 for d, doc in schedule.items()
        if doc == doctor and d != exclude_date and _week_monday(d) == wk
    )

def assign_major_holidays_global_rotation_strict(major_hols_dict, base_schedule, manual_assignments, max_per_week=2, min_gap_days=3, historical_major_counts=None, historical_specific_counts=None):
    working = dict(base_schedule)
    working.update(manual_assignments)
    assignments = {}
    conflicts = set()
    max_gap = min_gap_days - 1

    # Ομαδοποίηση των αργιών ανά έτος
    holidays_by_year = {}
    for d, name in sorted(major_hols_dict.items()):
        if d in manual_assignments:
            assignments[d] = manual_assignments[d]
            working[d] = manual_assignments[d]
            continue
        year_key = d.year if (d.month != 1 or d.day != 1) else d.year - 1 # (Για την Πρωτοχρονιά ανήκει στο προηγούμενο εορταστικό σετ, ή απλά d.year)
        # Ας ομαδοποιήσουμε με βάση το ημερολογιακό έτος
        y_group = d.year
        if y_group not in holidays_by_year:
            holidays_by_year[y_group] = []
        holidays_by_year[y_group].append((d, name))

    standalone_names = ["Χριστούγεννα", "Παραμονή Πρωτοχρονιάς", "Πρωτοχρονιά", "Κυριακή του Πάσχα", "Δευτέρα του Πάσχα"]
    xmas_pairable = ["Παραμονή Χριστουγέννων", "Δεύτερη μέρα Χριστουγέννων"]
    easter_pairable = ["Μεγάλη Παρασκευή", "Μεγάλο Σάββατο"]

    # Συγκεντρώνουμε ΟΛΕΣ τις standalone αργίες χρονολογικά για όλο το εύρος, 
    # ώστε να τρέξει μια ενιαία, αδιάκοπη κυκλική ρότα (global queue) για ΟΛΑ τα χρόνια!
    all_standalone = []
    for year, h_list in sorted(holidays_by_year.items()):
        for d, name in h_list:
            if name in standalone_names:
                all_standalone.append((d, name))

    # --- ΒΗΜΑ 1: Παγκόσμια κυκλική ρότα για ΟΛΕΣ τις κύριες (standalone) αργίες όλου του εύρους ---
    doc_index = 0
    # Dictionary για να ελέγχουμε ποιες κύριες αργίες πήρε ο κάθε γιατρός ανά έτος (για να μην πάρει την ίδια το ίδιο έτος, αν και είναι διαφορετικές)
    def _get_year_standalone_count(doc, year):
        cnt = 0
        for dt, assigned_doc in assignments.items():
            if assigned_doc == doc and dt.year == year and major_hols_dict.get(dt, "") in standalone_names:
                cnt += 1
        return cnt

    for d, holiday_name in all_standalone:
        year = d.year
        ordered_docs = [DOCTORS[(doc_index + i) % len(DOCTORS)] for i in range(len(DOCTORS))]

        chosen = None
        skipped = []
        for candidate in ordered_docs:
            if _get_year_standalone_count(candidate, year) >= 1:
                skipped.append(candidate)
                continue

            nearby_conflict = _has_nearby_shift(candidate, d, working, max_gap=max_gap)
            week_count = _shifts_in_week(candidate, d, working, exclude_date=d)
            weekly_conflict = (week_count + 1) > max_per_week

            if not nearby_conflict and not weekly_conflict:
                chosen = candidate
                doc_index = (DOCTORS.index(candidate) + 1) % len(DOCTORS)
                break
            skipped.append(candidate)

        if chosen is None and skipped:
            for candidate in skipped:
                if _get_year_standalone_count(candidate, year) >= 1:
                    continue
                nearby_conflict = _has_nearby_shift(candidate, d, working, max_gap=max_gap)
                week_count = _shifts_in_week(candidate, d, working, exclude_date=d)
                if not nearby_conflict and (week_count + 1) <= max_per_week:
                    chosen = candidate
                    doc_index = (DOCTORS.index(candidate) + 1) % len(DOCTORS)
                    break

        if chosen is None:
            for candidate in ordered_docs:
                if _get_year_standalone_count(candidate, year) < 1:
                    chosen = candidate
                    conflicts.add(d)
                    doc_index = (DOCTORS.index(candidate) + 1) % len(DOCTORS)
                    break
            if chosen is None:
                chosen = DOCTORS[doc_index % len(DOCTORS)]
                conflicts.add(d)
                doc_index = (doc_index + 1) % len(DOCTORS)

        assignments[d] = chosen
        working[d] = chosen
        if historical_major_counts is not None:
            historical_major_counts[chosen] = historical_major_counts.get(chosen, 0) + 1
        if historical_specific_counts is not None:
            if chosen not in historical_specific_counts:
                historical_specific_counts[chosen] = {}
            historical_specific_counts[chosen][holiday_name] = historical_specific_counts[chosen].get(holiday_name, 0) + 1

    # --- ΒΗΜΑ 2: Ανάθεση των συνδυαστικών/δεύτερων αργιών ανά έτος στους υπόλοιπους 2 γιατρούς ---
    for year, h_list in sorted(holidays_by_year.items()):
        year_xmas_pair = [item for item in h_list if item[1] in xmas_pairable]
        year_easter_pair = [item for item in h_list if item[1] in easter_pairable]

        # Βρίσκουμε ποιοι γιατροί είναι ήδη πιασμένοι από τις standalone σε αυτό το έτος
        year_assigned_docs = {assigned_doc for dt, assigned_doc in assignments.items() if dt.year == year}
        remaining_docs = [doc for doc in DOCTORS if doc not in year_assigned_docs]

        if len(remaining_docs) >= 2 and len(year_xmas_pair) > 0 and len(year_easter_pair) > 0:
            doc1, doc2 = remaining_docs[0], remaining_docs[1]
            pairs_to_assign = [
                (year_xmas_pair[0], doc1),
                (year_easter_pair[0], doc1),
                (year_xmas_pair[1] if len(year_xmas_pair) > 1 else year_xmas_pair[0], doc2),
                (year_easter_pair[1] if len(year_easter_pair) > 1 else year_easter_pair[0], doc2),
            ]
            for (d, holiday_name), candidate in pairs_to_assign:
                assignments[d] = candidate
                working[d] = candidate
                if historical_major_counts is not None:
                    historical_major_counts[candidate] = historical_major_counts.get(candidate, 0) + 1
                if historical_specific_counts is not None:
                    if candidate not in historical_specific_counts:
                        historical_specific_counts[candidate] = {}
                    historical_specific_counts[candidate][holiday_name] = historical_specific_counts[candidate].get(holiday_name, 0) + 1
        else:
            # Fallback
            for d, holiday_name in (year_xmas_pair + year_easter_pair):
                if d in manual_assignments:
                    continue
                candidate = remaining_docs[0] if remaining_docs else DOCTORS[0]
                assignments[d] = candidate
                working[d] = candidate
                if historical_major_counts is not None:
                    historical_major_counts[candidate] = historical_major_counts.get(candidate, 0) + 1
                if historical_specific_counts is not None:
                    if candidate not in historical_specific_counts:
                        historical_specific_counts[candidate] = {}
                    historical_specific_counts[candidate][holiday_name] = historical_specific_counts[candidate].get(holiday_name, 0) + 1

    return assignments, conflicts

def assign_regular_holidays(holiday_dates_sorted, base_schedule, manual_assignments=None, max_per_week=2, min_gap_days=3, historical_regular_counts=None):
    manual_assignments = manual_assignments or {}
    working = dict(base_schedule)
    working.update(manual_assignments)

    assignments = {}
    conflicts = set()
    max_gap = min_gap_days - 1

    for d in holiday_dates_sorted:
        if d in manual_assignments:
            continue

        sorted_doctors = sorted(
            DOCTORS,
            key=lambda doc: (
                historical_regular_counts.get(doc, 0) if historical_regular_counts is not None else 0,
                DOCTORS.index(doc)
            )
        )

        queue = deque(sorted_doctors)
        skipped = []
        chosen = None

        for _ in range(len(queue)):
            candidate = queue.popleft()
            nearby_conflict = _has_nearby_shift(candidate, d, working, max_gap=max_gap)
            week_count = _shifts_in_week(candidate, d, working, exclude_date=d)
            weekly_conflict = (week_count + 1) > max_per_week

            if not nearby_conflict and not weekly_conflict:
                chosen = candidate
                break
            skipped.append(candidate)

        if chosen is None and skipped:
            for _ in range(len(skipped)):
                candidate = skipped.pop(0)
                nearby_conflict = _has_nearby_shift(candidate, d, working, max_gap=max_gap)
                week_count = _shifts_in_week(candidate, d, working, exclude_date=d)

                if not nearby_conflict and (week_count + 1) <= max_per_week:
                    chosen = candidate
                    break
                skipped.append(candidate)

        if chosen is None and skipped:
            chosen = skipped.pop(0)
            conflicts.add(d)

        if chosen is not None:
            assignments[d] = chosen
            working[d] = chosen
            if historical_regular_counts is not None:
                historical_regular_counts[chosen] = historical_regular_counts.get(chosen, 0) + 1

    return assignments, conflicts

# ----------------------------
# HELPERS
# ----------------------------
def get_week_dates(any_date):
    monday = any_date - datetime.timedelta(days=any_date.weekday())
    return [monday + datetime.timedelta(days=i) for i in range(7)]

def generate_base_rota(initial_week, start_date, end_date):
    schedule = {}
    doctor_to_weekday = {doc: i for i, doc in enumerate(initial_week)}
    for i, doc in enumerate(initial_week):
        schedule[start_date + datetime.timedelta(days=i)] = doc
    current_week_start = start_date + datetime.timedelta(days=7)
    while current_week_start <= end_date:
        new_map = {doc: (wd - 2) % 7 for doc, wd in doctor_to_weekday.items()}
        for doc, wd in new_map.items():
            day = current_week_start + datetime.timedelta(days=wd)
            if day <= end_date:
                schedule[day] = doc
        doctor_to_weekday = new_map
        current_week_start += datetime.timedelta(days=7)
    return schedule

def generate_schedule(initial_week, start_date, end_date, holiday_assignments=None, manual_assignments=None):
    schedule = generate_base_rota(initial_week, start_date, end_date)
    if holiday_assignments:
        for d, doc in holiday_assignments.items():
            if start_date <= d <= end_date:
                schedule[d] = doc
    if manual_assignments:
        for d, doc in manual_assignments.items():
            if start_date <= d <= end_date:
                schedule[d] = doc
    return schedule

def compute_balance(schedule, holiday_dates=None):
    holiday_dates = holiday_dates or set()
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in DOCTORS}
    holiday_counts = {doc: 0 for doc in DOCTORS}
    for date, doc in schedule.items():
        if doc not in counts:
            continue
        wd = date.weekday()
        counts[doc][WEEKDAY_LABELS[wd]] += 1
        if date in holiday_dates:
            holiday_counts[doc] += 1
    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]
    df["Αργίες"] = df["Doctor"].map(holiday_counts)
    df["Total"] = df["Weekdays"] + df["Fri"] + df["Sat"] + df["Sun"]
    return df[["Doctor", "Weekdays", "Fri", "Sat", "Sun", "Αργίες", "Total"]]

# ----------------------------
# CALENDAR DISPLAY
# ----------------------------
def display_calendar(schedule):
    manual_assignments = st.session_state.get("manual_assignments", {})
    holiday_names = st.session_state.get("holiday_names", {})
    holiday_conflicts = st.session_state.get("holiday_conflicts", set())
    last_month = None
    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            st.markdown(f"## {month_name}")
            last_month = month_name
            headers = st.columns(7)
            for i, d in enumerate(WEEKDAY_LABELS):
                headers[i].markdown(f"**{d}**")
            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(date.year, date.month)
            for week in weeks:
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day.month == date.month:
                        doc = schedule.get(day, "")
                        is_holiday = day in holiday_names
                        icon = " ✏️" if day in manual_assignments else ""
                        conflict_icon = " ⚠️" if day in holiday_conflicts else ""
                        holiday_tag = f"<br><span style='font-size:10px'>🎉 {holiday_names[day]}{conflict_icon}</span>" if is_holiday else ""
                        color = '#%02x%02x%02x' % DOCTOR_COLORS.get(doc, (220, 220, 220))
                        border = "border:2px solid #d9534f;" if is_holiday else ""
                        cols[i].markdown(
                            f"<div style='background-color:{color}; {border} padding:6px; border-radius:4px; text-align:center'>"
                            f"<b>{day.day}</b><br>{doc}{icon}{holiday_tag}</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        cols[i].markdown("")

# ----------------------------
# PDF EXPORT
# ----------------------------
def create_balance_pdf(df, start_date, end_date, filename="balance_summary.pdf"):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'DejaVuSans.ttf', uni=True)

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Doctor Balance Summary", ln=True, align="C")
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"Period: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}", ln=True, align="C")
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
    pdf.output(filename)
    return filename

def create_major_holidays_pdf(df, start_date, end_date, filename="major_holidays_summary.pdf"):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'DejaVuSans.ttf', uni=True)

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Κατάσταση Εφημεριών 9 Μεγάλων Εορτών", ln=True, align="C")
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}", ln=True, align="C")
    pdf.ln(6)
    
    col_widths = [35, 20, 222]
    pdf.set_font("DejaVu", "B", 11)
    for h, w in zip(df.columns, col_widths):
        pdf.cell(w, 8, str(h), border=1, align="C")
    pdf.ln()
    
    pdf.set_font("DejaVu", "", 10)
    for _, row in df.iterrows():
        pdf.cell(col_widths[0], 10, str(row["Ακτινολόγος"]), border=1, align="C")
        pdf.cell(col_widths[1], 10, str(row["Σύνολο"]), border=1, align="C")
        pdf.multi_cell(col_widths[2], 5, str(row["Ημερομηνίες & Εορτές"]), border=1, align="L")
        pdf.ln(0)
        
    pdf.output(filename)
    return filename

def create_regular_holidays_pdf(df, start_date, end_date, filename="regular_holidays_summary.pdf"):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'DejaVuSans.ttf', uni=True)

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Κατάσταση Εφημεριών Μικρών Αργιών", ln=True, align="C")
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}", ln=True, align="C")
    pdf.ln(6)
    
    col_widths = [35, 20, 222]
    pdf.set_font("DejaVu", "B", 11)
    for h, w in zip(df.columns, col_widths):
        pdf.cell(w, 8, str(h), border=1, align="C")
    pdf.ln()
    
    pdf.set_font("DejaVu", "", 10)
    for _, row in df.iterrows():
        pdf.cell(col_widths[0], 10, str(row["Ακτινολόγος"]), border=1, align="C")
        pdf.cell(col_widths[1], 10, str(row["Σύνολο"]), border=1, align="C")
        pdf.multi_cell(col_widths[2], 5, str(row["Ημερομηνίες & Εορτές"]), border=1, align="L")
        pdf.ln(0)
        
    pdf.output(filename)
    return filename

def create_calendar_pdf(schedule, filename="calendar.pdf"):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'DejaVuSans.ttf', uni=True)
    pdf.set_font("DejaVu", "", 12)

    manual_assignments = st.session_state.get("manual_assignments", {})
    holiday_names = st.session_state.get("holiday_names", {})
    holiday_conflicts = st.session_state.get("holiday_conflicts", set())
    last_month = None
    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            pdf.add_page()
            pdf.set_font("DejaVu", "B", 16)
            pdf.cell(0, 10, month_name, ln=True, align="C")
            pdf.ln(4)
            pdf.set_font("DejaVu", "B", 12)
            col_width = 40
            for wd in WEEKDAY_LABELS:
                pdf.cell(col_width, 8, wd, border=1, align="C")
            pdf.ln()
            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(date.year, date.month)
            pdf.set_font("DejaVu", "", 12)
            cell_height = 20
            for week in weeks:
                x_start = pdf.get_x()
                y_start = pdf.get_y()
                for i, day in enumerate(week):
                    pdf.set_xy(x_start + i * col_width, y_start)
                    if day.month == date.month:
                        doc = schedule.get(day, "")
                        is_holiday = day in holiday_names
                        marker = "*" if day in manual_assignments else ""
                        text = f"{day.day}{marker}\n{doc}"
                        if is_holiday:
                            text += "\n(Αργία!)" if day in holiday_conflicts else "\n(Αργία)"
                            pdf.set_fill_color(255, 225, 225)
                        else:
                            pdf.set_fill_color(*DOCTOR_COLORS.get(doc, (220, 220, 220)))
                        pdf.multi_cell(col_width, 5, text, border=1, align="C", fill=True)
                    else:
                        pdf.set_fill_color(240, 240, 240)
                        pdf.cell(col_width, cell_height, "", border=1, fill=True)
                pdf.ln(cell_height)
            last_month = month_name
    pdf.output(filename)
    return filename

# ----------------------------
# STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="📅 Πρόγραμμα εφημεριών © Γιώργος Μενοίκου,PhD ", layout="wide")
st.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων")
st.markdown(
    "<span style='font-size:14px; color:gray;'>© Γιώργος Μενοίκου, PhD</span>",
    unsafe_allow_html=True
)

if "manual_assignments" not in st.session_state:
    st.session_state.manual_assignments = {}
if "holiday_assignments" not in st.session_state:
    st.session_state.holiday_assignments = {}
if "holiday_names" not in st.session_state:
    st.session_state.holiday_names = {}
if "holiday_conflicts" not in st.session_state:
    st.session_state.holiday_conflicts = set()
if "historical_major_counts" not in st.session_state:
    st.session_state.historical_major_counts = {doc: 0 for doc in DOCTORS}
if "historical_specific_counts" not in st.session_state:
    st.session_state.historical_specific_counts = {doc: {} for doc in DOCTORS}
if "historical_regular_counts" not in st.session_state:
    st.session_state.historical_regular_counts = {doc: 0 for doc in DOCTORS}

for key in ["initial_week", "start_date", "end_date", "schedule", "balance"]:
    if key not in st.session_state:
        st.session_state[key] = None

left_col, right_col = st.columns([0.35, 0.65])

# ----------------------------
# LEFT: Balance & Manual Assignment
# ----------------------------
with left_col:
    st.subheader("📊 Κατάσταση Εφημεριών Εύρους")

    if st.session_state.start_date and st.session_state.end_date:
        manual_date = st.date_input(
            "Επιλέξετε ημερομηνία για αλλαγή",
            min_value=st.session_state.start_date,
            max_value=st.session_state.end_date
        )
        manual_doctor = st.selectbox("Επιλογή Ακτινολόγου", DOCTORS)
        if st.button("✅ Επικύρωση"):
            current_schedule = dict(st.session_state.schedule) if st.session_state.schedule else {}
            check_schedule = {d: doc for d, doc in current_schedule.items() if d != manual_date}
            nearby_conflict = _has_nearby_shift(manual_doctor, manual_date, check_schedule, max_gap=2)
            weekly_conflict = (_shifts_in_week(manual_doctor, manual_date, check_schedule) + 1) > 2

            st.session_state.manual_assignments[manual_date] = manual_doctor
            st.session_state.schedule[manual_date] = manual_doctor
            
            active_holiday_dates = set(st.session_state.holiday_assignments.keys()) if st.session_state.holiday_assignments else set(st.session_state.holiday_names.keys())
            st.session_state.balance = compute_balance(
                st.session_state.schedule,
                holiday_dates=active_holiday_dates
            )

            holiday_note = ""
            if manual_date in st.session_state.holiday_names:
                holiday_note = f" (Αργία: {st.session_state.holiday_names[manual_date]})"
            st.success(f"{manual_doctor} assigned to {manual_date.strftime('%d/%m/%Y')}{holiday_note}")

            if nearby_conflict:
                st.warning(
                    f"⚠️ Ο/Η {manual_doctor} έχει ήδη άλλη εφημερία εντός 3 ημερών από τις "
                    f"{manual_date.strftime('%d/%m/%Y')}. Η ανάθεση έγινε ούτως ή άλλως."
                )
            if weekly_conflict:
                st.warning(
                    f"⚠️ Ο/Η {manual_doctor} θα έχει πάνω από 2 εφημερίες μέσα στην ίδια εβδομάδα με τις "
                    f"{manual_date.strftime('%d/%m/%Y')}. Η ανάθεση έγινε ούτως ή άλλως."
                )

        if st.session_state.holiday_names:
            conflicts = st.session_state.get("holiday_conflicts", set())
            if conflicts:
                st.warning(
                    f"⚠️ Σε {len(conflicts)} αργία(ες) δεν βρέθηκε γιατρός χωρίς σύγκρουση — ελέγξτε τις παρακάτω."
                )
            with st.expander(f"🎉 Αργίες στο διάστημα ({len(st.session_state.holiday_names)})"):
                for d in sorted(st.session_state.holiday_names.keys()):
                    doc = st.session_state.schedule.get(d, "") if st.session_state.schedule else ""
                    flag = " ⚠️" if d in conflicts else ""
                    st.markdown(f"- **{d.strftime('%d/%m/%Y')}** — {st.session_state.holiday_names[d]}: {doc}{flag}")

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        st.dataframe(st.session_state.balance, use_container_width=True, height=260)

        major_hols = get_major_holidays_in_range(st.session_state.start_date, st.session_state.end_date)
        if major_hols:
            with st.expander("🎄🐣 Ανάλυση 9 Μεγάλων Εορτών"):
                major_df = compute_major_holidays_summary(st.session_state.schedule, major_hols)
                st.dataframe(major_df, use_container_width=True)
                
                if st.button("📄 Εξαγωγή αναφοράς 9 μεγάλων εορτών σε PDF"):
                    pdf_hols_file = create_major_holidays_pdf(
                        major_df,
                        st.session_state.start_date,
                        st.session_state.end_date
                    )
                    with open(pdf_hols_file, "rb") as f:
                        st.download_button("⬇️ Κατέβασε αναφορά εορτών σε PDF", f, file_name=pdf_hols_file)

        if st.session_state.holiday_names:
            regular_hols_dict = {d: n for d, n in st.session_state.holiday_names.items() if d not in major_hols}
            if regular_hols_dict:
                with st.expander("🎈 Ανάλυση Μικρών Αργιών"):
                    regular_df = compute_regular_holidays_summary(st.session_state.schedule, regular_hols_dict)
                    st.dataframe(regular_df, use_container_width=True)
                    
                    if st.button("📄 Εξαγωγή αναφοράς μικρών αργιών σε PDF"):
                        pdf_reg_file = create_regular_holidays_pdf(
                            regular_df,
                            st.session_state.start_date,
                            st.session_state.end_date
                        )
                        with open(pdf_reg_file, "rb") as f:
                            st.download_button("⬇️ Κατέβασε αναφορά μικρών αργιών σε PDF", f, file_name=pdf_reg_file)

        if st.button("📄 Εξαγωγή κατάστασης σε PDF"):
            pdf_file = create_balance_pdf(
                st.session_state.balance,
                st.session_state.start_date,
                st.session_state.end_date
            )
            with open(pdf_file, "rb") as f:
                st.download_button("⬇️ Κατέβασε κατάσταση σε PDF", f, file_name=pdf_file)
        if st.button("🖨️ Εξαγωγή ημερολογίου σε PDF"):
            pdf_file = create_calendar_pdf(st.session_state.schedule)
            with open(pdf_file, "rb") as f:
                st.download_button("⬇️ Κατέβασε ημερολόγιο σε PDF", f, file_name=pdf_file)

# ----------------------------
# RIGHT: Initial Week + Schedule Generation
# ----------------------------
with right_col:
    selected_date = st.date_input("Ημερομηνία έναρξης:", datetime.date.today())
    week_dates = get_week_dates(selected_date)

    default_order = DOCTORS
    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            default_idx = DOCTORS.index(default_order[i % 7])
            initial_week[d] = st.selectbox(
                d.strftime("%a %d/%m"),
                DOCTORS,
                index=default_idx,
                key=f"doc_{d}"
            )

    if st.button("💾 Επιλογή Ημερομηνίας Έναρξης"):
        st.session_state.initial_week = [initial_week[d] for d in sorted(initial_week)]
        st.session_state.start_date = week_dates[0]

    if st.session_state.initial_week is None:
        st.stop()

    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start date", st.session_state.start_date)
    with c2:
        end_date = st.date_input("End date", st.session_state.start_date + datetime.timedelta(days=30))

    if st.button("🗓️ Δημιουργία Προγράμματος"):
        holiday_names = get_holidays_in_range(start_date, end_date)
        major_hols = get_major_holidays_in_range(start_date, end_date)
        regular_hols = {d: n for d, n in holiday_names.items() if d not in major_hols}

        base_rota = generate_base_rota(st.session_state.initial_week, start_date, end_date)
        
        # 1. Ενιαία παγκόσμια ρότα για ΟΛΕΣ τις κύριες standalone αργίες όλου του εύρους + μετά οι συνδυαστικές
        major_assignments, major_conflicts_1 = assign_major_holidays_global_rotation_strict(
            major_hols,
            base_rota,
            manual_assignments=st.session_state.manual_assignments,
            max_per_week=2,
            min_gap_days=3,
            historical_major_counts=st.session_state.historical_major_counts,
            historical_specific_counts=st.session_state.historical_specific_counts
        )

        temp_schedule = dict(base_rota)
        temp_schedule.update(st.session_state.manual_assignments)
        temp_schedule.update(major_assignments)

        # 2. Κατανομή μικρών αργιών
        regular_dates_sorted = sorted(regular_hols.keys())
        regular_assignments, major_conflicts_2 = assign_regular_holidays(
            regular_dates_sorted,
            temp_schedule,
            manual_assignments=st.session_state.manual_assignments,
            max_per_week=2,
            min_gap_days=3,
            historical_regular_counts=st.session_state.historical_regular_counts
        )

        holiday_assignments = {**major_assignments, **regular_assignments}
        holiday_conflicts = major_conflicts_1.union(major_conflicts_2)

        st.session_state.holiday_names = holiday_names
        st.session_state.holiday_assignments = holiday_assignments
        st.session_state.holiday_conflicts = holiday_conflicts

        st.session_state.schedule = generate_schedule(
            st.session_state.initial_week,
            start_date,
            end_date,
            holiday_assignments=holiday_assignments,
            manual_assignments=st.session_state.manual_assignments
        )
        st.session_state.start_date = start_date
        st.session_state.end_date = end_date
        
        st.session_state.balance = compute_balance(
            st.session_state.schedule,
            holiday_dates=set(holiday_assignments.keys())
        )

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule)
