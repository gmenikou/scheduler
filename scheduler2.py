# app.py
import streamlit as st
import datetime
import calendar
from fpdf import FPDF
import json
import os
import colorsys
import io

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
        json.dump(serializable, f, ensure_ascii=False, sort_keys=True)

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

    current = initial_monday
    weeks = []
    while current <= max(all_dates):
        week_block = [current + datetime.timedelta(days=i) for i in range(7)]
        weeks.append(week_block)
        current += datetime.timedelta(days=7)

    week_counter = 1
    for week_block in weeks:
        if any(d in initial_week for d in week_block):
            for d in week_block:
                if d in initial_week:
                    schedule[d] = initial_week[d]
        else:
            rotated_week = rotate_week_list(week_list, -2 * week_counter)
            for idx, d in enumerate(week_block):
                if d in all_dates:
                    schedule[d] = rotated_week[idx % 7]
            week_counter += 1

    schedule = {d: doc for d, doc in schedule.items() if d >= initial_monday}
    return schedule

def generate_schedule_for_range(initial_week, start_date, end_date):
    num_days = (end_date - start_date).days + 1
    all_dates = [start_date + datetime.timedelta(days=i) for i in range(num_days)]
    return generate_schedule(initial_week, all_dates)

def generate_doctor_colors(doctor_list):
    colors = {}
    n = max(1, len(doctor_list))
    for i, doc in enumerate(doctor_list):
        hue = (i / n)
        r, g, b = colorsys.hsv_to_rgb(hue, 0.35, 0.95)
        colors[doc] = '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))
    return colors

DOCTOR_COLORS = generate_doctor_colors(DOCTORS)

# -------------------------------
# PDF Export
# -------------------------------
class CalendarPDF(FPDF):
    def header(self):
        pass

    def add_calendar_page(self, title, schedule, edits=None):
        if edits is None:
            edits = {}
        self.add_page()
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, title, 0, 1, "C")
        self.ln(4)

        col_w, row_h = 26, 16
        left_margin = (self.w - (col_w * 7)) / 2
        self.set_x(left_margin)

        self.set_font("Arial", "B", 10)
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            self.cell(col_w, row_h, d, 1, 0, "C")
        self.ln(row_h)
        self.set_x(left_margin)

        cal = calendar.Calendar(firstweekday=0)
        for week in cal.monthdatescalendar(schedule["month"], schedule["month"]):
            for d in week:
                if d.month != schedule["month"]:
                    self.cell(col_w, row_h, "", 1, 0, "C")
                else:
                    doc = edits.get(d, schedule["dates"].get(d, ""))
                    bg = DOCTOR_COLORS.get(doc, "#ffffff") if doc else "#ffffff"
                    r = int(bg[1:3], 16); g = int(bg[3:5],16); b=int(bg[5:7],16)
                    self.set_fill_color(r,g,b)
                    self.cell(col_w, row_h, f"{d.day}\n{doc}", 1, 0, "C", fill=True)
            self.ln(row_h)
            self.set_x(left_margin)

def export_calendar_pdf(sched_dict, edits_map):
    pdf = CalendarPDF()
    for title, schedule_data in sched_dict.items():
        pdf.add_calendar_page(title, schedule_data, edits_map.get(title, {}))
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# -------------------------------
# Balance Table
# -------------------------------
def calculate_balance(schedule):
    balance = {doc: {"Fri":0,"Sat":0,"Sun":0} for doc in DOCTORS}
    for d, doc in schedule.items():
        if doc in DOCTORS:
            weekday = d.strftime("%a")
            if weekday in ["Fri","Sat","Sun"]:
                balance[doc][weekday] += 1
    return balance

def display_balance_table(balance):
    st.write("### 📊 Weekend Balance per Doctor")
    table_html = "<table style='border-collapse: collapse; width: 100%;'>"
    table_html += "<tr><th>Doctor</th><th>Fri</th><th>Sat</th><th>Sun</th></tr>"
    for doc, counts in balance.items():
        color = DOCTOR_COLORS.get(doc, "#ffffff")
        table_html += f"<tr style='background:{color};text-align:center'><td>{doc}</td>"
        for day in ["Fri","Sat","Sun"]:
            table_html += f"<td>{counts[day]}</td>"
        table_html += "</tr>"
    table_html += "</table>"
    st.markdown(table_html, unsafe_allow_html=True)

# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron")

st.title("📅 Programma Giatron – Calendar View")

if "initial_week" not in st.session_state:
    st.session_state.initial_week = load_initial_week()
if "start_date" not in st.session_state:
    st.session_state.start_date = None
if "edits" not in st.session_state:
    st.session_state.edits = {}
if "generated_schedule" not in st.session_state:
    st.session_state.generated_schedule = {}

# Reset
if st.button("🔄 Reset All"):
    st.session_state.clear()
    if os.path.exists(INIT_FILE):
        os.remove(INIT_FILE)
    st.success("Reset done. Reload the page.")

# Left panel: Balance table
left_col, right_col = st.columns([1,3])
with left_col:
    if st.session_state.generated_schedule:
        flat_sched = {}
        for m in st.session_state.generated_schedule.values():
            for d,doc in m.items():
                flat_sched[d] = doc
        balance = calculate_balance(flat_sched)
        display_balance_table(balance)

# Right panel: Calendar view and controls
with right_col:
    # Step 1: Select initial week
    st.subheader("1️⃣ Select initial week date")
    selected_date = st.date_input("Choose a date:", datetime.date.today())
    week_dates = get_week_dates(selected_date)
    st.write("Week:")
    st.write(", ".join([d.strftime("%a %d/%m") for d in week_dates]))

    # Step 2: Assign doctors for initial week
    st.subheader("2️⃣ Assign doctors for first week")
    if not st.session_state.initial_week:
        initial_week = {}
        cols = st.columns(7)
        for i, d in enumerate(week_dates):
            with cols[i]:
                doc = st.selectbox(d.strftime("%a %d/%m"), DOCTORS, key=f"manual_{d}")
                initial_week[d] = doc
        if st.button("💾 Save initial week"):
            st.session_state.initial_week = initial_week
            st.session_state.start_date = selected_date
            save_initial_week(initial_week)
            st.success("Initial week saved!")
    else:
        st.info("Initial week already saved.")

    # Step 3: Generate schedule for date range
    st.subheader("3️⃣ Generate schedule")
    start_range = st.date_input("Start date for program:", datetime.date.today())
    end_range = st.date_input("End date for program:", datetime.date.today() + datetime.timedelta(days=30))
    selected_doctor = st.selectbox("Select doctor to assign:", [""]+DOCTORS)

    if st.button("Generate Schedule"):
        sched = generate_schedule_for_range(st.session_state.initial_week, start_range, end_range)
        # store as {(title, schedule dict)}
        st.session_state.generated_schedule = {"Programma": sched}
        st.success("Schedule generated!")

    # Calendar view
    for title, schedule in st.session_state.generated_schedule.items():
        st.markdown(f"### {title}")
        # display month by month in chronological order
        dates_sorted = sorted(schedule.keys())
        months = {}
        for d in dates_sorted:
            months.setdefault((d.year,d.month),{})[d]=schedule[d]

        for (y,m), month_sched in sorted(months.items()):
            st.markdown(f"#### {calendar.month_name[m]} {y}")
            cal = calendar.Calendar(firstweekday=0)
            month_weeks = cal.monthdatescalendar(y,m)
            for week in month_weeks:
                cols = st.columns(7)
                for idx,d in enumerate(week):
                    c = cols[idx]
                    doc = month_sched.get(d,"") if d.month==m else ""
                    bg = DOCTOR_COLORS.get(doc,"#ffffff") if doc else "#f0f0f0"
                    c.markdown(f"<div style='background:{bg};min-height:60px;padding:4px;border-radius:6px;text-align:center;'>{d.day}<br>{doc}</div>",unsafe_allow_html=True)
                    c1,c2 = c.columns([1,1])
                    if c1.button("Assign",key=f"assign_{d}"):
                        if selected_doctor:
                            st.session_state.edits[d]=selected_doctor
                            st.experimental_rerun()
                    if c2.button("Clear",key=f"clear_{d}"):
                        st.session_state.edits[d]=""
                        st.experimental_rerun()

    # PDF Export
    if st.session_state.generated_schedule:
        if st.button("Export PDF (with colors)"):
            buf = export_calendar_pdf(st.session_state.generated_schedule, {title:st.session_state.edits for title in st.session_state.generated_schedule})
            st.download_button("⬇️ Download PDF", data=buf, file_name="calendar.pdf")
