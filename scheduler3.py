import streamlit as st
import datetime
import calendar
import random
import pandas as pd
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
    "Χριστίνα": (245, 222, 179)
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

def _has_nearby_shift(doctor, date, schedule, max_gap=3):
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

def _saturdays_in_month(doctor, date, schedule, exclude_date=None):
    year, month = date.year, date.month
    count = 0
    for d, doc in schedule.items():
        if d == exclude_date:
            continue
        if doc == doctor and d.year == year and d.month == month and d.weekday() == 5:
            count += 1
    return count

def _sundays_in_month(doctor, date, schedule, exclude_date=None):
    year, month = date.year, date.month
    count = 0
    for d, doc in schedule.items():
        if d == exclude_date:
            continue
        if doc == doctor and d.year == year and d.month == month and d.weekday() == 6:
            count += 1
    return count

def _worked_same_weekday_in_month(doctor, date, schedule, exclude_date=None):
    year, month = date.year, date.month
    weekday = date.weekday()
    for d, doc in schedule.items():
        if d == exclude_date:
            continue
        if doc == doctor and d.year == year and d.month == month and d.weekday() == weekday:
            return True
    return False

def is_valid_assignment(doctor, date, schedule, holiday_names, exclude_date=None):
    # 1. Κανόνας: Απαγόρευση ίδιας μέρας (π.χ. Τετάρτη) ξανά μέσα στον ίδιο μήνα
    if _worked_same_weekday_in_month(doctor, date, schedule, exclude_date=exclude_date):
        return False

    # 2. Κανόνας: Ελάχιστο κενό 3 ημερών
    if _has_nearby_shift(doctor, date, schedule, max_gap=3):
        return False
        
    # 3. Κανόνας: Αυστηρά ΜΕΓΙΣΤΟ 1 εφημερίδα την εβδομάδα
    if _shifts_in_week(doctor, date, schedule, exclude_date=exclude_date) >= 1:
        return False
            
    # 4. Απαραβάτος Κανόνας Σαββατοκύριακων: Αυστηρά έως 1 Σάββατο και 1 Κυριακή ανά μήνα (ΧΩΡΙΣ ΧΑΛΑΡΩΣΗ)
    if date.weekday() == 5:  # Σάββατο
        if _saturdays_in_month(doctor, date, schedule, exclude_date=exclude_date) >= 1:
            return False
    elif date.weekday() == 6:  # Κυριακή
        if _sundays_in_month(doctor, date, schedule, exclude_date=exclude_date) >= 1:
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
# SEQUENTIAL FAIR SCHEDULING LOGIC
# ----------------------------
def generate_full_schedule(start_date, end_date, manual_assignments=None):
    manual_assignments = manual_assignments or {}
    schedule = {}
    holiday_names = get_holidays_in_range(start_date, end_date)
    
    total_days = (end_date - start_date).days + 1
    
    for day_offset in range(total_days):
        current_date = start_date + datetime.timedelta(days=day_offset)
        
        if current_date in manual_assignments:
            schedule[current_date] = manual_assignments[current_date]
            continue
            
        is_holiday = current_date in holiday_names
        
        # Απολύτως αυστηρός έλεγχος με βάση τους κανόνες
        valid_docs = [doc for doc in DOCTORS if is_valid_assignment(doc, current_date, schedule, holiday_names)]
        
        # Αν για κάποιο λόγο δεν βρεθεί κανείς (ακραία περίπτωση), επιτρέπουμε μόνο χαλάρωση του κενού ημερών, αλλά ΠΟΤΕ των Σαββατοκύριακων/ίδιας μέρας
        if not valid_docs:
            valid_docs = [doc for doc in DOCTORS if not _worked_same_weekday_in_month(doc, current_date, schedule)]
            if date.weekday() == 6:
                valid_docs = [doc for doc in valid_docs if _sundays_in_month(doc, current_date, schedule) == 0]
            elif date.weekday() == 5:
                valid_docs = [doc for doc in valid_docs if _saturdays_in_month(doc, current_date, schedule) == 0]
            
        if not valid_docs:
            valid_docs = DOCTORS
            
        # Τυχαία επιλογή μεταξύ ισοβαθμιών
        valid_docs_shuffled = list(valid_docs)
        random.shuffle(valid_docs_shuffled)
        
        best_doc = min(valid_docs_shuffled, key=lambda doc: (
            _count_doctor_holidays(doc, schedule, holiday_names) if is_holiday else 0,
            _total_shifts_in_month_flex(doc, current_date, schedule),
            _shifts_in_week(doc, current_date, schedule)
        ))
        
        schedule[current_date] = best_doc

    return schedule, holiday_names

