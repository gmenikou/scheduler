# app.py
import streamlit as st
import datetime
import calendar
from fpdf import FPDF
import json
import os
import colorsys
import io
from collections import defaultdict

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
    current = start_month
    for _ in range(num_months):
        year = current.year
        month = current.month
        num_days = calendar.monthrange(year, month)[1]
        month_dates = [datetime.date(year, month, d) for d in range(1, num_days + 1)]
        schedule = generate_schedule(initial_week, month_dates)
        all_schedules[(year, month)] = schedule
        if month == 12:
            current = datetime.date(year+1, 1, 1)
        else:
            current = datetime.date(year, month+1, 1)
    return all_schedules

# -------------------------------
# Doctor colors
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
# PDF Calendar
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
        left_margin = (self.w - (col_width*7))/2
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
                    bg = DOCTOR_COLORS.get(doc, "#FFFFFF") if doc else "#FFFFFF"
                    # FPDF does not support bg color per cell easily; workaround: set fill color
                    r = int(bg[1:3],16)
                    g = int(bg[3:5],16)
                    b = int(bg[5:7],16)
                    self.set_fill_color(r,g,b)
                    self.cell(col_width, row_height, text, 1, 0, "C", fill=True)
            self.ln(row_height)
            self.set_x(left_margin)

def export_calendar_pdf(all_schedules, edits_map):
    pdf = CalendarPDF()
    for (year, month), schedule in sorted(all_schedules.items()):
        month_edits = edits_map.get((year, month), {})
        pdf.add_calendar_page(year, month, schedule, edits=month_edits)
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron - Calendar Grid")
st.title("📅 Programma Giatron – Backwards Rotation")

# Session state
if "initial_week" not in st.session_state:
    st.session_state.initial_week = load_initial_week()
if "start_date" not in st.session_state:
    st.session_state.start_date = None
