import streamlit as st
import datetime
import calendar
import pandas as pd
from fpdf import FPDF
from collections import deque

# ----------------------------
# CONSTANTS & SETUP
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
ROTATION_BASE_YEAR = 2026  # Σταθερό έτος βάσης για τη 7ετία

# Fixed-date Cyprus public holidays: (month, day, name)
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
        # 5 Κύριες Αργίες Χριστούγεννων & Πρωτοχρονιάς (συμπεριλαμβάνεται η 24/12)
        c_dates = [
            (datetime.date(year, 12, 24), "Παραμονή Χριστουγέννων"),
            (datetime.date(year, 12, 25), "Χριστούγεννα"),
            (datetime.date(year, 12, 26), "Δεύτερη μέρα Χριστουγέννων"),
            (datetime.date(year, 12, 31), "Παραμονή Πρωτοχρονιάς"),
            (datetime.date(year, 1, 1), "Πρωτοχρονιά"),
        ]
        for d, name in c_dates:
            if start_date <= d <= end_date:
                target_dates[d] = name
        
        # 4 Κύριες Αργίες Πάσχα
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

# ----------------------------
# ROTATION & ASSIGNMENT LOGIC
# ----------------------------
def assign_major_holidays_by_rotation(start_year, end_year, manual_assignments=None):
    """
    Αναθέτει τις 9 κύριες αργίες βάσει των 7 ετήσιων πακέτων με 7ετή Rota Rotation.
    """
    manual_assignments = manual_assignments or {}
    assignments = {}
    doctors_list = list(DOCTORS)

    for year in range(start_year, end_year + 1):
        try:
            easter = orthodox_easter(year)
            easter_fri = easter - datetime.timedelta(days=2)
            easter_sat = easter - datetime.timedelta(days=1)
            easter_sun = easter
            easter_mon = easter + datetime.timedelta(days=1)
        except Exception:
            continue

        c_24 = datetime.date(year, 12, 24)
        c_25 = datetime.date(year, 12, 25)
        c_26 = datetime.date(year, 12, 26)
        c_31 = datetime.date(year, 12, 31)
        c_01 = datetime.date(year + 1, 1, 1)

        holiday_packages = [
            [c_24, easter_sat], # Πακέτο 0: 24/12 + Μ. Σάββατο
            [c_25],             # Πακέτο 1: 25/12
            [c_26, easter_fri], # Πακέτο 2: 26/12 + Μ. Παρασκευή
            [c_31],             # Πακέτο 3: 31/12
            [c_01],             # Πακέτο 4: 01/01
            [easter_sun],       # Πακέτο 5: Κυριακή του Πάσχα
            [easter_mon]        # Πακέτο 6: Δευτέρα του Πάσχα
        ]

        year_offset = (year - ROTATION_BASE_YEAR) % 7

        for pkg_idx, pkg_dates in enumerate(holiday_packages):
            doc_idx = (pkg_idx + year_offset) % 7
            assigned_doc = doctors_list[doc_idx]

            for d in pkg_dates:
                if d in manual_assignments:
                    assignments[d] = manual_assignments[d]
                else:
                    assignments[d] = assigned_doc

    return assignments

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

def assign_regular_holidays(regular_dates_sorted, base_schedule, manual_assignments=None, max_per_week=2, min_gap_days=3, custom_queue=None):
    """
    Αναθέτει τις μικρές αργίες χρησιμοποιώντας την κυκλική ουρά.
    """
    manual_assignments = manual_assignments or {}
    working = dict(base_schedule)
    working.update(manual_assignments)

    queue = deque(custom_queue) if custom_queue is not None else deque(DOCTORS)
    assignments = {}
    conflicts = set()
    max_gap = min_gap_days - 1

    for d in regular_dates_sorted:
        if d in manual_assignments:
            continue

        skipped = []
        chosen = None
        for _ in range(len(queue)):
            candidate = queue.popleft()
            nearby_conflict = _has_nearby_shift(candidate, d, working, max_gap=max_gap)
            week_count = _shifts_in_week(candidate, d, working, exclude_date=d)
            weekly_conflict = (week_count + 1) > max_per_week
            
            if not nearby_conflict and not weekly_conflict:
                chosen = candidate
                queue.append(candidate)
                break
            skipped.append(candidate)

        if chosen is None:
            chosen = skipped.pop(0) if skipped else DOCTORS[0]
            queue.append(chosen)
            conflicts.add(d)

        for s in reversed(skipped):
            queue.appendleft(s)

        assignments[d] = chosen
        working[d] = chosen

    return assignments, conflicts, queue

