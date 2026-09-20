import streamlit as st
import datetime
import calendar
import pandas as pd
from fpdf import FPDF

# ----------------------------
# CONSTANTS & SETUP
# ----------------------------
DOCTORS = ["Χριστίνα", "Αθηνά", "Μαρία", "Έλια", "Αλέξανδρος", "Εύα", "Έλενα"]

# Διακριτά και μοναδικά χρώματα για κάθε γιατρό
DOCTOR_COLORS = {
    "Έλενα": (255, 182, 193),       # Ανοιχτό Ροζ (Light Pink)
    "Εύα": (152, 251, 152),         # Ανοιχτό Πράσινο (Pale Green)
    "Μαρία": (176, 196, 222),       # Ανοιχτό Μπλε (Light Steel Blue)
    "Αθηνά": (255, 250, 205),       # Κίτρινο Λεμονιού (Lemon Chiffon)
    "Αλέξανδρος": (221, 160, 221),   # Μωβ/Plum
    "Έλια": (175, 238, 238),        # Τουρκουάζ (Pale Turquoise)
    "Χριστίνα": (245, 222, 179)     # Μπεζ/Wheat
}

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
ROTATION_BASE_YEAR = 2026

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
# HELPER FUNCTIONS (VALIDATION)
# ----------------------------
def _week_monday(date):
    return date - datetime.timedelta(days=date.weekday())

def _has_nearby_shift(doctor, date, schedule, max_gap=2):
    """Ελέγχει αν υπάρχει εφημερία σε απόσταση +-2 ημερών."""
    for d, doc in schedule.items():
        if doc == doctor and d != date and abs((d - date).days) <= max_gap:
            return True
    return False

def _shifts_in_week(doctor, date, schedule, exclude_date=None):
    """Υπολογίζει πόσες εφημερίες έχει ο γιατρός στη συγκεκριμένη εβδομάδα."""
    wk = _week_monday(date)
    return sum(
        1 for d, doc in schedule.items()
        if doc == doctor and d != exclude_date and _week_monday(d) == wk
    )

def _count_doctor_weekends_in_month(doctor, date, schedule, exclude_date=None):
    """Μετράει πόσα Σάββατα και πόσες Κυριακές έχει ο γιατρός στον ίδιο μήνα."""
    year, month = date.year, date.month
    saturdays = 0
    sundays = 0
    for d, doc in schedule.items():
        if d == exclude_date:
            continue
        if doc == doctor and d.year == year and d.month == month:
            if d.weekday() == 5:  # Σάββατο
                saturdays += 1
            elif d.weekday() == 6:  # Κυριακή
                sundays += 1
    return saturdays, sundays

def is_valid_assignment(doctor, date, schedule, exclude_date=None):
    """
    Επαληθεύει τους κανόνες: 
    1. Απόσταση +-2 μέρες
    2. Max 2 εφημερίες/εβδομάδα
    3. Max 1 Σάββατο ανά μήνα
    4. Max 1 Κυριακή ανά μήνα
    """
    if _has_nearby_shift(doctor, date, schedule, max_gap=2):
        return False
    if _shifts_in_week(doctor, date, schedule, exclude_date=exclude_date) >= 2:
        return False
        
    saturdays, sundays = _count_doctor_weekends_in_month(doctor, date, schedule, exclude_date=exclude_date)
    wd = date.weekday()
    if wd == 5 and saturdays >= 1:
        return False
    if wd == 6 and sundays >= 1:
        return False
        
    return True

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
            (datetime.date(year, 1, 1), "Πρωτοχρονιά"),
            (datetime.date(year, 12, 24), "Παραμονή Χριστουγέννων"),
            (datetime.date(year, 12, 25), "Χριστούγεννα"),
            (datetime.date(year, 12, 26), "Δεύτερη μέρα Χριστουγέννων"),
            (datetime.date(year, 12, 31), "Παραμονή Πρωτοχρονιάς"),
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

