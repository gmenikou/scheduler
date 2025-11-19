import streamlit as st
import datetime
import calendar
from fpdf import FPDF
import json
import os
import pandas as pd

# -------------------------------
# Constants
# -------------------------------
DOCTORS = ["Elena", "Eva", "Maria", "Athina", "Alexandros", "Elia", "Christina"]
DOCTOR_COLORS = {
    "Elena": "#FF9999",
    "Eva": "#99FF99",
    "Maria": "#9999FF",
    "Athina": "#FFFF99",
    "Alexandros": "#FF99FF",
    "Elia": "#99FFFF",
    "Christina": "#FFCC99",
}
INIT_FILE = "initial_week.json"

# -------------------------------
# Helpers
# -------------------------------
def get_week_dates(any_date):
    monday = any_date - datetime.timedelta(days=any_date.weekday())
    return [monday + datetime.timedelta(days=i) for i in range(7)]

def save_initial_week(initial_week):
    serializable = {d.strftime("%Y-%m-%d"): doc for d, doc in initial_week.items()}
    with open(INIT_FILE, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False)

def load_initial_week():
    if os.path.exists(INIT_FILE):
        with open(INIT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {datetime.datetime.strptime(k, "%Y-%m-%d").date(): v for k, v in data.items()}
    return None

def rotate_week_list(week_list, shift):
    shift = shift % 7
    return week_list[-shift:] + week_list[:-shift]

def generate_schedule(initial_week, start_date, end_date):
    schedule = {}
    week_list = [initial_week[d] for d in sorted(initial_week.keys())]
    initial_monday = min(initial_week.keys())
    current = initial_monday
    week_counter = 1
    while current <= end_date:
        week_block = [current + datetime.timedelta(days=i) for i in range(7)]
        if any(d in initial_week for d in week_block):
            # Preserve initial week
            for d in week_block:
                if start_date <= d <= end_date and d in initial_week:
                    schedule[d] = initial_week[d]
        else:
            # Rotate week starting after initial
            rotated_week = rotate_week_list(week_list, -2 * (week_counter - 1))
            for idx, d in enumerate(week_block):
                if start_date <= d <= end_date:
                    schedule[d] = rotated_week[idx % 7]
            week_counter += 1
        current += datetime.timedelta(days=7)
    return schedule

def compute_balance(schedule):
    balance = {doc: 0 for doc in DOCTORS}
    for d in schedule.values():
        balance[d] += 1
    return balance

# -------------------------------
# PDF Export (Single-column calendar)
# -------------------------------
class PDFCalendar(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        self.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf', uni=True)

    def create_calendar(self, schedule_dict, title="ΠΡΟΓΡΑΜΜΑ ΓΙΑΤΡΩΝ"):
        self.add_page()
        self.set_font("DejaVu", 'B', 16)
        self.cell(0, 12, title, 0, 1, "C")
        self.ln(4)
        self.set_font("DejaVu", '', 12)

        for month_str in schedule_dict:
            self.set_font("DejaVu", 'B', 14)
            self.cell(0, 10, f"📅 {month_str}", 0, 1)
            self.set_font("DejaVu", '', 12)
            schedule = schedule_dict[month_str]
            for d in sorted(schedule.keys()):
                weekday = d.strftime("%a")
                doctor = schedule[d]
                color = DOCTOR_COLORS.get(doctor, "#FFFFFF")
                r, g, b = tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2 ,4))
                self.set_fill_color(r, g, b)
                self.cell(0, 8, f"{d.strftime('%d/%m/%Y')} ({weekday}) → {doctor}", 0, 1, fill=True)

            # Month balance
            balance = compute_balance(schedule)
            self.ln(2)
            self.set_font("DejaVu", 'B', 12)
            self.cell(0, 8, "Balance Table", 0, 1)
            self.set_font("DejaVu", '', 12)
            for doc, count in balance.items():
                color = DOCTOR_COLORS.get(doc, "#FFFFFF")
                r, g, b = tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2 ,4))
                self.set_fill_color(r, g, b)
                self.cell(0, 6, f"{doc} → {count} shifts", 0, 1, fill=True)
            self.ln(4)

def export_calendar_pdf(schedule_dict, filename="schedule.pdf"):
    pdf = PDFCalendar()
    pdf.create_calendar(schedule_dict)
    pdf.output(filename)
    return filename

# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(layout="wide")
st.title("📅 Programma Giatron – Backwards Rotation")

# Load initial week
if "initial_week" not in st.session_state:
    st.session_state.initial_week = load_initial_week()

# -------------------------------
# Sidebar
# -------------------------------
with st.sidebar:
    st.header("Controls")

    # Reset
    if st.button("🔄 Reset All"):
        st.session_state.clear()
        if os.path.exists(INIT_FILE):
            os.remove(INIT_FILE)
        st.success("Session and initial week deleted.")
        st.stop()

    # Step 1: Initial week selection
    st.subheader("1️⃣ Initial Week Date")
    if st.session_state.initial_week is None:
        selected_date = st.date_input("Choose a date:", datetime.date.today())
        week_dates = get_week_dates(selected_date)
        st.write("Week:")
        for d in week_dates:
            st.write("-", d.strftime("%d/%m/%Y"))
    else:
        week_dates = sorted(st.session_state.initial_week.keys())
        st.info("Initial week already saved:")
        for d in week_dates:
            st.write("-", d.strftime("%d/%m/%Y"))

    # Step 2: Assign doctors
    st.subheader("2️⃣ Assign Doctors")
    if st.session_state.initial_week is None:
        initial_week = {}
        cols = st.columns(7)
        for i, d in enumerate(week_dates):
            with cols[i]:
                doc = st.selectbox(d.strftime("%a\n%d/%m"), DOCTORS, key=f"manual_{d}")
                initial_week[d] = doc

        if st.button("💾 Save Initial Week"):
            st.session_state.initial_week = initial_week
            save_initial_week(initial_week)
            st.success("Initial week saved!")

    # Step 3: Schedule generation
    if st.session_state.initial_week:
        st.subheader("3️⃣ Schedule Range / Months")
        start_date = st.date_input("Start date:", min_value=min(week_dates))
        months_to_generate = st.number_input("Number of months to generate:", min_value=1, value=1)
        if st.button("Generate Schedule"):
            all_schedules = {}
            current_start = start_date.replace(day=1)
            for _ in range(months_to_generate):
                year = current_start.year
                month = current_start.month
                num_days = calendar.monthrange(year, month)[1]
                month_start = datetime.date(year, month, 1)
                month_end = datetime.date(year, month, num_days)
                sched = generate_schedule(st.session_state.initial_week, month_start, month_end)
                month_str = current_start.strftime("%B %Y")
                all_schedules[month_str] = sched
                # next month
                next_month = month + 1 if month < 12 else 1
                next_year = year + 1 if next_month == 1 else year
                current_start = datetime.date(next_year, next_month, 1)
            st.session_state.generated_schedule = all_schedules
            st.success("Schedule generated!")

# -------------------------------
# Main Panel: Editable Schedule
# -------------------------------
st.subheader("📋 Schedule & Balance Table (Editable & Color-coded)")

if "generated_schedule" in st.session_state and st.session_state.generated_schedule:
    for month_str, schedule in st.session_state.generated_schedule.items():
        st.write(f"### 📅 {month_str}")
        # Convert schedule to DataFrame
        df = pd.DataFrame({
            "Date": [d.strftime("%d/%m/%Y (%a)") for d in schedule.keys()],
            "Doctor": [schedule[d] for d in schedule.keys()]
        })

        # Apply color coding
        def color_doctor(val):
            color = DOCTOR_COLORS.get(val, "#FFFFFF")
            return f'background-color: {color}'

        styled_df = df.style.applymap(color_doctor, subset=["Doctor"])
        st.dataframe(styled_df, use_container_width=True)

        # Editable table
        edited_df = st.experimental_data_editor(df, num_rows="dynamic", use_container_width=True)
        for idx, row in edited_df.iterrows():
            d_str = row["Date"].split(" ")[0]  # extract dd/mm/yyyy
            d = datetime.datetime.strptime(d_str, "%d/%m/%Y").date()
            schedule[d] = row["Doctor"]

        # Balance table
        balance = compute_balance(schedule)
        st.write("### Balance Table")
        st.table(balance)

    # PDF export
    if st.button("🖨️ Export PDF for All Months"):
        export_calendar_pdf(st.session_state.generated_schedule)
        st.success("PDF created! Check app folder for schedule.pdf")
else:
    st.info("Generate a schedule first to see it here.")