def generate_base_rota(initial_week, start_date, end_date):
    schedule = {}
    total_days = (end_date - start_date).days + 1
    
    for day_offset in range(total_days):
        current_date = start_date + datetime.timedelta(days=day_offset)
        week_num = day_offset // 7
        day_of_week = day_offset % 7
        
        doc_index = (day_of_week + (week_num * 2)) % len(initial_week)
        schedule[current_date] = initial_week[doc_index]
        
    return schedule

def generate_schedule_with_swaps(initial_week, start_date, end_date, holiday_assignments, manual_assignments):
    """
    Δημιουργεί το τελικό πρόγραμμα με Swap:
    Ο Α (που είχε βάρδια) παίρνει την επόμενη κανονική βάρδια του Β (που πήρε την αργία).
    """
    schedule = generate_base_rota(initial_week, start_date, end_date)
    manual_assignments = manual_assignments or {}
    holiday_assignments = holiday_assignments or {}

    all_dates = sorted(schedule.keys())

    for h_date, b_doctor in holiday_assignments.items():
        if h_date not in schedule:
            continue

        a_doctor = schedule[h_date]

        if a_doctor == b_doctor:
            continue

        schedule[h_date] = b_doctor

        for future_date in all_dates:
            if future_date > h_date:
                if schedule[future_date] == b_doctor and future_date not in holiday_assignments and future_date not in manual_assignments:
                    schedule[future_date] = a_doctor
                    break

    for m_date, m_doc in manual_assignments.items():
        if m_date in schedule:
            schedule[m_date] = m_doc

    return schedule

# ----------------------------
# BALANCE & REPORTING
# ----------------------------
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

# ----------------------------
# DISPLAY & PDF HELPERS
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
    pdf.cell(0, 10, "Κατάσταση Εφημεριών Χριστουγέννων & Πάσχα", ln=True, align="C")
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
if "regular_holiday_queue" not in st.session_state:
    st.session_state.regular_holiday_queue = deque(DOCTORS)

for key in ["initial_week", "start_date", "end_date", "schedule", "balance"]:
    if key not in st.session_state:
        st.session_state[key] = None

left_col, right_col = st.columns([0.35, 0.65])

# ----------------------------
# LEFT: Balance & Manual Overrides
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
                    f"⚠️ Σε {len(conflicts)} αργία(ες) δεν βρέθηκε γιατρός χωρίς σύγκρουση "
                    f"(κανόνας 3 ημερών / 2 εφημεριών τη βδομάδα) — ελέγξτε τις παρακάτω."
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
            with st.expander("🎄🐣 Ανάλυση Μεγάλων Εορτών (Χριστούγεννα & Πάσχα)"):
                major_df = compute_major_holidays_summary(st.session_state.schedule, major_hols)
                st.dataframe(major_df, use_container_width=True)
                
                if st.button("📄 Εξαγωγή αναφοράς Χριστουγέννων/Πάσχα σε PDF"):
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
# RIGHT: Rota Generation
# ----------------------------
with right_col:
    selected_date = st.date_input("Ημερομηνία έναρξης:", datetime.date.today())
    week_dates = [selected_date - datetime.timedelta(days=selected_date.weekday()) + datetime.timedelta(days=i) for i in range(7)]

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
        
        # 1. Μεγάλες Εορτές: Rota Rotation 7-ετίας με τα 7 Πακέτα
        major_assignments = assign_major_holidays_by_rotation(
            start_date.year,
            end_date.year,
            manual_assignments=st.session_state.manual_assignments
        )

        # 2. Μικρές Αργίες: Κυκλική Ουρά
        regular_dates_sorted = sorted(regular_hols.keys())
        regular_assignments, regular_conflicts, updated_regular_q = assign_regular_holidays(
            regular_dates_sorted,
            base_rota,
            manual_assignments=st.session_state.manual_assignments,
            custom_queue=st.session_state.regular_holiday_queue
        )
        st.session_state.regular_holiday_queue = updated_regular_q

        holiday_assignments = {**major_assignments, **regular_assignments}

        st.session_state.holiday_names = holiday_names
        st.session_state.holiday_assignments = holiday_assignments
        st.session_state.holiday_conflicts = regular_conflicts

        # 3. Παραγωγή με Swap
        st.session_state.schedule = generate_schedule_with_swaps(
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
