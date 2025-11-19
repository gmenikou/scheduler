import streamlit as st
import datetime
import calendar
import pandas as pd
from fpdf import FPDF

# ---------------------------------------------
# 1. CONSTANT DOCTOR LIST & COLORS
# ---------------------------------------------
DOCTORS = ["Elena", "Eva", "Maria", "Athina", "Alexandros", "Elia", "Christina"]
DOCTOR_COLORS = {
    "Elena": (255, 200, 200),
    "Eva": (200, 255, 200),
    "Maria": (200, 200, 255),
    "Athina": (255, 255, 200),
    "Alexandros": (255, 200, 255),
    "Elia": (200, 255, 255),
    "Christina": (220, 220, 220)
}

# ---------------------------------------------
# 2. HELPERS
# ---------------------------------------------
def get_week_dates(any_date):
    monday = any_date - datetime.timedelta(days=any_date.weekday())
    return [monday + datetime.timedelta(days=i) for i in range(7)]

def get_text_color(rgb):
    r, g, b = rgb
    brightness = (r*299 + g*587 + b*114)/1000
    return (0,0,0) if brightness > 125 else (255,255,255)

# ---------------------------------------------
# 3. SCHEDULE GENERATION WITH -2 DAYS ROTATION PER DOCTOR
# ---------------------------------------------
def generate_schedule(initial_week, start_date, months=1):
    """
    Generate schedule with -2 day/week rotation per doctor.
    - initial_week: list of 7 doctors for the first week (Mon=0 ... Sun=6)
    - start_date: Monday of the initial week
    - months: number of months to generate
    """
    schedule = {}

    # Map each doctor to their weekday (0=Mon ... 6=Sun) for initial week
    doctor_to_weekday = {doc: i for i, doc in enumerate(initial_week)}

    # Save initial week exactly
    for i, doc in enumerate(initial_week):
        schedule[start_date + datetime.timedelta(days=i)] = doc

    # Start rotation from the week after initial
    current_week_start = start_date + datetime.timedelta(days=7)

    # Determine last day of the requested months
    last_month = (start_date.month + months - 1 - 1) % 12 + 1
    last_year = start_date.year + (start_date.month + months - 1 - 1) // 12
    last_day = datetime.date(last_year, last_month, calendar.monthrange(last_year, last_month)[1])

    while current_week_start <= last_day:
        # Rotate each doctor -2 days from last week's weekday
        new_doctor_to_weekday = {doc: (wd - 2) % 7 for doc, wd in doctor_to_weekday.items()}

        # Assign doctors to this week
        for doc, wd in new_doctor_to_weekday.items():
            day_date = current_week_start + datetime.timedelta(days=wd)
            if day_date <= last_day:
                schedule[day_date] = doc

        doctor_to_weekday = new_doctor_to_weekday
        current_week_start += datetime.timedelta(days=7)

    return schedule

# ---------------------------------------------
# 4. BALANCE TABLE WITH FRIDAY/SAT/SUN
# ---------------------------------------------
def compute_balance_fri_sat_sun(schedule):
    counts = {doc: {"Friday":0, "Saturday":0, "Sunday":0} for doc in DOCTORS}
    for date, doc in schedule.items():
        weekday = date.weekday()
        if weekday == 4:
            counts[doc]["Friday"] += 1
        elif weekday == 5:
            counts[doc]["Saturday"] += 1
        elif weekday == 6:
            counts[doc]["Sunday"] += 1
    df = pd.DataFrame.from_dict(counts, orient="index")
    df.index.name = "Doctor"
    df = df.reset_index()
    return df

# ---------------------------------------------
# 5. PDF EXPORT (CALENDAR GRID)
# ---------------------------------------------
def create_pdf(schedule, filename="schedule_calendar.pdf"):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    
    last_month = None
    pdf.set_font("Arial", "", 12)

    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, month_name, ln=True, align="C")
            pdf.ln(3)
            last_month = month_name

            # Draw weekday headers
            pdf.set_font("Arial", "B", 12)
            days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
            col_width = pdf.w / 7 - 5
            for d in days:
                pdf.cell(col_width, 8, d, border=1, align='C')
            pdf.ln()
            pdf.set_font("Arial", "", 12)

            # Generate weeks
            cal = calendar.Calendar(firstweekday=0)
            m_year, m_month = date.year, date.month
            weeks = cal.monthdatescalendar(m_year, m_month)
            for week in weeks:
                for day in week:
                    if day.month == m_month:
                        doc = schedule.get(day, "")
                        color = DOCTOR_COLORS.get(doc, (220,220,220))
                        text_color = get_text_color(color)
                        pdf.set_fill_color(*color)
                        pdf.set_text_color(*text_color)
                        pdf.cell(col_width, 20, f"{day.day}\n{doc}", border=1, ln=0, align='C', fill=True)
                    else:
                        pdf.set_fill_color(240,240,240)
                        pdf.cell(col_width, 20, "", border=1, ln=0)
                pdf.ln()
    pdf.output(filename)
    return filename

