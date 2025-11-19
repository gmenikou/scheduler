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
    all_dates = [start_date + datetime.timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    return generate_schedule(initial_week, all_dates)

# -------------------------------
# Doctor Colors
# -------------------------------
def generate_doctor_colors(doctor_list):
    colors = {}
    n = max(1, len(doctor_list))
    for i, doc in enumerate(doctor_list):
        hue = i / n
        r, g, b = colorsys.hsv_to_rgb(hue, 0.35, 0.95)
        colors[doc] = '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))
    return colors

DOCTOR_COLORS = generate_doctor_colors(DOCTORS)

# -------------------------------
# Balance table
# -------------------------------
def calculate_balance(schedule):
    balance = {doc: {"Fri":0, "Sat":0, "Sun":0} for doc in DOCTORS}
    for d, doc in schedule.items():
        if doc in balance:
            wd = d.weekday()
            if wd == 4: balance[doc]["Fri"] += 1
            elif wd == 5: balance[doc]["Sat"] += 1
            elif wd == 6: balance[doc]["Sun"] += 1
    return balance

# -------------------------------
# PDF Export
# -------------------------------
class CalendarPDF(FPDF):
    def header(self):
        pass

    def add_calendar_page(self, year, month, schedule):
        self.add_page()
        try:
            self.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            self.set_font("DejaVu", "B", 14)
        except:
            self.set_font("Arial", "B", 14)
        self.cell(0, 10, f"{calendar.month_name[month]} {year}", 0, 1, "C")
        self.ln(4)
        col_width = 26
        row_height = 16
        left_margin = (self.w - (col_width * 7)) / 2
        self.set_x(left_margin)
        self.set_font("", "", 10)
        # Weekday header
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            self.cell(col_width, row_height, d, 1, 0, "C")
        self.ln(row_height)
        self.set_x(left_margin)
        cal = calendar.Calendar(firstweekday=0)
        for week in cal.monthdatescalendar(year, month):
            for d in week:
                if d.month != month:
                    self.cell(col_width, row_height, "", 1, 0, "C")
                else:
                    doc = schedule.get(d, "")
                    text = f"{d.day}\n{doc}"
                    if doc in DOCTOR_COLORS:
                        hexcol = DOCTOR_COLORS[doc]
                        r=int(hexcol[1:3],16)
                        g=int(hexcol[3:5],16)
                        b=int(hexcol[5:7],16)
                        self.set_fill_color(r,g,b)
                    else:
                        self.set_fill_color(224,224,224)
                    self.multi_cell(col_width,row_height,text,1,'C',fill=True)
            self.ln(row_height)
            self.set_x(left_margin)

def export_calendar_pdf(schedule):
    pdf = CalendarPDF()
    months = sorted(set((d.year,d.month) for d in schedule))
    for year, month in months:
        month_sched = {d:doc for d,doc in schedule.items() if d.year==year and d.month==month}
        pdf.add_calendar_page(year, month, month_sched)
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# -------------------------------
# Calendar Display
# -------------------------------
def display_calendar(schedule, edits, selected_doctor, dark_mode):
    months = sorted(set((d.year,d.month) for d in schedule))
    for year, month in months:
        st.markdown(f"### {calendar.month_name[month]} {year}")
        cal = calendar.Calendar(firstweekday=0)
        month_weeks = cal.monthdatescalendar(year, month)
        # Weekday header
        cols = st.columns(7)
        for i, dname in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
            cols[i].markdown(f"**{dname}**")
        # Grid
        for week in month_weeks:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day.month != month:
                        st.markdown("<div style='height:70px;background:#f0f0f0'></div>",unsafe_allow_html=True)
                        continue
                    doc = edits.get(day, schedule.get(day,""))
                    bg = DOCTOR_COLORS.get(doc,"#ffffff") if doc else "#ffffff"
                    text_color="#000000"
                    try:
                        r=int(bg[1:3],16); g=int(bg[3:5],16); b=int(bg[5:7],16)
                        lum=0.2126*r+0.7152*g+0.0722*b
                        if dark_mode and lum<140: text_color="#ffffff"
                    except: text_color="#ffffff"
                    st.markdown(f"""
                    <div style='
                    border-radius:8px; padding:6px; min-height:70px; display:flex; flex-direction:column; justify-content:space-between; align-items:center;
                    background:{bg}; color:{text_color}; border:1px solid #ccc'>
                    <div style='font-weight:700'>{day.day}</div>
                    <div style='font-size:12px;white-space:pre-wrap'>{doc}</div>
                    </div>
                    """,unsafe_allow_html=True)
                    btn1, btn2 = st.columns([1,1])
                    if btn1.button("Assign", key=f"assign_{day}"):
                        if selected_doctor: edits[day]=selected_doctor; st.experimental_rerun()
                    if btn2.button("Clear", key=f"clear_{day}"):
                        edits[day] = ""; st.experimental_rerun()
        st.markdown("<br>",unsafe_allow_html=True)

# -------------------------------
# Streamlit UI
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron Calendar")
st.title("📅 Programma Giatron – Calendar View")

if "initial_week" not in st.session_state: st.session_state.initial_week = load_initial_week()
if "start_date" not in st.session_state: st.session_state.start_date = None
if "edits" not in st.session_state: st.session_state.edits = {}
if "generated_schedule" not in st.session_state: st.session_state.generated_schedule = {}
if "dark_mode" not in st.session_state: st.session_state.dark_mode = False

# Top panel
col1, col2 = st.columns([1,2])
with col1:
    if st.button("🔄 Reset All"):
        st.session_state.clear()
        if os.path.exists(INIT_FILE): os.remove(INIT_FILE)
        st.success("Session cleared")
        st.experimental_rerun()
    st.checkbox("🌙 Dark Mode", value=st.session_state.dark_mode, key="dark_mode")

# Left panel balance table
col_left, col_right = st.columns([1,3])
with col_left:
    if st.session_state.generated_schedule:
        flat_sched = {d:doc for s in st.session_state.generated_schedule.values() for d,doc in s.items()}
        balance = calculate_balance(flat_sched)
        st.subheader("📝 Balance Table (Fri/Sat/Sun)")
        for doc in DOCTORS:
            st.markdown(f"<div style='background:{DOCTOR_COLORS[doc]}; padding:4px; border-radius:4px'><b>{doc}</b>: Fri {balance[doc]['Fri']}, Sat {balance[doc]['Sat']}, Sun {balance[doc]['Sun']}</div>", unsafe_allow_html=True)

with col_right:
    # Step1 initial week
    st.subheader("1️⃣ Select initial week date")
    sel_date = st.date_input("Choose a date:", datetime.date.today() if st.session_state.start_date is None else st.session_state.start_date)
    week_dates = get_week_dates(sel_date)
    st.write("Week:", ", ".join([d.strftime("%a %d/%m/%Y") for d in week_dates]))

    # Step2 assign doctors first week
    st.subheader("2️⃣ Assign doctors for first week")
    if st.session_state.initial_week is None:
        init_week={}
        cols = st.columns(7)
        for i,d in enumerate(week_dates):
            with cols[i]:
                init_week[d]=st.selectbox(d.strftime("%a\n%d/%m"), DOCTORS, key=f"manual_{d}")
        if st.button("💾 Save initial week"):
            st.session_state.initial_week=init_week
            st.session_state.start_date=sel_date
            save_initial_week(init_week)
            st.success("Initial week saved")
    else:
        st.info("Initial week saved. Use Reset to change.")
        for d in sorted(st.session_state.initial_week.keys()):
            st.write(f"{d.strftime('%d/%m/%Y')} → {st.session_state.initial_week[d]}")

    # Step3 generate schedule for range
    st.subheader("3️⃣ Generate schedule for date range")
    start_gen = st.date_input("Start date", datetime.date.today())
    end_gen = st.date_input("End date", datetime.date.today()+datetime.timedelta(days=30))
    if st.button("Generate Schedule"):
        sched = generate_schedule_for_range(st.session_state.initial_week, start_gen, end_gen)
        # split by month
        month_dict={}
        for d,doc in sched.items():
            month_dict.setdefault((d.year,d.month),{})[d]=doc
        st.session_state.generated_schedule=month_dict
        st.session_state.edits={}
        st.success("Schedule generated")

    # Calendar view
    if st.session_state.generated_schedule:
        selected_doc = st.selectbox("Select doctor to assign:", [""]+DOCTORS, index=0)
        edits = st.session_state.edits
        # merge all months into single schedule for display
        merged_sched={d:doc for m,s in st.session_state.generated_schedule.items() for d,doc in s.items()}
        display_calendar(merged_sched, edits, selected_doc if selected_doc else None, st.session_state.dark_mode)

        if st.button("Export PDF"):
            merged_sched={d:edits.get(d,doc) for d,doc in merged_sched.items()}
            buf = export_calendar_pdf(merged_sched)
            st.download_button("⬇️ Download PDF", data=buf, file_name="schedule.pdf")