# ----------------------------
# ROTATION & ASSIGNMENT LOGIC
# ----------------------------
def assign_major_holidays_by_rotation(start_year, end_year, base_rota, manual_assignments=None):
    manual_assignments = manual_assignments or {}
    working = dict(base_rota)
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

        c_01 = datetime.date(year, 1, 1)
        c_24 = datetime.date(year, 12, 24)
        c_25 = datetime.date(year, 12, 25)
        c_26 = datetime.date(year, 12, 26)
        c_31 = datetime.date(year, 12, 31)

        holiday_packages = [
            [c_24, easter_sat],
            [c_25],            
            [c_26, easter_fri],
            [c_31],            
            [c_01],            
            [easter_sun],      
            [easter_mon]       
        ]

        year_offset = (year - ROTATION_BASE_YEAR) % 7

        for pkg_idx, pkg_dates in enumerate(holiday_packages):
            valid_pkg_dates = [d for d in pkg_dates if start_year <= d.year <= end_year and d in working]
            if not valid_pkg_dates:
                continue

            # Έλεγχος για manual assignments σε αυτές τις ημερομηνίες
            pkg_assigned_manually = False
            for d in valid_pkg_dates:
                if d in manual_assignments:
                    doc = manual_assignments[d]
                    assignments[d] = doc
                    working[d] = doc
                    pkg_assigned_manually = True
            
            if pkg_assigned_manually:
                continue

            base_doc_idx = (pkg_idx + year_offset) % 7
            chosen_doc = None
            
            # 1. Δοκιμή γιατρών σύμφωνα με τη σειρά εναλλαγής τηρώντας αυστηρά τους κανόνες
            for offset in range(len(doctors_list)):
                doc_idx = (base_doc_idx + offset) % len(doctors_list)
                doc = doctors_list[doc_idx]
                
                can_take_all = True
                temp_working = dict(working)
                for d in valid_pkg_dates:
                    if not is_valid_assignment(doc, d, temp_working, exclude_date=d):
                        can_take_all = False
                        break
                    temp_working[d] = doc
                
                if can_take_all:
                    chosen_doc = doc
                    break
            
            # 2. ΑΥΣΤΗΡΟ FALLBACK: Αν κανείς δεν πληροί 100% τους κανόνες, 
            # αποκλείουμε απόλυτα όσους έχουν ήδη Σάββατο/Κυριακή στον μήνα αυτόν.
            if not chosen_doc:
                has_sat_pkg = any(d.weekday() == 5 for d in valid_pkg_dates)
                has_sun_pkg = any(d.weekday() == 6 for d in valid_pkg_dates)
                
                best_fallback = None
                for offset in range(len(doctors_list)):
                    doc_idx = (base_doc_idx + offset) % len(doctors_list)
                    doc = doctors_list[doc_idx]
                    
                    sats, suns = _count_doctor_weekends_in_month(doc, valid_pkg_dates[0], working)
                    if has_sat_pkg and sats >= 1:
                        continue
                    if has_sun_pkg and suns >= 1:
                        continue
                    best_fallback = doc
                    break
                
                # Αν ακόμη κι έτσι δεν βρεθεί, παίρνουμε τουλάχιστον τον βασικό της σειράς αλλά αποφεύγουμε τις διπλές παραβιάσεις αν γίνεται
                chosen_doc = best_fallback if best_fallback else doctors_list[base_doc_idx]

            for d in valid_pkg_dates:
                assignments[d] = chosen_doc
                working[d] = chosen_doc

    return assignments

def find_best_doctor_for_date(target_date, schedule, holiday_counts, exclude_date=None):
    valid_doctors = [
        doc for doc in DOCTORS 
        if is_valid_assignment(doc, target_date, schedule, exclude_date=exclude_date)
    ]
    
    if not valid_doctors:
        return DOCTORS[0]
        
    min_hols = min(holiday_counts[doc] for doc in valid_doctors)
    candidates = [doc for doc in valid_doctors if holiday_counts[doc] == min_hols]
    
    best_doc = candidates[0]
    best_score = -1
    
    for doc in candidates:
        prev_dates = [
            d for d, assigned in schedule.items() 
            if assigned == doc and d < target_date and d != exclude_date
        ]
        prev_dist = (target_date - max(prev_dates)).days if prev_dates else 9999
        
        next_dates = [
            d for d, assigned in schedule.items() 
            if assigned == doc and d > target_date and d != exclude_date
        ]
        next_dist = (min(next_dates) - target_date).days if next_dates else 9999
        
        score = min(prev_dist, next_dist)
        
        if score > best_score:
            best_score = score
            best_doc = doc
            
    return best_doc

