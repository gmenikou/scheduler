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

    for i, doc in enumerate(initial_week):
        schedule[start_date + datetime.timedelta(days=i)] = doc

    current_week_start = start_date + datetime.timedelta(days=7)

    while current_week_start <= end_date:
        new_doctor_to_weekday = {
            doc: (wd - 2) % 7 for doc, wd in doctor_to_weekday.items()
        }

        for doc, wd in new_doctor_to_weekday.items():
            day_date = current_week_start + datetime.timedelta(days=wd)
            if day_date <= end_date:
                schedule[day_date] = doc

        doctor_to_weekday = new_doctor_to_weekday
        current_week_start += datetime.timedelta(days=7)

    return schedule

# ----------------------------
# 4. BALANCE TABLE (FULL)
# ----------------------------
def compute_balance_fri_sat_sun(schedule):
    counts = {
        doc: {
            "Monday": 0,
            "Tuesday": 0,
            "Wednesday": 0,
            "Thursday": 0,
            "Friday": 0,
            "Saturday": 0,
            "Sunday": 0,
        }
        for doc in DOCTORS
    }

    for date, doc in schedule.items():
        wd = date.weekday()
        if wd == 0:
            counts[doc]["Monday"] += 1
        elif wd == 1:
            counts[doc]["Tuesday"] += 1
        elif wd == 2:
            counts[doc]["Wednesday"] += 1
        elif wd == 3:
            counts[doc]["Thursday"] += 1
        elif wd == 4:
            counts[doc]["Friday"] += 1
        elif wd == 5:
            counts[doc]["Saturday"] += 1
        elif wd == 6:
            counts[doc]["Sunday"] += 1

    df = pd.DataFrame.from_dict(counts, orient="index")
    df.index.name = "Doctor"
    df = df.reset_index()

    df["Weekdays"] = df["Monday"] + df["Tuesday"] + df["Wednesday"] + df["Thursday"]
    df["Weekend"] = df["Friday"] + df["Saturday"] + df["Sunday"]
    df["Total"] = df["Weekdays"] + df["Weekend"]

    df = df.rename(columns={
        "Monday": "Mon",
        "Tuesday": "Tue",
        "Wednesday": "Wed",
        "Thursday": "Thu",
        "Friday": "Fri",
        "Saturday": "Sat",
        "Sunday": "Sun"
    })

    df = df[
        ["Doctor",
         "Mon", "Tue", "Wed", "Thu",
         "Fri", "Sat", "Sun",
         "Weekdays", "Weekend", "Total"]
    ]

    return df

# ----------------------------
# 5. PDF EXPORT
# ----------------------------
def create_pdf(schedule, filename="schedule_calendar.pdf"):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", "", 12)

    last_month = None

    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, month_name, ln=True, align="C")
            pdf.ln(3)
            last_month = month_name

            pdf.set_font("Arial", "B", 12)
            days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
            col_width = pdf.w / 7 - 5
            for d in days:
                pdf.cell(col_width, 8, d, border=1, align='C')
            pdf.ln()
            pdf.set_font("Arial", "", 12)

            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(date.year, date.month)

            for week in weeks:
                for day in week:
                    if day.month == date.month:
                        doc = schedule.get(day, "")
                        color = DOCTOR_COLORS.get(doc, (220,220,220))
                        text_color = get_text_color(color)
                        pdf.set_fill_color(*color)
                        pdf.set_text_color(*text_color)
                        pdf.cell(col_width, 20, f"{day.day}\n{doc}", border=1, align='C', fill=True)
                    else:
                        pdf.set_fill_color(240,240,240)
                        pdf.cell(col_width, 20, "", border=1)
                pdf.ln()

    pdf.output(filename)
    return filename

# ----------------------------
# 6. STREAMLIT CALENDAR DISPLAY
# ----------------------------
def display_calendar(schedule):
    last_month = None
    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            st.markdown(f"## {month_name}")
            last_month = month_name

            header_cols = st.columns(7)
            for i, d in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
                header_cols[i].markdown(f"**{d}**")

            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(date.year, date.month)

            for week in weeks:
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day.month == date.month:
                        doc = schedule.get(day, "")
                        color = '#%02x%02x%02x' % DOCTOR_COLORS.get(doc, (220,220,220))
                        cols[i].markdown(
                            f"<div style='background-color:{color}; padding:6px; border-radius:4px; text-align:center'>"
                            f"<b>{day.day}</b><br>{doc}</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        cols[i].markdown("")

# ----------------------------
# 7. STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="📅 Programma Giatron – Backwards Rotation", layout="wide")
st.title("📅 Programma Giatron – Backwards Rotation")

for key in ["initial_week", "start_date", "generated_schedule", "balance_df"]:
    if key not in st.session_state:
        st.session_state[key] = None

if st.button("🔄 Reset All"):
    for key in ["initial_week", "start_date", "generated_schedule", "balance_df"]:
        st.session_state[key] = None
    st.experimental_rerun()

left_col, right_col = st.columns([0.35, 0.65])

# LEFT: BALANCE
with left_col:
    st.subheader("📊 Weekend & Weekday Balance")
    if st.session_state.balance_df is not None:
        st.dataframe(
            st.session_state.balance_df,
            use_container_width=True,
            height=800,
            column_config={
                "Doctor": st.column_config.TextColumn(width="medium"),
                "Mon": st.column_config.NumberColumn(width="small"),
                "Tue": st.column_config.NumberColumn(width="small"),
                "Wed": st.column_config.NumberColumn(width="small"),
                "Thu": st.column_config.NumberColumn(width="small"),
                "Fri": st.column_config.NumberColumn(width="small"),
                "Sat": st.column_config.NumberColumn(width="small"),
                "Sun": st.column_config.NumberColumn(width="small"),
                "Weekdays": st.column_config.NumberColumn(width="small"),
                "Weekend": st.column_config.NumberColumn(width="small"),
                "Total": st.column_config.NumberColumn(width="small"),
            }
        )

# RIGHT: MAIN UI
with right_col:
    st.subheader("1️⃣ Select a date in the initial week")
    selected_date = st.date_input("Pick a date (Mon–Sun of initial week):", datetime.date.today())
    week_dates = get_week_dates(selected_date)

    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            initial_week[d] = st.selectbox(d.strftime("%a %d/%m"), DOCTORS, key=f"manual_{d}")

    if st.button("💾 Save Initial Week"):
        st.session_state.initial_week = [initial_week[d] for d in sorted(initial_week)]
        st.session_state.start_date = week_dates[0]

    if st.session_state.initial_week is None:
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        start_month = st.date_input("Start date", st.session_state.start_date)
    with col2:
        end_month = st.date_input("End date", st.session_state.start_date + datetime.timedelta(days=30))

    if st.button("🗓️ Generate Schedule"):
        st.session_state.generated_schedule = generate_schedule(
            st.session_state.initial_week, start_month, end_month
        )
        st.session_state.balance_df = compute_balance_fri_sat_sun(
            st.session_state.generated_schedule
        )

    if st.session_state.generated_schedule:
        display_calendar(st.session_state.generated_schedule)

        if st.button("🖨️ Export PDF"):
            pdf_file = create_pdf(st.session_state.generated_schedule)
            with open(pdf_file, "rb") as f:
                st.download_button("⬇️ Download PDF", f, file_name="schedule_calendar.pdf")
