import streamlit as st
import datetime
import calendar
from fpdf import FPDF
import json
import os

# ---------------------------------------------
# 1. CONSTANTS
# ---------------------------------------------
DOCTORS = ["Elena", "Eva", "Maria", "Athina", "Alexandros", "Elia", "Christina"]
INIT_FILE = "initial_week.json"

# ---------------------------------------------
# 2. HELPERS
# ---------------------------------------------
def get_week_dates(any_date):
    monday = any_date - datetime.timedelta(days=any_date.weekday())
    return [monday + datetime.timedelta(days=i) for i in range(7)]

def get_month_dates(year, month):
    num_days = calendar.monthrange(year, month)[1]
    return [datetime.date(year, month, d) for d in range(1, num_days+1)]

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

# ---------------------------------------------
# 3. Multi-month schedule with preserved initial week
# ---------------------------------------------
def generate_multi_month_schedule_fixed(initial_week, start_month, num_months=3):
    all_months_schedule = {}
    # Ordered doctors of initial week
    initial_week_sorted = [initial_week[d] for d in sorted(initial_week.keys())]
    last_rotated_week = initial_week_sorted.copy()

    for m in range(num_months):
        month_start = (start_month + datetime.timedelta(days=30*m)).replace(day=1)
        year = month_start.year
        month = month_start.month
        num_days = calendar.monthrange(year, month)[1]
        month_dates = [datetime.date(year, month, d) for d in range(1, num_days+1)]

        weeks = [month_dates[i:i+7] for i in range(0, len(month_dates), 7)]
        assignments = {}

        for w_idx, block in enumerate(weeks):
            # Preserve initial week dates exactly
            preserved_block = {d: initial_week[d] for d in block if d in initial_week}
            non_preserved_dates = [d for d in block if d not in initial_week]

            if w_idx == 0 and preserved_block:
                rotated = last_rotated_week
            else:
                offset = 2 % 7
                rotated = last_rotated_week[-offset:] + last_rotated_week[:-offset]

            for i, d in enumerate(block):
                if d in preserved_block:
                    assignments[d] = preserved_block[d]
                else:
                    assignments[d] = rotated[i % 7]

            last_rotated_week = [assignments[d] for d in block]

        all_months_schedule[(year, month)] = assignments

    return all_months_schedule

# ---------------------------------------------
# PDF latin-only (avoid Unicode errors)
# ---------------------------------------------
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Programma Giatron – Month", 0, 1, "C")
        self.ln(4)

    def create_schedule_table(self, assignments):
        self.set_font("Arial", "", 12)
        self.set_fill_color(220, 220, 220)
        self.cell(60, 8, "Date", 1, 0, "C", 1)
        self.cell(80, 8, "Doctor", 1, 1, "C", 1)
        for d in sorted(assignments.keys()):
            self.cell(60, 8, d.strftime("%d/%m/%Y"), 1, 0, "C")
            self.cell(80, 8, assignments[d], 1, 1, "C")

def create_pdf(assignments, month_year_str, filename="schedule.pdf"):
    pdf = PDF()
    pdf.title = f"Programma Giatron – {month_year_str}"
    pdf.add_page()
    pdf.create_schedule_table(assignments)
    pdf.output(filename)
    return filename

# ---------------------------------------------
# 4. STREAMLIT APP
# ---------------------------------------------
st.title("📅 Programma Giatron – Backwards Rotation")

# Session initialization
if "initial_week" not in st.session_state:
    st.session_state.initial_week = load_initial_week()
if "start_date" not in st.session_state:
    st.session_state.start_date = None

# Reset
if st.button("🔄 Reset All"):
    st.session_state.clear()
    if os.path.exists(INIT_FILE):
        os.remove(INIT_FILE)
    st.success("Session and initial week deleted.")
    st.stop()

# Step 1: Select initial date
st.subheader("1️⃣ Select a date in the initial week")
if st.session_state.start_date is None:
    selected_date = st.date_input("Choose a date:", datetime.date.today())
else:
    selected_date = st.session_state.start_date

week_dates = get_week_dates(selected_date)
st.write("The week is:")
for d in week_dates:
    st.write("-", d.strftime("%d/%m/%Y"))

# Step 2: Manual assignment
st.subheader("2️⃣ Assign doctors for the first week")
if st.session_state.initial_week is None:
    initial_week = {}
    selected_doctors = []
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            doc = st.selectbox(d.strftime("%a\n%d/%m"), DOCTORS, key=f"manual_{d}")
            initial_week[d] = doc
            selected_doctors.append(doc)

    if len(set(selected_doctors)) < len(selected_doctors):
        st.error("❗ Duplicate doctors in the same week are not allowed.")
    else:
        if st.button("💾 Save initial week"):
            st.session_state.initial_week = initial_week
            st.session_state.start_date = selected_date
            save_initial_week(initial_week)
            st.success("Initial week saved!")
else:
    st.info("Initial week already saved. Use Reset to change it.")

# Step 2b: Show initial week exactly as assigned
if st.session_state.initial_week is not None:
    st.write("Your assigned initial week:")
    for d in sorted(st.session_state.initial_week.keys()):
        st.write(d.strftime("%d/%m/%Y"), "→", st.session_state.initial_week[d])

# Step 3: Select month(s) and generate schedule
st.subheader("3️⃣ Select month for full schedule")
today = datetime.date.today()
months_options = [(today + datetime.timedelta(days=30*i)).replace(day=1) for i in range(12)]
months_display = [d.strftime("%B %Y") for d in months_options]

selected_month_index = st.selectbox("Choose month:", list(range(12)), format_func=lambda x: months_display[x])
selected_month_date = months_options[selected_month_index]

num_months = st.number_input("Number of months to generate:", min_value=1, max_value=12, value=1, step=1)

if st.button("Generate Month Schedule"):
    multi_schedule = generate_multi_month_schedule_fixed(st.session_state.initial_week, selected_month_date, num_months)

    # Show schedules
    for (year, month), assignments in multi_schedule.items():
        st.write(f"### 📋 Schedule for {datetime.date(year, month, 1).strftime('%B %Y')}")
        for d in sorted(assignments.keys()):
            st.write(d.strftime("%d/%m/%Y"), "→", assignments[d])

    # PDF export in latin-only
    st.subheader("📄 Export PDF")
    if st.button("🖨️ Create PDF for selected month"):
        assignments = multi_schedule[(selected_month_date.year, selected_month_date.month)]
        filename = create_pdf(assignments, selected_month_date.strftime('%B %Y'))
        with open(filename, "rb") as f:
            st.download_button(
                "⬇️ Download PDF",
                data=f,
                file_name=f"schedule_{selected_month_date.strftime('%Y_%m')}.pdf"
            )
