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
    """Generate schedule month by month starting from initial week."""
    schedule = {}
    year, month = start_date.year, start_date.month
    week_doctors = initial_week.copy()
    
    for m in range(months):
        m_year = year + (month + m - 1) // 12
        m_month = (month + m - 1) % 12 + 1
        num_days = calendar.monthrange(m_year, m_month)[1]
        all_dates = [datetime.date(m_year, m_month, d) for d in range(1, num_days+1)]
        
        i = 0
        while i < len(all_dates):
            week_block = all_dates[i:i+7]
            if i == 0 and week_block[0] == start_date:
                # first week: preserve initial week
                for d, doc in zip(week_block, week_doctors):
                    schedule[d] = doc
            else:
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
    df = df.reset_index()
    return df

def get_text_color(rgb):
    """Return black or white text depending on background brightness."""
    r, g, b = rgb
    brightness = (r*299 + g*587 + b*114)/1000
    return (0,0,0) if brightness > 125 else (255,255,255)

def create_pdf(schedule, filename="schedule.pdf"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Doctor Schedule", ln=True, align="C")
    pdf.ln(5)
    
    last_month = None
    pdf.set_font("Arial", "", 12)
    
    for date in sorted(schedule.keys()):
        doc = schedule[date]
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            pdf.ln(3)
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 8, month_name, ln=True)
            pdf.set_font("Arial", "", 12)
            last_month = month_name
        
        color = DOCTOR_COLORS.get(doc, (200,200,200))
        text_color = get_text_color(color)
        pdf.set_fill_color(*color)
        pdf.set_text_color(*text_color)
        pdf.cell(50, 8, date.strftime("%d/%m (%a)"), border=1, fill=True)
        pdf.cell(0, 8, doc, border=1, ln=True, fill=True)
    
    pdf.output(filename)
    return filename

# ---------------------------------------------
# 3. STREAMLIT UI
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

# LEFT PANEL: balance table
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

# 4️⃣ Display schedule single-column, color-coded by doctor
if st.session_state.generated_schedule:
    st.subheader("📋 Calendar View")
    last_month = None
    for date in sorted(st.session_state.generated_schedule.keys()):
        doc = st.session_state.generated_schedule[date]
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            st.markdown(f"### {month_name}")
            last_month = month_name
        color = '#%02x%02x%02x' % DOCTOR_COLORS.get(doc, (200,200,200))
        st.markdown(f"<div style='background-color:{color}; padding:4px'>{date.strftime('%d/%m (%a)')} → {doc}</div>", unsafe_allow_html=True)

# 5️⃣ Export PDF
if st.session_state.generated_schedule:
    st.subheader("📄 Export PDF")
    if st.button("🖨️ Export PDF"):
        pdf_file = create_pdf(st.session_state.generated_schedule)
        with open(pdf_file, "rb") as f:
            st.download_button("⬇️ Download PDF", f, file_name="schedule.pdf")