# ---------------------------------------------
# 6. STREAMLIT CALENDAR DISPLAY
# ---------------------------------------------
def display_calendar(schedule):
    last_month = None
    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            st.markdown(f"## {month_name}")
            last_month = month_name
            m_year, m_month = date.year, date.month

            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(m_year, m_month)
            for week in weeks:
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day.month == m_month:
                        doc = schedule.get(day, "")
                        color = '#%02x%02x%02x' % DOCTOR_COLORS.get(doc, (220,220,220))
                        # Highlight Sat/Sun differently
                        if day.weekday() >= 5:
                            color = '#d9d9d9'
                        cols[i].markdown(
                            f"<div style='background-color:{color}; padding:6px; border-radius:4px; text-align:center'>"
                            f"<b>{day.day}</b><br>{doc}</div>", unsafe_allow_html=True)
                    else:
                        cols[i].markdown("<div style='padding:6px'></div>", unsafe_allow_html=True)

# ---------------------------------------------
# 7. STREAMLIT UI
# ---------------------------------------------
st.set_page_config(page_title="📅 Programma Giatron – Backwards Rotation", layout="wide")
st.title("📅 Programma Giatron – Backwards Rotation")

# SESSION STATE
if "initial_week" not in st.session_state:
    st.session_state.initial_week = None
if "start_date" not in st.session_state:
    st.session_state.start_date = None
if "generated_schedule" not in st.session_state:
    st.session_state.generated_schedule = None

# RESET
if st.button("🔄 Reset All"):
    st.session_state.initial_week = None
    st.session_state.start_date = None
    st.session_state.generated_schedule = None
    st.experimental_rerun()

# Sidebar: Doctor balance
with st.sidebar:
    st.subheader("📊 Doctor Weekend Balance Table")
    if st.session_state.generated_schedule:
        balance_df = compute_balance_fri_sat_sun(st.session_state.generated_schedule)
        st.dataframe(balance_df, width=400, height=300)  # prevent wrapping

# 1️⃣ Initial week selection
st.subheader("1️⃣ Select a date in the initial week")
selected_date = st.date_input("Pick a date (Mon–Sun of initial week):", datetime.date.today())
week_dates = get_week_dates(selected_date)
st.write("This week is:")
for d in week_dates:
    st.write("-", d.strftime("%A %d/%m/%Y"))

# 2️⃣ Assign doctors
st.subheader("2️⃣ Assign doctors for the first week")
initial_week = {}
cols = st.columns(7)
for i, d in enumerate(week_dates):
    with cols[i]:
        doc = st.selectbox(d.strftime("%a\n%d/%m"), DOCTORS, key=f"manual_{d}")
        initial_week[d] = doc

if st.button("💾 Save Initial Week"):
    st.session_state.initial_week = [initial_week[d] for d in sorted(initial_week.keys())]
    st.session_state.start_date = week_dates[0]
    st.success("Initial week saved!")

if st.session_state.initial_week is None:
    st.info("Save an initial week to proceed.")
    st.stop()

# 3️⃣ Generate schedule
st.subheader("3️⃣ Generate schedule for forthcoming months")
col1, col2 = st.columns(2)
with col1:
    start_month = st.date_input("Start month", value=st.session_state.start_date)
with col2:
    months_to_generate = st.number_input("Number of months to generate", min_value=1, max_value=12, value=1)

if st.button("🗓️ Generate Schedule"):
    st.session_state.generated_schedule = generate_schedule(
        st.session_state.initial_week,
        start_month,
        months_to_generate
    )

# 4️⃣ Display calendar view
if st.session_state.generated_schedule:
    st.subheader("📋 Calendar View")
    display_calendar(st.session_state.generated_schedule)

# 5️⃣ Export PDF
if st.session_state.generated_schedule:
    st.subheader("📄 Export PDF")
    if st.button("🖨️ Export PDF"):
        pdf_file = create_pdf(st.session_state.generated_schedule)
        with open(pdf_file, "rb") as f:
            st.download_button("⬇️ Download PDF", f, file_name="schedule_calendar.pdf")