if "edits" not in st.session_state:
    st.session_state.edits = {}
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# -------------------------------
# Reset / Dark mode
# -------------------------------
col1, col2, col3 = st.columns([1,2,1])
with col1:
    if st.button("🔄 Reset All", key="reset_all"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        if os.path.exists(INIT_FILE):
            os.remove(INIT_FILE)
        st.rerun()

with col3:
    dark = st.checkbox("🌙 Dark Mode", value=st.session_state.dark_mode, key="dark_mode_checkbox")
    st.session_state.dark_mode = dark

# -------------------------------
# Initial week selection
# -------------------------------
st.subheader("1️⃣ Select a date in the initial week")
if st.session_state.start_date is None:
    selected_date = st.date_input("Choose a date:", datetime.date.today(), key="start_date_input")
else:
    selected_date = st.session_state.start_date

week_dates = get_week_dates(selected_date)
colw = st.columns(7)
for i, d in enumerate(week_dates):
    colw[i].write(f"**{d.strftime('%a %d/%m/%Y')}**")

st.subheader("2️⃣ Assign doctors for the first week")
if st.session_state.initial_week is None:
    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            doc = st.selectbox(d.strftime("%a\n%d/%m"), DOCTORS, key=f"manual_{d}")
            initial_week[d] = doc
    if st.button("💾 Save initial week", key="save_initial_week"):
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

# -------------------------------
# Generate schedule
# -------------------------------
if st.session_state.initial_week and st.session_state.start_date:
    st.subheader("3️⃣ Generate schedule for forthcoming months")
    today = datetime.date.today()
    months_options = [(today + datetime.timedelta(days=30*i)).replace(day=1) for i in range(12)]
    months_display = [d.strftime("%B %Y") for d in months_options]
    selected_month_index = st.selectbox("Choose start month:", list(range(12)),
                                        format_func=lambda x: months_display[x], key="month_start_select")
    selected_month_date = months_options[selected_month_index]
    num_months = st.number_input("Number of months to generate:", min_value=1, max_value=12, value=1, step=1, key="num_months_input")

    if st.button("Generate Schedule", key="generate_schedule_btn"):
        multi_schedule = generate_schedule_for_months(st.session_state.initial_week, selected_month_date, num_months)
        st.session_state.generated_schedule = multi_schedule
        st.session_state.edits = {}
        st.success("Schedule generated. Scroll down to view in calendar grid.")

# -------------------------------
# Calendar display
# -------------------------------
def display_calendar_grid():
    if "generated_schedule" not in st.session_state:
        st.info("Generate a schedule first.")
        return

    st.subheader("📋 Calendar Grid (click cells to Assign / Clear)")

    col_left, col_main = st.columns([1,3])
    with col_left:
        st.write("### Doctor Balance (Fridays/Saturdays/Sundays)")
        balance = defaultdict(lambda: {"Fri":0,"Sat":0,"Sun":0})
        for sched in st.session_state.generated_schedule.values():
            for d, doc in sched.items():
                day = d.strftime("%a")
                if day in ["Fri","Sat","Sun"]:
                    balance[doc][day] += 1
        # Display nice table
        st.table({doc: balance[doc] for doc in DOCTORS})

    with col_main:
        selected_doctor = st.selectbox("Select doctor to assign:", [""] + DOCTORS, index=0, key="assign_selector")
        for (year, month), schedule in sorted(st.session_state.generated_schedule.items()):
            month_edits = {}
            for d, doc in st.session_state.edits.items():
                if isinstance(d, str):
                    d_obj = datetime.datetime.strptime(d,"%Y-%m-%d").date()
                else:
                    d_obj = d
                if d_obj.year==year and d_obj.month==month:
                    month_edits[d_obj]=doc

            st.markdown(f"### {calendar.month_name[month]} {year}")
            cal = calendar.Calendar(firstweekday=0)
            month_weeks = cal.monthdatescalendar(year, month)

            weekday_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
            cols = st.columns(7)
            for i, c in enumerate(cols):
                c.markdown(f"**{weekday_names[i]}**")

            for w_idx, week in enumerate(month_weeks):
                cols = st.columns(7)
                for c_idx, d in enumerate(week):
                    cell_col = cols[c_idx]
                    if d.month != month:
                        cell_col.markdown("<div style='height:70px;background:#f6f6f6;border-radius:6px'></div>", unsafe_allow_html=True)
                        continue
                    doc = month_edits.get(d, schedule.get(d,""))
                    bg = DOCTOR_COLORS.get(doc,"#ffffff") if doc else "#ffffff"
                    text_color = "#000000"
                    if st.session_state.dark_mode:
                        r = int(bg[1:3],16); g=int(bg[3:5],16); b=int(bg[5:7],16)
                        luminance=0.2126*r+0.7152*g+0.0722*b
                        if luminance<140: text_color="#ffffff"
                    display_text = f"{d.day}\n{doc}" if doc else f"{d.day}"
                    key_base = f"cell_{year}_{month}_{d.isoformat()}"
                    html = f"""
                    <div style="
                        border-radius:8px;
                        padding:8px;
                        min-height:70px;
                        display:flex;
                        flex-direction:column;
                        justify-content:space-between;
                        align-items:center;
                        background:{bg};
                        color:{text_color};
                        border:1px solid #ccc;
                    ">{display_text}</div>
                    """
                    cell_col.write(html, unsafe_allow_html=True)
                    btn1, btn2 = cell_col.columns([1,1])
                    if btn1.button("Assign", key=key_base+"_assign"):
                        if selected_doctor:
                            st.session_state.edits[d]=selected_doctor
                            st.experimental_rerun()
                        else:
                            st.warning("Select a doctor first.")
                    if btn2.button("Clear", key=key_base+"_clear"):
                        if d in st.session_state.edits: del st.session_state.edits[d]
                        st.experimental_rerun()

        if st.session_state.edits:
            st.subheader("📝 Current edits")
            for d in sorted(st.session_state.edits.keys()):
                val = st.session_state.edits[d]
                st.write(f"{d.strftime('%d/%m/%Y')} → {val if val else '(cleared)'}")

        if st.button("💾 Export PDF (with colors)", key="export_pdf_btn"):
            edits_map = {}
            for d, doc in st.session_state.edits.items():
                d_obj = d if isinstance(d, datetime.date) else datetime.datetime.strptime(d,"%Y-%m-%d").date()
                edits_map.setdefault((d_obj.year,d_obj.month),{})[d_obj]=doc
            buf = export_calendar_pdf(st.session_state.generated_schedule, edits_map)
            st.download_button("⬇️ Download Calendar PDF", data=buf, file_name="calendar.pdf")

display_calendar_grid()
