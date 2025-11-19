# app.py
import streamlit as st
import datetime
import calendar
from fpdf import FPDF
import json
import os
import colorsys
import io
from io import BytesIO

# -------------------------------
# Constants
# -------------------------------
DOCTORS = ["Elena", "Eva", "Maria", "Athina", "Alexandros", "Elia", "Christina"]
INIT_FILE = "initial_week.json"

# -------------------------------
# Scheduling helpers
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

# -------------------------------
# Doctor color generator
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
    def header(self): pass
    def add_calendar_page(self, year, month, schedule, edits=None):
        if edits is None:
            edits = {}
        self.add_page()
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, f"{calendar.month_name[month]} {year}", 0, 1, "C")
        self.ln(4)

        col_width = 26
        row_height = 16
        left_margin = (self.w - (col_width * 7)) / 2
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
                    doc = edits.get(d, schedule.get(d, ""))
                    text = f"{d.day} {doc}"
                    self.cell(col_width, row_height, text, 1, 0, "C")
            self.ln(row_height)
            self.set_x(left_margin)

def export_calendar_pdf(all_schedules, edits_map):
    pdf = CalendarPDF()
    for (year, month), schedule in sorted(all_schedules.items(), key=lambda x: (x[0][0], x[0][1])):
        pdf.add_calendar_page(year, month, schedule, edits=edits_map.get((year, month), {}))
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    buf = BytesIO(pdf_bytes)
    return buf

# -------------------------------
# Calendar display helpers
# -------------------------------
def apply_edits_to_schedule(schedule, edits):
    merged = dict(schedule)
    merged.update(edits)
    return merged

def display_month_calendar_grid(year, month, schedule, edits, selected_doctor=None, dark_mode=False):
    merged = apply_edits_to_schedule(schedule, edits)
    st.markdown(f"### 🗓️ {calendar.month_name[month]} {year}")

    cal = calendar.Calendar(firstweekday=0)
    month_weeks = cal.monthdatescalendar(year, month)

    # Weekday header
    cols = st.columns(7)
    for i, day in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
        cols[i].markdown(f"**{day}**")

    # Render weeks
    for week in month_weeks:
        cols = st.columns(7)
        for i, d in enumerate(week):
            doc = merged.get(d, "")
            is_edited = d in edits and edits[d] != schedule.get(d, "")
            bg = DOCTOR_COLORS.get(doc, "#e0e0e0") if doc else "#ffffff"
            border = "#ff0000" if is_edited else "#ccc"
            display_doc = f"{doc} ⚡" if is_edited else doc

            html = f"""
            <div style="
                border:2px solid {border};
                border-radius:6px;
                min-height:70px;
                padding:4px;
                text-align:center;
                background:{bg};
                color:#000000;
            ">
                <strong>{d.day}</strong><br>
                {display_doc}
            </div>
            """
            cols[i].write(html, unsafe_allow_html=True)

# -------------------------------
# Streamlit UI
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron - Calendar Grid")
st.title("📅 Programma Giatron – Backwards Rotation (Calendar Grid)")

# Session state
if "initial_week" not in st.session_state:
    st.session_state.initial_week = load_initial_week()
if "start_date" not in st.session_state:
    st.session_state.start_date = None
if "edits" not in st.session_state:
    st.session_state.edits = {}
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# Reset & dark mode
col1, _, col3 = st.columns([1,2,1])
with col1:
    if st.button("🔄 Reset All"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        if os.path.exists(INIT_FILE):
            os.remove(INIT_FILE)
        st.rerun()
with col3:
    st.session_state.dark_mode = st.checkbox("🌙 Dark Mode", value=st.session_state.dark_mode)

# Dark mode CSS
if st.session_state.dark_mode:
    st.markdown("""
    <style>
    .stApp {background-color: #0f1115; color: #e6eef8;}
    .stButton>button {background-color:#2b2f36;color:#e6eef8;}
    </style>
    """, unsafe_allow_html=True)

# Step 1: initial week
st.subheader("1️⃣ Select a date in the initial week")
selected_date = st.session_state.start_date or st.date_input("Choose a date:", datetime.date.today())
week_dates = get_week_dates(selected_date)
cols = st.columns(7)
for i, d in enumerate(week_dates):
    cols[i].write(f"**{d.strftime('%a %d/%m/%Y')}**")

# Step 2: assign doctors to initial week
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

# Step 3: generate schedule
if st.session_state.initial_week:
    st.subheader("3️⃣ Generate schedule for forthcoming months")
    today = datetime.date.today()
    months_options = [(today + datetime.timedelta(days=30*i)).replace(day=1) for i in range(12)]
    months_display = [d.strftime("%B %Y") for d in months_options]
    selected_month_index = st.selectbox("Choose start month:", list(range(12)),
                                        format_func=lambda x: months_display[x])
    selected_month_date = months_options[selected_month_index]
    num_months = st.number_input("Number of months to generate:", 1, 12, 1, 1)

    if st.button("Generate Schedule"):
        multi_schedule = generate_schedule_for_months(st.session_state.initial_week,
                                                      selected_month_date, num_months)
        st.session_state.generated_schedule = multi_schedule
        st.success("Schedule generated. Scroll down to view in calendar grid.")

# Calendar display
if "generated_schedule" in st.session_state:
    st.subheader("📋 Calendar Grid")
    ctrl_col, preview_col = st.columns([1,3])
    with ctrl_col:
        selected_doctor = st.selectbox("Select doctor to assign:", [""] + DOCTORS, index=0)
        if st.button("Clear all edits"):
            st.session_state.edits = {}
            st.rerun()
        if st.button("Export PDF"):
            edits_map = {}
            for d, doc in st.session_state.edits.items():
                key = (d.year, d.month)
                edits_map.setdefault(key, {})[d] = doc
            buf = export_calendar_pdf(st.session_state.generated_schedule, edits_map)
            st.download_button("⬇️ Download Calendar PDF", data=buf, file_name="calendar.pdf")

    with preview_col:
        months = sorted(st.session_state.generated_schedule.items(), key=lambda x: (x[0][0], x[0][1]))
        col_blocks = [st.container(), st.container()]
        for idx, ((year, month), schedule) in enumerate(months):
            target_col = col_blocks[idx % 2]
            month_edits = {d: doc for d, doc in st.session_state.edits.items() if d.year==year and d.month==month}
            with target_col:
                display_month_calendar_grid(year, month, schedule, month_edits, selected_doctor, st.session_state.dark_mode)

    if st.session_state.edits:
        st.subheader("📝 Current edits")
        for d in sorted(st.session_state.edits.keys()):
            val = st.session_state.edits[d]
            st.write(f"{d.strftime('%d/%m/%Y')} → {val if val else '(cleared)'}")
