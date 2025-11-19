import streamlit as st
import datetime
import calendar
import pandas as pd
from fpdf import FPDF

# ----------------------------
# 1. CONSTANTS
# ----------------------------
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

# ----------------------------
# 2. HELPERS
# ----------------------------
def get_week_dates(any_date):
    monday = any_date - datetime.timedelta(days=any_date.weekday())
    return [monday + datetime.timedelta(days=i) for i in range(7)]

def get_text_color(rgb):
    r, g, b = rgb
    brightness = (r*299 + g*587 + b*114)/1000
    return (0,0,0) if brightness > 125 else (255,255,255)

# ----------------------------
# 3. SCHEDULE GENERATION
# ----------------------------
def generate_schedule(initial_week, start_date, end_date):
    schedule = {}
    doctor_to_weekday = {doc: i for i, doc in enumerate(initial_week)}

    # Preserve initial week
    for i, doc in enumerate(initial_week):
        schedule[start_date + datetime.timedelta(days=i)] = doc

    current_week_start = start_date + datetime.timedelta(days=7)

    while current_week_start <= end_date:
        new_doctor_to_weekday = {doc: (wd - 2) % 7 for doc, wd in doctor_to_weekday.items()}
        for doc, wd in new_doctor_to_weekday.items():
            day_date = current_week_start + datetime.timedelta(days=wd)
            if day_date <= end_date:
                schedule[day_date] = doc
        doctor_to_weekday = new_doctor_to_weekday
        current_week_start += datetime.timedelta(days=7)

    return schedule

# ----------------------------
# 4. BALANCE TABLE
# ----------------------------
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

# ----------------------------
# 5. PDF EXPORT
# ----------------------------
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

            # Weekday header row
            pdf.set_font("Arial", "B", 12)
            days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
            col_width = pdf.w / 7 - 5
            for d in days:
                pdf.cell(col_width, 8, d, border=1, align='C')
            pdf.ln()
            pdf.set_font("Arial", "", 12)

            # Weeks
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

# ----------------------------
# 6. STREAMLIT CALENDAR DISPLAY
# ----------------------------
def display_calendar(schedule, show_balance=False):
    last_month = None
    first_month_done = False
    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            st.markdown(f"## {month_name}")
            last_month = month_name
            m_year, m_month = date.year, date.month

            # Weekday headers
            if show_balance and not first_month_done:
                header_cols = st.columns([0.6]*7 + [0.4])
            else:
                header_cols = st.columns(7)
            days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
            for i, d in enumerate(days):
                header_cols[i].markdown(f"**{d}**", unsafe_allow_html=True)

            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(m_year, m_month)

            for week in weeks:
                if show_balance and not first_month_done:
                    cols = st.columns([0.6]*7 + [0.4])
                else:
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

            # Show balance table next to first month
            if show_balance and not first_month_done:
                with cols[-1]:
                    st.subheader("📊 Weekend Balance (All Months)")
                    if "balance_df" in st.session_state:
                        st.dataframe(st.session_state.balance_df, width=250, height=400)
                first_month_done = True

# ----------------------------
# 7. STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="📅 Programma Giatron – Backwards Rotation", layout="wide")
st.title("📅 Programma Giatron – Backwards Rotation")

# Session state
for key in ["initial_week", "start_date", "generated_schedule", "balance_df"]:
    if key not in st.session_state:
        st.session_state[key] = None

# Reset
if st.button("🔄 Reset All"):
    for key in ["initial_week", "start_date", "generated_schedule", "balance_df"]:
        st.session_state[key] = None
    st.experimental_rerun()

# Right panel: Main UI
right_col, _ = st.columns([0.65, 0.35])  # right side main content
with right_col:
    st.subheader("1️⃣ Select a date in the initial week")
    selected_date = st.date_input("Pick a date (Mon–Sun of initial week):", datetime.date.today())
    week_dates = get_week_dates(selected_date)
    st.write("This week is:")
    for d in week_dates:
        st.write("-", d.strftime("%A %d/%m/%Y"))

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

    st.subheader("3️⃣ Generate schedule (Start → End)")
    col1, col2 = st.columns(2)
    with col1:
        start_month = st.date_input("Start date (Monday of initial week)", value=st.session_state.start_date)
    with col2:
        end_month = st.date_input("End date", value=st.session_state.start_date + datetime.timedelta(days=30))

    generate_clicked = st.button("🗓️ Generate Schedule")
    if generate_clicked:
        st.session_state.generated_schedule = generate_schedule(
            st.session_state.initial_week,
            start_month,
            end_month
        )
        # Recalculate balance for all months immediately
        st.session_state.balance_df = compute_balance_fri_sat_sun(st.session_state.generated_schedule)

    # Display calendar
    if st.session_state.generated_schedule:
        st.subheader("📋 Calendar View")
        display_calendar(st.session_state.generated_schedule, show_balance=True)

    # Export PDF
    if st.session_state.generated_schedule:
        st.subheader("📄 Export PDF")
        if st.button("🖨️ Export PDF"):
            pdf_file = create_pdf(st.session_state.generated_schedule)
            with open(pdf_file, "rb") as f:
                st.download_button("⬇️ Download PDF", f, file_name="schedule_calendar.pdf")
