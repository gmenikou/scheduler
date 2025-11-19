# app.py
import streamlit as st
import datetime
import calendar
import json
import os
import colorsys
import io
from fpdf import FPDF

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
    delta = end_date - start_date
    all_dates = [start_date + datetime.timedelta(days=i) for i in range(delta.days + 1)]
    return generate_schedule(initial_week, all_dates)

def generate_doctor_colors(doctor_list):
    colors = {}
    n = max(1, len(doctor_list))
    for i, doc in enumerate(doctor_list):
        hue = (i / n)
        r, g, b = colorsys.hsv_to_rgb(hue, 0.35, 0.95)
        hexcol = '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))
        colors[doc] = hexcol
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

        col_width = 26
        row_height = 16
        left_margin = (self.w - (col_width*7))/2
        self.set_x(left_margin)

        self.set_font("Arial", "B", 10)
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            self.cell(col_width, row_height, d, 1, 0, "C")
        self.ln(row_height)
        self.set_x(left_margin)

        self.set_font("Arial", "", 9)
        cal = calendar.Calendar(firstweekday=0)
        year, month = list(schedule.keys())[0].year, list(schedule.keys())[0].month
        for week in cal.monthdatescalendar(year, month):
            for d in week:
                if d.month != month:
                    self.cell(col_width, row_height, "", 1, 0, "C")
                else:
                    doc = edits.get(d, schedule.get(d,""))
                    bg = DOCTOR_COLORS.get(doc, "#ffffff") if doc else "#ffffff"
                    text = f"{d.day} {doc}"
                    self.set_fill_color(int(bg[1:3],16), int(bg[3:5],16), int(bg[5:7],16))
                    self.cell(col_width, row_height, text, 1, 0, "C", 1)
            self.ln(row_height)
            self.set_x(left_margin)

def export_calendar_pdf(schedule, edits):
    pdf = CalendarPDF()
    # Flatten months
    flat_schedule = schedule
    title = "Programma Giatron"
    pdf.add_calendar_page(title, flat_schedule, edits)
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron Calendar")
st.title("📅 Programma Giatron – Calendar View")

if "initial_week" not in st.session_state:
    st.session_state.initial_week = load_initial_week()
if "start_date" not in st.session_state:
    st.session_state.start_date = None
if "edits" not in st.session_state:
    st.session_state.edits = {}

# Reset & Dark mode
col1, col2, col3 = st.columns([1,2,1])
with col1:
    if st.button("🔄 Reset All"):
        st.session_state.clear()
        if os.path.exists(INIT_FILE):
            os.remove(INIT_FILE)
        st.success("Session reset.")
        st.experimental_rerun()

with col3:
    st.session_state.dark_mode = st.checkbox("🌙 Dark Mode", value=st.session_state.get("dark_mode", False))

# Step 1: initial week
st.subheader("1️⃣ Select initial week")
selected_date = st.date_input("Choose a date:", datetime.date.today())
week_dates = get_week_dates(selected_date)
colsw = st.columns(7)
for i,d in enumerate(week_dates):
    colsw[i].write(f"**{d.strftime('%a %d/%m/%Y')}**")

st.subheader("2️⃣ Assign doctors for first week")
if st.session_state.initial_week is None:
    initial_week = {}
    cols = st.columns(7)
    for i,d in enumerate(week_dates):
        with cols[i]:
            doc = st.selectbox(d.strftime("%a\n%d/%m"), DOCTORS, key=f"manual_{d}")
            initial_week[d] = doc
    if st.button("💾 Save initial week"):
        st.session_state.initial_week = initial_week
        st.session_state.start_date = selected_date
        save_initial_week(initial_week)
        st.success("Initial week saved!")
else:
    st.write("Initial week already saved:")
    for d in sorted(st.session_state.initial_week.keys()):
        st.write(f"{d.strftime('%d/%m/%Y')} → {st.session_state.initial_week[d]}")

# Step 3: generate schedule
st.subheader("3️⃣ Generate schedule")
start_date = st.date_input("Start date", datetime.date.today())
end_date = st.date_input("End date", datetime.date.today() + datetime.timedelta(days=30))
if st.button("Generate Schedule"):
    st.session_state.generated_schedule = generate_schedule_for_range(st.session_state.initial_week, start_date, end_date)
    st.session_state.edits = {}
    st.success("Schedule generated.")

# Display calendar + balance
if "generated_schedule" in st.session_state:
    flat_schedule = st.session_state.generated_schedule

    # Calculate balance per doctor for Fri, Sat, Sun
    balance = {doc: {"Fri":0,"Sat":0,"Sun":0} for doc in DOCTORS}
    for d,doc in flat_schedule.items():
        if doc:
            wd = d.strftime("%a")
            if wd in ["Fri","Sat","Sun"]:
                balance[doc][wd]+=1

    # Layout: left = balance, right = calendar
    left_col, right_col = st.columns([1,3])
    with left_col:
        st.subheader("📊 Balance (Fri/Sat/Sun per doctor)")
        table_md = "| Doctor | Fri | Sat | Sun |\n|---|---|---|---|\n"
        for doc in DOCTORS:
            color = DOCTOR_COLORS.get(doc,"#ffffff")
            table_md += f"| <span style='background:{color}'>{doc}</span> | {balance[doc]['Fri']} | {balance[doc]['Sat']} | {balance[doc]['Sun']} |\n"
        st.markdown(table_md, unsafe_allow_html=True)

    with right_col:
        # Display month-by-month
        months = {}
        for d,doc in flat_schedule.items():
            key = (d.year,d.month)
            months.setdefault(key,{})[d]=doc
        for (y,m), month_sched in sorted(months.items()):
            st.markdown(f"### {calendar.month_name[m]} {y}")
            cal = calendar.Calendar(firstweekday=0)
            month_weeks = cal.monthdatescalendar(y,m)
            for week in month_weeks:
                cols = st.columns(7)
                for idx,d in enumerate(week):
                    c = cols[idx]
                    doc = month_sched.get(d,"") if d.month==m else ""
                    bg = DOCTOR_COLORS.get(doc,"#ffffff") if doc else "#f0f0f0"
                    c.markdown(f"<div style='background:{bg};border:1px solid #ccc;padding:8px;height:70px;text-align:center'>{d.day}<br>{doc}</div>",unsafe_allow_html=True)
                    c1,c2 = c.columns([1,1])
                    if c1.button("Assign", key=f"assign_{d}"):
                        st.session_state.edits[d]=doc
                        st.experimental_rerun()
                    if c2.button("Clear", key=f"clear_{d}"):
                        st.session_state.edits[d]=""
                        st.experimental_rerun()

    st.markdown("---")
    if st.button("Export PDF (with colors)"):
        buf = export_calendar_pdf(flat_schedule, st.session_state.edits)
        st.download_button("⬇️ Download PDF", data=buf, file_name="calendar.pdf")
