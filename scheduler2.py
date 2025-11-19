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

def rotate_week(week_list, offset=-2):
    offset = offset % 7
    return week_list[-offset:] + week_list[:-offset]

def generate_schedule(initial_week, start_date, months=1):
    schedule = {}
    year, month = start_date.year, start_date.month
    week_doctors = initial_week.copy()  # Preserve initial week

    for m in range(months):
        m_year = year + (month + m - 1) // 12
        m_month = (month + m - 1) % 12 + 1
        num_days = calendar.monthrange(m_year, m_month)[1]
        all_dates = [datetime.date(m_year, m_month, d) for d in range(1, num_days + 1)]

        i = 0
        while i < len(all_dates):
            week_block = all_dates[i:i + 7]
            if i == 0 and week_block[0] == start_date:
                # Preserve initial week exactly
                for d, doc in zip(week_block, week_doctors):
                    schedule[d] = doc
            else:
                # Rotation starts from the second week onward
                week_doctors = rotate_week(week_doctors, offset=-2)
                for d, doc in zip(week_block, week_doctors):
                    schedule[d] = doc
            i += 7
    return schedule

def compute_balance(schedule):
    counts = {doc: 0 for doc in DOCTORS}
    for doc in schedule.values():
        counts[doc] += 1
    df = pd.DataFrame.from_dict(counts, orient="index", columns=["Shifts"])
    df.index.name = "Doctor"
    return df.reset_index()

def get_text_color(rgb):
    r, g, b = rgb
    brightness = (r*299 + g*587 + b*114)/1000
    return (0,0,0) if brightness > 125 else (255,255,255)

# ---------------------------------------------
# PDF Export with Calendar Grid
# ---------------------------------------------
def create_pdf(schedule, filename="schedule_calendar.pdf"):
    pdf = FPDF(orientation='L', unit='mm', format='A4')  # Landscape
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
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
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
                        pdf.multi_cell(col_width, 15, f"{day.day}\n{doc}", border=1, ln=3, align='C', fill=True)
                    else:
                        pdf.set_fill_color(240,240,240)
                        pdf.cell(col_width, 15, "", border=1, ln=0)
                pdf.ln()
    pdf.output(filename)
    return filename

# ---------------------------------------------
# Calendar View in Streamlit
# ---------------------------------------------
def display_calendar(schedule):
    """Display schedule in a 7-column calendar grid per month."""
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
                        cols[i].markdown(
                            f"<div style='background-color:{color}; padding:6px; border-radius:4px; text-align:center'>"
                            f"<b>{day.day}</b><br>{doc}</div>", unsafe_allow_html=True)
                    else:
                        cols[i].markdown("<div style='padding:6px'></div>", unsafe_allow_html=True)

# ---------------------------------------------
# STREAMLIT UI
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
    st.subheader("📊 Doctor Balance Table")
    if st.session_state.generated_schedule:
        balance_df = compute_balance(st.session_state.generated_schedule)
        st.table(balance_df)

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