def _total_shifts_in_month_flex(doctor, date, schedule, exclude_date=None):
    year, month = date.year, date.month
    total = 0
    for d, doc in schedule.items():
        if d == exclude_date:
            continue
        if doc == doctor and d.year == year and d.month == month:
            total += 1
    return total

def _count_doctor_holidays(doctor, schedule, holiday_names):
    return sum(1 for d, doc_name in schedule.items() if doc_name == doctor and d in holiday_names)

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

def display_calendar(schedule, holiday_names):
    manual_assignments = st.session_state.get("manual_assignments", {})
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
                        holiday_tag = f"<br><span style='font-size:10px'>🎉 {holiday_names[day]}</span>" if is_holiday else ""
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
# STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="📅 Πρόγραμμα Εφημεριών", layout="wide")
st.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων")
st.markdown("<span style='font-size:14px; color:gray;'>© Γιώργος Μενοίκου, PhD</span>", unsafe_allow_html=True)

if "manual_assignments" not in st.session_state:
    st.session_state.manual_assignments = {}
if "schedule" not in st.session_state:
    st.session_state.schedule = None
if "holiday_names" not in st.session_state:
    st.session_state.holiday_names = {}
if "balance" not in st.session_state:
    st.session_state.balance = None
if "start_date" not in st.session_state:
    st.session_state.start_date = datetime.date.today()

left_col, right_col = st.columns([0.35, 0.65])

with left_col:
    st.subheader("📊 Κατάσταση Εφημεριών Εύρους")
    if st.session_state.start_date and st.session_state.schedule:
        manual_date = st.date_input("Επιλέξετε ημερομηνία για αλλαγή", min_value=min(st.session_state.schedule.keys()), max_value=max(st.session_state.schedule.keys()))
        manual_doctor = st.selectbox("Επιλογή Ακτινολόγου", DOCTORS)
        if st.button("✅ Επικύρωση"):
            st.session_state.manual_assignments[manual_date] = manual_doctor
            st.session_state.schedule[manual_date] = manual_doctor
            st.session_state.balance = compute_balance(st.session_state.schedule, holiday_dates=set(st.session_state.holiday_names.keys()))
            st.success(f"Ο/Η {manual_doctor} ανατέθηκε στις {manual_date.strftime('%d/%m/%Y')}")
            st.rerun()

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        st.dataframe(st.session_state.balance, use_container_width=True, height=260)

        major_hols = get_major_holidays_in_range(st.session_state.start_date, max(st.session_state.schedule.keys()) if st.session_state.schedule else st.session_state.start_date)
        if major_hols:
            with st.expander("🎄🐣 Ανάλυση Μεγάλων Εορτών"):
                major_df = compute_major_holidays_summary(st.session_state.schedule, major_hols)
                st.dataframe(major_df, use_container_width=True)

        if st.session_state.holiday_names:
            regular_hols_dict = {d: n for d, n in st.session_state.holiday_names.items() if d not in major_hols}
            if regular_hols_dict:
                with st.expander("🎈 Ανάλυση Μικρών Αργιών"):
                    regular_df = compute_regular_holidays_summary(st.session_state.schedule, regular_hols_dict)
                    st.dataframe(regular_df, use_container_width=True)

        if st.button("📄 Εξαγωγή κατάστασης σε PDF"):
            pdf_file = create_balance_pdf(st.session_state.balance, st.session_state.start_date, max(st.session_state.schedule.keys()))
            with open(pdf_file, "rb") as f:
                st.download_button("⬇️ Κατέβασε κατάσταση σε PDF", f, file_name=pdf_file)

with right_col:
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start date", datetime.date.today())
    with c2:
        default_end = start_date + datetime.timedelta(days=30)
        end_date = st.date_input("End date", default_end)

    if st.button("🗓️ Δημιουργία Προγράμματος"):
        st.session_state.start_date = start_date
        sch, hols = generate_full_schedule(
            start_date, end_date, 
            manual_assignments=st.session_state.manual_assignments
        )
        st.session_state.schedule = sch
        st.session_state.holiday_names = hols
        st.session_state.balance = compute_balance(sch, holiday_dates=set(hols.keys()))
        st.rerun()

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule, st.session_state.holiday_names)
