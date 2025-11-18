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
# 3. Schedule logic: initial week preserved
# ---------------------------------------------
def full_month_schedule(initial_week, all_dates):
    initial_week_dates = sorted(initial_week.keys())
    initial_week_list = [initial_week[d] for d in initial_week_dates]
    initial_monday = initial_week_dates[0]

    schedule = {}
    for d in all_dates:
        delta_days = (d - initial_monday).days
        week_diff = delta_days // 7
        offset = (abs(week_diff) * 2) % 7

        if week_diff < 0:
            rotated = initial_week_list[offset:] + initial_week_list[:offset]
        elif week_diff > 0:
            rotated = initial_week_list[-offset:] + initial_week_list[:-offset]
        else:
            rotated = initial_week_list

        schedule[d] = rotated[d.weekday()]

    return schedule

# ---------------------------------------------
# 4. PDF Export (latin-only)
# ---------------------------------------------
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
            self.cell(60, 8, d.strftime("%d/%m/%Y"), 1, 0, "C")
            self.cell(80, 8, assignments[d], 1, 1, "C")

def create_pdf(assignments, filename="schedule.pdf"):
    pdf = PDF()
    pdf.add_page()
    pdf.create_schedule_table(assignments)
    pdf.output(filename)
    return filename

# ---------------------------------------------
# 5. STREAMLIT APP
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

# Step 2: Assign doctors for the initial week
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

# Display initial week
if st.session_state.initial_week:
    st.write("Your assigned initial week:")
    for d in sorted(st.session_state.initial_week.keys()):
        st.write(d.strftime("%d/%m/%Y"), "→", st.session_state.initial_week[d])

# Step 3 & 4: Generate schedule & PDF only if initial week exists
if st.session_state.initial_week is not None and st.session_state.start_date is not None:
    st.subheader("3️⃣ Generate full schedule")
    year = st.session_state.start_date.year
    month = st.session_state.start_date.month
    num_days = calendar.monthrange(year, month)[1]
    all_dates = [datetime.date(year, month, d) for d in range(1, num_days + 1)]

    schedule = full_month_schedule(st.session_state.initial_week, all_dates)

    # Show schedule
    st.write("### 📋 Month Schedule")
    for d in sorted(schedule.keys()):
        st.write(d.strftime("%d/%m/%Y"), "→", schedule[d])

    # PDF export
    st.subheader("📄 Export PDF")
    if st.button("🖨️ Create PDF"):
        filename = create_pdf(schedule)
        with open(filename, "rb") as f:
            st.download_button("⬇️ Download PDF", data=f, file_name="schedule.pdf")
else:
    st.warning("Please assign and save the initial week first.")
