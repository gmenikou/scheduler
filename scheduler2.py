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

    def add_calendar_page(self, year, month, schedule, edits=None):
        if edits is None:
            edits = {}
        self.add_page()
        self.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
        self.set_font("DejaVu", "B", 16)
        self.cell(0, 10, f"{calendar.month_name[month]} {year}", 0, 1, "C")
        self.ln(4)

        col_w, row_h = 26, 16
        left_margin = (self.w - col_w * 7) / 2
        self.set_x(left_margin)

        self.set_font("DejaVu", "B", 10)
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            self.cell(col_w, row_h, d, 1, 0, "C")
        self.ln(row_h)
        self.set_x(left_margin)

        self.set_font("DejaVu", "", 9)
        cal = calendar.Calendar(firstweekday=0)
        for week in cal.monthdatescalendar(year, month):
            for d in week:
                if d.month != month:
                    self.set_fill_color(240,240,240)
                    self.cell(col_w,row_h,"",1,0,"C",1)
                else:
                    doc_base = schedule.get(d,"")
                    doc_edit = edits.get(d, doc_base)
                    text = f"{doc_edit}" if doc_edit else ""
                    if d in edits and edits[d]!=doc_base:
                        text += " ✎"
                    hexcol = DOCTOR_COLORS.get(doc_edit,"#ffffff")
                    r = int(hexcol[1:3],16)
                    g = int(hexcol[3:5],16)
                    b = int(hexcol[5:7],16)
                    self.set_fill_color(r,g,b)
                    self.multi_cell(col_w,row_h/2,f"{d.day}\n{text}",1,"C",fill=True, ln=3)
            self.ln(row_h)
            self.set_x(left_margin)

def export_calendar_pdf(all_schedules, edits_map):
    pdf = CalendarPDF()
    for (year, month), schedule in sorted(all_schedules.items()):
        month_edits = edits_map.get((year, month), {})
        pdf.add_calendar_page(year, month, schedule, month_edits)
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# -------------------------------
# Balance Table
# -------------------------------
def calculate_balance(flat_schedule):
    balance = {doc: {"Fri":0,"Sat":0,"Sun":0} for doc in DOCTORS}
    for d, doc in flat_schedule.items():
        if doc not in DOCTORS:
            continue
        weekday = d.weekday()
        if weekday==4: balance[doc]["Fri"]+=1
        elif weekday==5: balance[doc]["Sat"]+=1
        elif weekday==6: balance[doc]["Sun"]+=1
    return balance

# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron")

st.title("📅 Programma Giatron – Backwards Rotation (Calendar Grid)")

if "initial_week" not in st.session_state: st.session_state.initial_week = load_initial_week()
if "start_date" not in st.session_state: st.session_state.start_date = None
if "edits" not in st.session_state: st.session_state.edits = {}
if "generated_schedule" not in st.session_state: st.session_state.generated_schedule = None

