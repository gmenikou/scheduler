import streamlit as st
import datetime
import calendar
import pandas as pd
from collections import defaultdict
from fpdf import FPDF
import os

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


def _has_nearby_shift(doctor, date, schedule, min_gap=2):
    for d, doc in schedule.items():
        if doc == doctor and d != date and abs((d - date).days) <= min_gap:
            return True
    return False


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


def get_day_category(date, holiday_dates):
    if date in holiday_dates:
        return "Αργίες"
    wd = date.weekday()
    if wd == 5:
        return "Sat"
    elif wd == 6:
        return "Sun"
    elif wd == 4:
        return "Fri"
    else:
        return "Weekdays"


# ----------------------------
# BALANCED SCHEDULING LOGIC
# ----------------------------
def generate_full_schedule(start_date, end_date, initial_week=None, manual_assignments=None):
    manual_assignments = manual_assignments or {}
    schedule = {}
    warnings = []

    holiday_names = get_holidays_in_range(start_date, end_date)
    holiday_dates = set(holiday_names.keys())

    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            schedule[d] = doc

    total_Days = (end_date - start_date).days + 1
    all_days = [start_date + datetime.timedelta(days=i) for i in range(total_Days)]
    
    unassigned_days = [d for d in all_days if d not in schedule]
    category_counters = {cat: {doc: 0 for doc in DOCTORS} for cat in ["Weekdays", "Fri", "Sat", "Sun", "Αργίες"]}

    for d, doc in schedule.items():
        cat = get_day_category(d, holiday_dates)
        if doc in category_counters[cat]:
            category_counters[cat][doc] += 1

    unassigned_days.sort()

    for d in unassigned_days:
        cat = get_day_category(d, holiday_dates)
        best_doc = None
        sorted_doctors = sorted(DOCTORS, key=lambda doc: (category_counters[cat][doc], doc))

        assigned = False
        for min_gap in [2, 1, 0]:
            for doc in sorted_doctors:
                if not _has_nearby_shift(doc, d, schedule, min_gap=min_gap):
                    best_doc = doc
                    assigned = True
                    break
            if assigned:
                break

        if best_doc is None:
            best_doc = sorted_doctors[0]
            warnings.append(f"{d.strftime('%d/%m/%Y')}: Ελάχιστο κενό παραβιάστηκε για δίκαιη κατανομή.")

        schedule[d] = best_doc
        category_counters[cat][best_doc] += 1

    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            schedule[d] = doc

    return schedule, holiday_names, warnings


def compute_balance(schedule, start_date, end_date, holiday_names):
    holiday_dates = set(holiday_names.keys())
    counts = {doc: {"Weekdays": 0, "Fri": 0, "Sat": 0, "Sun": 0, "Αργίες": 0, "Total": 0} for doc in DOCTORS}
    
    for date, doc in schedule.items():
        if doc in counts:
            cat = get_day_category(date, holiday_dates)
            counts[doc][cat] += 1
            counts[doc]["Total"] += 1

    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    return df[["Doctor", "Weekdays", "Fri", "Sat", "Sun", "Αργίες", "Total"]]


def create_balance_pdf(df, start_date, end_date):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    
    # Προσθήκη unicode font (DejaVuSans) για υποστήριξη ελληνικών χαρακτήρων στο PDF
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", "B", 16)
    else:
        pdf.set_font("Arial", "B", 16)

    pdf.cell(0, 10, "Ισοζύγιο Εφημεριών Ακτινολόγων", align="C", new_x="LMARGIN", new_y="NEXT")
    
    if os.path.exists(font_path):
        pdf.set_font("DejaVu", "", 10)
    else:
        pdf.set_font("Arial", "", 10)
        
    for index, row in df.iterrows():
        txt = f"{row['Doctor']} | Weekdays: {row['Weekdays']} | Fri: {row['Fri']} | Sat: {row['Sat']} | Sun: {row['Sun']} | Αργίες: {row['Αργίες']} | Total: {row['Total']}"
        pdf.cell(0, 8, txt, new_x="LMARGIN", new_y="NEXT")
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
st.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων (Ισόποση Κατανομή)")
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
    st.subheader("📊 Παραμετροποίηση Εύρους")
    start_date = st.date_input("Ημερομηνία Έναρξης", value=datetime.date(2026, 1, 1))
    end_date = st.date_input("Ημερομηνία Λήξης", value=datetime.date(2026, 12, 31))
    
    if st.button("🚀 Δημιουργία Ισόρροπου Προγράμματος"):
        st.session_state.start_date = start_date
        holiday_names = get_holidays_in_range(start_date, end_date)
        st.session_state.holiday_names = holiday_names
        
        schedule, holiday_names, warnings = generate_full_schedule(
            start_date, end_date, st.session_state.initial_week, st.session_state.manual_assignments
        )
        st.session_state.schedule = schedule
        st.session_state.warnings = warnings
        st.session_state.balance = compute_balance(schedule, start_date, end_date, holiday_names)
        st.success("Το ισόρροπο πρόγραμμα δημιουργήθηκε επιτυχώς!")

    st.markdown("---")
    st.subheader("⚙️ Χειροκίνητες Παρεμβάσεις")
    with st.expander("Προσθήκη / Τροποποίηση Εφημερίας"):
        m_date = st.date_input("Ημερομηνία", value=datetime.date(2026, 1, 1))
        m_doc = st.selectbox("Γιατρός", DOCTORS)
        if st.button("💾 Αποθήκευση Ανάθεσης"):
            st.session_state.manual_assignments[m_date] = m_doc
            st.success(f"Ανατέθηκε η {m_date.strftime('%d/%m/%Y')} στον/ην {m_doc}")
            if st.session_state.schedule:
                st.session_state.schedule[m_date] = m_doc
                st.session_state.balance = compute_balance(st.session_state.schedule, st.session_state.start_date, end_date, st.session_state.holiday_names)
        
        if st.button("🗑️ Εκκαθάριση Χειροκίνητων"):
            st.session_state.manual_assignments = {}
            st.success("Καθαρίστηκαν οι χειροκίνητες αναθέσεις!")

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        st.markdown("---")
        st.subheader("📈 Ισοζύγιο Εφημεριών")
        st.dataframe(st.session_state.balance, use_container_width=True, height=260)
        
        pdf_bytes = create_balance_pdf(st.session_state.balance, start_date, end_date)
        st.download_button(
            label="📥 Λήψη Ισοζυγίου σε PDF",
            data=pdf_bytes,
            file_name="doctor_balance.pdf",
            mime="application/pdf"
        )

with right_col:
    st.subheader("🗓️ Ημερολόγιο Εφημεριών")
    if st.session_state.warnings:
        with st.expander("⚠️ Προειδοποιήσεις Αυτόματης Δημιουργίας"):
            for w in st.session_state.warnings:
                st.warning(w)

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule, st.session_state.holiday_names)
    else:
        st.info("Πατήστε «Δημιουργία Ισόρροπου Προγράμματος» για να εμφανιστεί το ημερολόγιο.")
