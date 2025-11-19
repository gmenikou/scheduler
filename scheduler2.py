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
    current = start_date
    all_schedules = {}
    while current <= end_date:
        year = current.year
        month = current.month
        num_days = calendar.monthrange(year, month)[1]
        month_dates = [datetime.date(year, month, d) for d in range(1, num_days+1) if datetime.date(year, month, d) >= start_date and datetime.date(year, month, d) <= end_date]
        schedule = generate_schedule(initial_week, month_dates)
        all_schedules[(year, month)] = schedule
        if month == 12:
            current = datetime.date(year+1, 1, 1)
        else:
            current = datetime.date(year, month+1, 1)
    return all_schedules

# -------------------------------
# Doctor color generation
# -------------------------------
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
# PDF exporter
# -------------------------------
class CalendarPDF(FPDF):
    def header(self):
        pass

    def add_calendar_page(self, year, month, schedule, edits=None):
        if edits is None:
            edits = {}
        self.add_page()
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, f"{calendar.month_name[month]} {year}", 0, 1, "C")
        self.ln(4)

        col_width = 26
        row_height = 16
        left_margin = (self.w - (col_width*7)) / 2
        self.set_x(left_margin)

        self.set_font("Arial", "B", 10)
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            self.cell(col_width, row_height, d, 1, 0, "C")
        self.ln(row_height)
        self.set_x(left_margin)

        self.set_font("Arial", "", 9)
        cal = calendar.Calendar(firstweekday=0)
        for week in cal.monthdatescalendar(year, month):
            for d in week:
                if d.month != month:
                    self.cell(col_width, row_height, "", 1, 0, "C")
                else:
                    doc = edits.get(d, schedule.get(d,""))
                    bg_color = DOCTOR_COLORS.get(doc, "#ffffff") if doc else "#f0f0f0"
                    r = int(bg_color[1:3],16)
                    g = int(bg_color[3:5],16)
                    b = int(bg_color[5:7],16)
                    self.set_fill_color(r,g,b)
                    self.cell(col_width, row_height, f"{d.day}\n{doc}", 1, 0, "C", 1)
            self.ln(row_height)
            self.set_x(left_margin)

def export_calendar_pdf(all_schedules, edits_map):
    pdf = CalendarPDF()
    for (year, month), schedule in all_schedules.items():
        month_edits = edits_map.get((year, month), {})
        pdf.add_calendar_page(year, month, schedule, month_edits)
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# -------------------------------
# Balance calculation
# -------------------------------
def calculate_balance(flat_schedule):
    balance = {doc: {"Fri":0,"Sat":0,"Sun":0} for doc in DOCTORS}
    for d, doc in flat_schedule.items():
        if not doc: 
            continue
        wd = d.weekday()
        if wd==4: balance[doc]["Fri"]+=1
        if wd==5: balance[doc]["Sat"]+=1
        if wd==6: balance[doc]["Sun"]+=1
    return balance

# -------------------------------
# Calendar display
# -------------------------------
def display_month_calendar(year, month, schedule, edits, selected_doctor, dark_mode=False):
    merged = {**schedule, **edits}
    st.markdown(f"### 🗓️ {calendar.month_name[month]} {year}")
    cal = calendar.Calendar(firstweekday=0)
    month_weeks = cal.monthdatescalendar(year, month)

    cols = st.columns(7)
    for i, wd in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
        cols[i].markdown(f"**{wd}**")

    for week in month_weeks:
        cols = st.columns(7)
        for idx,d in enumerate(week):
            c = cols[idx]
            if d.month != month:
                c.markdown("<div style='height:70px;background:#f0f0f0'></div>", unsafe_allow_html=True)
                continue
            doc = merged.get(d,"")
            bg = DOCTOR_COLORS.get(doc,"#ffffff") if doc else "#ffffff"
            text_color = "#000000"
            display_text = f"{d.day}\n{doc}" if doc else f"{d.day}"
            html = f"""
            <div style="
                background:{bg};
                color:{text_color};
                border-radius:6px;
                border:1px solid #ccc;
                min-height:70px;
                display:flex;
                flex-direction:column;
                justify-content:center;
                align-items:center;
                white-space:pre-wrap;
            ">
                {display_text}
            </div>
            """
            c.write(html, unsafe_allow_html=True)

            c1, c2 = c.columns([1,1])
            assign_key = f"assign_{year}_{month}_{d.day}"
            clear_key = f"clear_{year}_{month}_{d.day}"
            if c1.button("Assign", key=assign_key):
                if selected_doctor:
                    st.session_state.edits[d] = selected_doctor
                    st.experimental_rerun()
                else:
                    st.warning("Select a doctor first.")
            if c2.button("Clear", key=clear_key):
                st.session_state.edits[d] = ""
                st.experimental_rerun()

# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron")

st.title("📅 Programma Giatron – Calendar View")

if "initial_week" not in st.session_state:
    st.session_state.initial_week = load_initial_week()
if "edits" not in st.session_state:
    st.session_state.edits = {}
if "generated_schedule" not in st.session_state:
    st.session_state.generated_schedule = {}

# Reset
col1, col2 = st.columns([1,1])
with col1:
    if st.button("🔄 Reset All"):
        st.session_state.clear()
        if os.path.exists(INIT_FILE):
            os.remove(INIT_FILE)
        st.experimental_rerun()

# Step 1: initial week selection
st.subheader("1️⃣ Select initial week")
selected_date = st.date_input("Choose a date:", datetime.date.today())
week_dates = get_week_dates(selected_date)
cols = st.columns(7)
for i, d in enumerate(week_dates):
    cols[i].write(f"**{d.strftime('%a %d/%m/%Y')}**")

# Step 2: Assign initial week
st.subheader("2️⃣ Assign doctors for first week")
if st.session_state.initial_week is None:
    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            doc = st.selectbox(d.strftime("%a\n%d/%m"), DOCTORS, key=f"init_{d}")
            initial_week[d] = doc
    if st.button("💾 Save initial week"):
        st.session_state.initial_week = initial_week
        save_initial_week(initial_week)
        st.experimental_rerun()
else:
    st.info("Initial week already saved.")
    for d in sorted(st.session_state.initial_week.keys()):
        st.write(f"{d.strftime('%d/%m/%Y')} → {st.session_state.initial_week[d]}")

# Step 3: Generate schedule
st.subheader("3️⃣ Generate schedule")
start_date = st.date_input("Start date", datetime.date.today())
end_date = st.date_input("End date", datetime.date.today() + datetime.timedelta(days=30))
if st.button("Generate Schedule"):
    st.session_state.generated_schedule = generate_schedule_for_range(st.session_state.initial_week, start_date, end_date)
    st.experimental_rerun()

# Display calendar + balance
if st.session_state.generated_schedule:
    st.subheader("📊 Balance (Fri/Sat/Sun per doctor)")
    flat_schedule = {d:doc for sched in st.session_state.generated_schedule.values() for d,doc in sched.items()}
    balance = calculate_balance(flat_schedule)
    balance_table = "| Doctor | Fri | Sat | Sun |\n|---|---|---|---|\n"
    for doc in DOCTORS:
        balance_table += f"| {doc} | {balance[doc]['Fri']} | {balance[doc]['Sat']} | {balance[doc]['Sun']} |\n"
    st.markdown(balance_table)

    selected_doctor = st.selectbox("Select doctor to assign:", [""] + DOCTORS, index=0)

    for (y,m), sched in sorted(st.session_state.generated_schedule.items()):
        month_edits = {d:v for d,v in st.session_state.edits.items() if d in sched}
        display_month_calendar(y, m, sched, month_edits, selected_doctor)

    # PDF export
    if st.button("Export calendar PDF"):
        edits_map = {}
        for d,doc in st.session_state.edits.items():
            key = (d.year, d.month)
            edits_map.setdefault(key,{})[d] = doc
        buf = export_calendar_pdf(st.session_state.generated_schedule, edits_map)
        st.download_button("⬇️ Download PDF", data=buf, file_name="calendar.pdf")