# -------------------------------
# Reset / Controls
# -------------------------------
col1,col2,col3 = st.columns([1,2,1])
with col1:
    if st.button("🔄 Reset All"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        if os.path.exists(INIT_FILE): os.remove(INIT_FILE)
        st.success("Reset done.")
        st.experimental_rerun()

# -------------------------------
# Initial Week
# -------------------------------
st.subheader("1️⃣ Select initial week date")
selected_date = st.date_input("Choose a date:", datetime.date.today() if st.session_state.start_date is None else st.session_state.start_date)
week_dates = get_week_dates(selected_date)
st.write("The week is:")
st.columns([st.write(f"**{d.strftime('%a %d/%m/%Y')}**") for d in week_dates])

st.subheader("2️⃣ Assign doctors for first week")
if st.session_state.initial_week is None:
    initial_week = {}
    cols = st.columns(7)
    for i,d in enumerate(week_dates):
        with cols[i]:
            doc = st.selectbox(d.strftime("%a\n%d/%m"), DOCTORS, key=f"manual_{d}")
            initial_week[d]=doc
    if st.button("💾 Save initial week"):
        st.session_state.initial_week = initial_week
        st.session_state.start_date = selected_date
        save_initial_week(initial_week)
        st.success("Initial week saved!")
else:
    st.info("Initial week already saved. Use Reset to change it.")

# -------------------------------
# Generate Schedule for a Range
# -------------------------------
st.subheader("3️⃣ Generate schedule for a date range")
start_gen = st.date_input("Start date:", datetime.date.today())
end_gen = st.date_input("End date:", datetime.date.today() + datetime.timedelta(days=60))
if st.button("Generate Schedule") and st.session_state.initial_week:
    st.session_state.generated_schedule = generate_schedule_for_range(st.session_state.initial_week, start_gen, end_gen)
    st.session_state.edits = {}
    st.success("Schedule generated!")

# -------------------------------
# Display Calendar + Balance Table
# -------------------------------
if st.session_state.generated_schedule:
    flat_schedule = {d: doc for s in st.session_state.generated_schedule.values() for d,doc in s.items()}
    balance = calculate_balance(flat_schedule)

    col_left, col_right = st.columns([1,3])
    with col_left:
        st.subheader("⚖️ Balance Table")
        st.write("Number of Fri/Sat/Sun per doctor:")
        for doc in DOCTORS:
            bg = DOCTOR_COLORS.get(doc, "#ffffff")
            st.markdown(f"<div style='padding:6px;margin-bottom:4px;background:{bg};border-radius:6px'><b>{doc}</b>: Fri {balance[doc]['Fri']} | Sat {balance[doc]['Sat']} | Sun {balance[doc]['Sun']}</div>", unsafe_allow_html=True)
    
    with col_right:
        selected_doctor = st.selectbox("Select doctor to assign:", [""]+DOCTORS)
        months = sorted(st.session_state.generated_schedule.keys())
        for (year, month) in months:
            schedule = st.session_state.generated_schedule[(year,month)]
            month_edits = {d:st.session_state.edits[d] for d in schedule if d in st.session_state.edits}
            st.markdown(f"### 🗓️ {calendar.month_name[month]} {year}")
            # Display calendar grid
            cal = calendar.Calendar(firstweekday=0)
            month_weeks = cal.monthdatescalendar(year, month)
            # Weekday header
            cols = st.columns(7)
            for i,dname in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]): cols[i].write(f"**{dname}**")
            for week in month_weeks:
                cols = st.columns(7)
                for i,d in enumerate(week):
                    cell_col = cols[i]
                    doc_base = schedule.get(d,"")
                    doc_edit = st.session_state.edits.get(d, doc_base)
                    is_edited = d in st.session_state.edits and st.session_state.edits[d]!=doc_base
                    text = f"{d.day}\n{doc_edit}" + (" ✎" if is_edited else "")
                    bg = DOCTOR_COLORS.get(doc_edit,"#ffffff") if doc_edit else "#f0f0f0"
                    border = "3px solid #000" if is_edited else "1px solid #ccc"
                    cell_col.markdown(f"<div style='background:{bg};border-radius:6px;border:{border};padding:6px;text-align:center;'>{text}</div>",unsafe_allow_html=True)
                    # Assign / Clear side by side
                    c1,c2 = cell_col.columns([1,1])
                    if c1.button("Assign", key=f"assign_{d}"):
                        if selected_doctor: st.session_state.edits[d]=selected_doctor; st.experimental_rerun()
                    if c2.button("Clear", key=f"clear_{d}"):
                        st.session_state.edits[d] = ""
                        st.experimental_rerun()

# -------------------------------
# PDF Export
# -------------------------------
if st.session_state.generated_schedule:
    edits_map = {}
    for d,doc in st.session_state.edits.items():
        edits_map.setdefault((d.year,d.month),{})[d]=doc
    if st.button("Export PDF"):
        buf = export_calendar_pdf(st.session_state.generated_schedule, edits_map)
        st.download_button("⬇️ Download PDF", data=buf, file_name="schedule.pdf")