def assign_regular_holidays(regular_dates_sorted, current_schedule, manual_assignments=None):
    manual_assignments = manual_assignments or {}
    working = dict(current_schedule)

    assignments = {}
    conflicts = set()
    holiday_counts = {doc: 0 for doc in DOCTORS}

    for d, assigned in manual_assignments.items():
        if assigned in holiday_counts:
            holiday_counts[assigned] += 1

    for d in regular_dates_sorted:
        if d in manual_assignments:
            assigned = manual_assignments[d]
            working[d] = assigned
            continue

        chosen = find_best_doctor_for_date(d, working, holiday_counts, exclude_date=d)
        
        if not is_valid_assignment(chosen, d, working, exclude_date=d):
            conflicts.add(d)

        assignments[d] = chosen
        working[d] = chosen
        holiday_counts[chosen] += 1

    return assignments, conflicts

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
            
            nearby_conflict = _has_nearby_shift(manual_doctor, manual_date, current_schedule, max_gap=2)
            weekly_conflict = (_shifts_in_week(manual_doctor, manual_date, current_schedule, exclude_date=manual_date) + 1) > 2

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
            st.success(f"Ο/Η {manual_doctor} ανατέθηκε στις {manual_date.strftime('%d/%m/%Y')}{holiday_note}")

            if nearby_conflict:
                st.warning(
                    f"⚠️ Προσοχή: Ο/Η {manual_doctor} έχει άλλη εφημερία εντός +-2 ημερών από τις "
                    f"{manual_date.strftime('%d/%m/%Y')}."
                )
            if weekly_conflict:
                st.warning(
                    f"⚠️ Προσοχή: Ο/Η {manual_doctor} υπερβαίνει τις 2 εφημερίες την ίδια εβδομάδα."
                )
            
            st.rerun()

        if st.session_state.holiday_names:
            conflicts = st.session_state.get("holiday_conflicts", set())
            if conflicts:
                st.warning(
                    f"⚠️ Σε {len(conflicts)} αργία(ες) δεν βρέθηκε διαθέσιμος γιατρός χωρίς σύγκρουση "
                    f"(κανόνας +-2 ημερών / max 2 εφημεριών / max 1 ΣΚ μήνα) — παρακαλώ ελέγξτε τις."
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
        st.rerun()

    if st.session_state.initial_week is None:
        st.stop()

    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start date", st.session_state.start_date)
    with c2:
        end_date = st.date_input("End date", st.session_state.start_date + datetime.timedelta(days=30))

    if st.button("🗓️ Δημιουργία Προγράμματος"):
        holiday_names = get_holidays_in_range(start_date, end_date)
        
        # 1. Δημιουργία βασικής ρότας πρώτα
        base_rota = generate_base_rota(st.session_state.initial_week, start_date, end_date)
        
        # 2. Υπολογισμός μεγάλων αργιών με αυστηρό έλεγχο ορίων S/K
        major_assignments = assign_major_holidays_by_rotation(
            start_date.year,
            end_date.year,
            base_rota,
            manual_assignments=st.session_state.manual_assignments
        )
        
        working_rota = dict(base_rota)
        for d, doc in major_assignments.items():
            if d in working_rota:
                working_rota[d] = doc

        # 3. Υπολογισμός μικρών αργιών
        regular_hols = {d: n for d, n in holiday_names.items() if d not in major_assignments}
        regular_dates_sorted = sorted(regular_hols.keys())
        
        regular_assignments, regular_conflicts = assign_regular_holidays(
            regular_dates_sorted,
            working_rota,
            manual_assignments=st.session_state.manual_assignments
        )

        holiday_assignments = {**major_assignments, **regular_assignments}

        st.session_state.holiday_names = holiday_names
        st.session_state.holiday_assignments = holiday_assignments
        st.session_state.holiday_conflicts = regular_conflicts

        # 4. Τελική σύνθεση προγράμματος
        final_schedule = dict(base_rota)
        for d, doc in holiday_assignments.items():
            if d in final_schedule:
                final_schedule[d] = doc
                
        if st.session_state.manual_assignments:
            for d, doc in st.session_state.manual_assignments.items():
                if d in final_schedule:
                    final_schedule[d] = doc

        st.session_state.schedule = final_schedule
        st.session_state.start_date = start_date
        st.session_state.end_date = end_date
        
        st.session_state.balance = compute_balance(
            st.session_state.schedule,
            holiday_dates=set(holiday_assignments.keys())
        )

        st.rerun()

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule)
