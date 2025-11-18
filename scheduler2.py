import streamlit as st
import datetime
import calendar
from fpdf import FPDF
import json
import os

# -------------------------------
# Constants
# -------------------------------
DOCTORS = ["Elena", "Eva", "Maria", "Athina", "Alexandros", "Elia", "Christina"]
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

def generate_schedule(initial_week, all_dates):
    schedule = {}
    week_list = [initial_week[d] for d in sorted(initial_week.keys())]
    initial_monday = min(initial_week.keys())

    # Start grouping weeks from Monday of initial week
    start_date = initial_monday
    weeks = []
    current = start_date
    while current <= max(all_dates):
        week_block = [current + datetime.timedelta(days=i) for i in range(7)]
        weeks.append(week_block)
        current += datetime.timedelta(days=7)

    week_counter = 0
    for week_block in weeks:
        # Skip weeks completely before initial week (should not happen now)
        if max(week_block) < initial_monday:
            continue

        # Preserve initial week exactly
        if any(d in initial_week for d in week_block):
            for d in week_block:
                if d in initial_week:
                    schedule[d] = initial_week[d]
        else:
            # Rotation for weeks after initial
            rotated_week = rotate_week_list(week_list, -2 * week_counter)
            for idx, d in enumerate(week_block):
                if d in all_dates:  # only keep dates in this month(s)
                    schedule[d] = rotated_week[idx % 7]
            week_counter += 1

    # Only keep dates from initial week onwards
    schedule = {d: doc for d, doc in schedule.items() if d >= initial_monday}
    return schedule

def generate_schedule_for_months(initial_week, start_month, num_months=1):
    all_schedules = {}
    for m in range(num_months):
        month = (start_month.month + m - 1) % 12 + 1
        year = start_month.year + ((start_month.month + m - 1) // 12)
        num_days = calendar.monthrange(year, month)[1]
        month_dates = [datetime.date(year, month, d) for d in range(1, num_days + 1)]
        schedule = generate_schedule(initial_week, month_dates)
        all_schedules[(year, month)] = schedule
    return all_schedules

# PDF export
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Programma Giatron", 0, 1, "C")
        self.ln(4)

    def create_schedule_table(self, assignments):
        self.set_font("Arial", "", 12)
        self.set_fill_color(220, 220, 220)
        self.cell(60, 8, "Date", 1, 0, "C", 1)
        self.cell(80, 8, "Doctor", 1, 1, "C", 1)
        for d in sorted(assignments.keys()):
            weekday = d.strftime("%a")
            self.cell(60, 8, f"{d.strftime('%d/%m/%Y')} ({weekday})", 1, 0, "C")
            self.cell(80, 8, assignments[d], 1, 1, "C")

def create_pdf_multi_months(all_schedules, filename="schedule.pdf"):
    pdf = PDF()
    pdf.add_page()
    for (year, month), schedule in all_schedules.items():
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, datetime.date(year, month, 1).strftime("Programma Giatron - %B %Y"), 0, 1, "C")
        pdf.ln(2)
        pdf.create_schedule_table(schedule)
        pdf.add_page()
    pdf.output(filename)
    return filename

# -------------------------------
# Streamlit App
# -------------------------------
st.title("📅 Programma Giatron – Backwards Rotation")

if "initial_week" not in st.session_state:
    st.session_state.initial_week = load_initial_week()
if "start_date" not in st.session_state:
    st.session_state.start_date = None

# Reset All
if st.button("🔄 Reset All"):
    st.session_state.clear()
    if os.path.exists(INIT_FILE):
        os.remove(INIT_FILE)
    st.success("Session and initial week deleted.")
    st.stop()

# Step 1: Select initial week date
st.subheader("1️⃣ Select a date in the initial week")
if st.session_state.start_date is None:
    selected_date = st.date_input("Choose a date:", datetime.date.today())
else:
    selected_date = st.session_state.start_date

week_dates = get_week_dates(selected_date)
st.write("The week is:")
for d in week_dates:
    st.write("-", d.strftime("%d/%m/%Y"))

# Step 2: Assign doctors
st.subheader("2️⃣ Assign doctors for the first week")
if st.session_state.initial_week is None:
    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            doc = st.selectbox(d.strftime("%a\n%d/%m"), DOCTORS, key=f"manual_{d}")
            initial_week[d] = doc

    if st.button("💾 Save initial week"):
        st.session_state.initial_week = initial_week
        st.session_state.start_date = selected_date
        save_initial_week(initial_week)
        st.success("Initial week saved!")
else:
    st.info("Initial week already saved. Use Reset to change it.")

if st.session_state.initial_week:
    st.write("Your assigned initial week:")
    for d in sorted(st.session_state.initial_week.keys()):
        st.write(f"{d.strftime('%d/%m/%Y')} ({d.strftime('%a')}) → {st.session_state.initial_week[d]}")

# Step 3: Generate schedule
if st.session_state.initial_week and st.session_state.start_date:
    st.subheader("3️⃣ Generate schedule for forthcoming months")
    today = datetime.date.today()
    months_options = [(today + datetime.timedelta(days=30*i)).replace(day=1) for i in range(12)]
    months_display = [d.strftime("%B %Y") for d in months_options]
    selected_month_index = st.selectbox("Choose start month:", list(range(12)),
                                        format_func=lambda x: months_display[x])
    selected_month_date = months_options[selected_month_index]

    num_months = st.number_input("Number of months to generate:", min_value=1, max_value=12, value=1, step=1)

    if st.button("Generate Schedule"):
        multi_schedule = generate_schedule_for_months(st.session_state.initial_week,
                                                      selected_month_date, num_months)
        for (year, month), schedule in multi_schedule.items():
            st.write(f"### 📋 Schedule for {datetime.date(year, month, 1).strftime('%B %Y')}")
            for d in sorted(schedule.keys()):
                st.write(f"{d.strftime('%d/%m/%Y')} ({d.strftime('%a')}) → {schedule[d]}")

        # PDF export buttons
        st.subheader("📄 Export PDF for selected month")
        if st.button("🖨️ Create PDF for selected month only"):
            schedule_single = multi_schedule[(selected_month_date.year, selected_month_date.month)]
            filename = create_pdf_multi_months({(selected_month_date.year, selected_month_date.month): schedule_single})
            with open(filename, "rb") as f:
                st.download_button("⬇️ Download PDF", data=f, file_name=f"schedule_{selected_month_date.strftime('%B_%Y')}.pdf")

        st.subheader("📄 Export PDF for all generated months")
        if st.button("🖨️ Create PDF for all months"):
            filename = create_pdf_multi_months(multi_schedule)
            with open(filename, "rb") as f:
                st.download_button("⬇️ Download PDF", data=f, file_name="schedule_all_months.pdf")
