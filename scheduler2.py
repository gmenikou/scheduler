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

    # Group dates into weeks starting from initial_monday
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
# Doctor color generation
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
# PDF Export
# -------------------------------
class CalendarPDF(FPDF):
    def header(self):
        pass

    def add_calendar_page(self, year, month, schedule, edits=None):
        if edits is None: edits = {}
        self.add_page()
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, f"{calendar.month_name[month]} {year}", 0, 1, "C")
        self.ln(4)

        col_width = 26
        row_height = 16
        left_margin = (self.w - col_width * 7) / 2
        self.set_x(left_margin)
        self.set_font("Arial", "B", 10)

        for wd in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            self.cell(col_width, row_height, wd, 1, 0, "C")
        self.ln(row_height)
        self.set_x(left_margin)
        self.set_font("Arial", "", 9)

        cal = calendar.Calendar(firstweekday=0)
        for week in cal.monthdatescalendar(year, month):
            for d in week:
                if d.month != month:
                    self.cell(col_width, row_height, "", 1, 0, "C")
                else:
                    doc_base = schedule.get(d,"")
                    doc = edits.get(d, doc_base)
                    edit_symbol = " ✎" if d in edits and edits[d]!=doc_base else ""
                    text = f"{d.day} {doc}{edit_symbol}" if doc else f"{d.day}"

                    color_hex = DOCTOR_COLORS.get(doc, "#ffffff")
                    r=int(color_hex[1:3],16)
                    g=int(color_hex[3:5],16)
                    b=int(color_hex[5:7],16)
                    self.set_fill_color(r,g,b)

                    self.cell(col_width,row_height,text,1,0,"C",fill=True)
            self.ln(row_height)
            self.set_x(left_margin)

def export_calendar_pdf(schedule_dict, edits_map):
    pdf = CalendarPDF()
    for (year, month), schedule in sorted(schedule_dict.items()):
        month_edits = edits_map.get((year,month),{})
        pdf.add_calendar_page(year,month,schedule,month_edits)
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# -------------------------------
# Balance calculation
# -------------------------------
def calculate_balance(schedule, edits):
    merged = dict(schedule)
    merged.update(edits)
    balance = {doc: {"Fri":0,"Sat":0,"Sun":0} for doc in DOCTORS}
    for d, doc in merged.items():
        wd = d.strftime("%a")
        if wd in ["Fri","Sat","Sun"] and doc in DOCTORS:
            balance[doc][wd] += 1
    return balance

# -------------------------------
# Calendar display
# -------------------------------
def display_month_calendar(year, month, schedule, edits, selected_doctor, dark_mode=False):
    merged = dict(schedule)
    merged.update(edits)

    st.markdown(f"### {calendar.month_name[month]} {year}")
    cal = calendar.Calendar(firstweekday=0)
    month_weeks = cal.monthdatescalendar(year, month)

    # Weekday header
    cols = st.columns(7)
    for i, wd in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
        cols[i].markdown(f"**{wd}**")

    for week in month_weeks:
        cols = st.columns(7)
        for idx, d in enumerate(week):
            with cols[idx]:
                if d.month != month:
                    st.markdown("<div style='height:70px;background:#f6f6f6;border-radius:6px'></div>", unsafe_allow_html=True)
                    continue
                doc_base = schedule.get(d,"")
                doc = edits.get(d, doc_base)
                edit_symbol = " ✎" if d in edits and edits[d]!=doc_base else ""
                bg = DOCTOR_COLORS.get(doc,"#ffffff") if doc else "#ffffff"
                text_color="#000000"
                if dark_mode:
                    r=int(bg[1:3],16); g=int(bg[3:5],16); b=int(bg[5:7],16)
                    luminance = 0.2126*r + 0.7152*g + 0.0722*b
                    if luminance<140: text_color="#ffffff"

                html=f"""
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
                ">
                    <div style="font-weight:700">{d.day}</div>
                    <div style="font-size:12px;white-space:pre-wrap;">{doc}{edit_symbol}</div>
                </div>
                """
                st.write(html,unsafe_allow_html=True)

                c1,c2=st.columns([1,1])
                if c1.button("Assign", key=f"{d}_assign") and selected_doctor:
                    st.session_state.edits[d]=selected_doctor
                    st.experimental_rerun()
                if c2.button("Clear", key=f"{d}_clear"):
                    st.session_state.edits[d]=""
                    st.experimental_rerun()

# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron - Calendar Grid")
st.title("📅 Programma Giatron – Backwards Rotation")

if "initial_week" not in st.session_state: st.session_state.initial_week = load_initial_week()
if "start_date" not in st.session_state: st.session_state.start_date = None
if "edits" not in st.session_state: st.session_state.edits = {}
if "generated_schedule" not in st.session_state: st.session_state.generated_schedule = {}
if "dark_mode" not in st.session_state: st.session_state.dark_mode=False

# -------------------------------
# Sidebar / top controls
# -------------------------------
col1,col2=st.columns([1,3])
with col1:
    if st.button("🔄 Reset All"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        if os.path.exists(INIT_FILE): os.remove(INIT_FILE)
        st.experimental_rerun()
with col2:
    st.checkbox("🌙 Dark Mode", value=st.session_state.dark_mode, key="dark_mode")

# -------------------------------
# Step 1: Select initial week
# -------------------------------
st.subheader("1️⃣ Select a date in the initial week")
selected_date = st.date_input("Choose a date:", datetime.date.today() if not st.session_state.start_date else st.session_state.start_date)
week_dates = get_week_dates(selected_date)
st.write("The week is:")
cols = st.columns(7)
for i,d in enumerate(week_dates):
    cols[i].write(f"**{d.strftime('%a %d/%m/%Y')}**")

# -------------------------------
# Step 2: Assign doctors for first week
# -------------------------------
st.subheader("2️⃣ Assign doctors for the first week")
if st.session_state.initial_week is None:
    initial_week={}
    cols = st.columns(7)
    for i,d in enumerate(week_dates):
        with cols[i]:
            doc = st.selectbox(d.strftime("%a\n%d/%m"), DOCTORS, key=f"manual_{d}")
            initial_week[d]=doc
    if st.button("💾 Save initial week"):
        st.session_state.initial_week=initial_week
        st.session_state.start_date=selected_date
        save_initial_week(initial_week)
        st.success("Initial week saved!")
else:
    st.info("Initial week already saved. Use Reset to change it.")
    st.write("Your assigned initial week:")
    for d in sorted(st.session_state.initial_week.keys()):
        st.write(f"{d.strftime('%d/%m/%Y')} ({d.strftime('%a')}) → {st.session_state.initial_week[d]}")

# -------------------------------
# Step 3: Generate schedule for date range
# -------------------------------
st.subheader("3️⃣ Generate schedule for date range")
start_range = st.date_input("Start date:", datetime.date.today())
end_range = st.date_input("End date:", datetime.date.today()+datetime.timedelta(days=30))
if st.button("Generate Schedule"):
    st.session_state.generated_schedule = {**generate_schedule_for_range(st.session_state.initial_week, start_range, end_range)}
    st.session_state.edits={}  # reset edits
    st.success("Schedule generated. Scroll below to see the calendar grid.")

# -------------------------------
# Step 4: Display calendar and balance table
# -------------------------------
if st.session_state.generated_schedule:
    st.subheader("📋 Calendar & Balance Table")
    layout_cols = st.columns([1,4])
    with layout_cols[0]:
        # Balance table
        balance = calculate_balance({d:doc for m,s in st.session_state.generated_schedule.items() for d,doc in s.items()},
                                    st.session_state.edits)
        st.write("### 🧾 Weekend Balance per Doctor")
        for doc in DOCTORS:
            bg = DOCTOR_COLORS[doc]
            html=f"""
            <div style="
                padding:5px; margin:2px; border-radius:5px;
                background:{bg}; color:#000; font-weight:bold;">
                {doc}: Fri {balance[doc]['Fri']} | Sat {balance[doc]['Sat']} | Sun {balance[doc]['Sun']}
            </div>
            """
            st.write(html, unsafe_allow_html=True)
    with layout_cols[1]:
        # Calendar months one below the other
        for (year, month), schedule in sorted(st.session_state.generated_schedule.items()):
            month_edits = {d:st.session_state.edits[d] for d in st.session_state.edits if d.year==year and d.month==month}
            display_month_calendar(year, month, schedule, month_edits, selected_doctor="", dark_mode=st.session_state.dark_mode)
            st.markdown("<br><br>", unsafe_allow_html=True)

    # PDF export
    if st.button("Export Calendar PDF"):
        edits_map={}
        for d,doc in st.session_state.edits.items():
            key=(d.year,d.month)
            edits_map.setdefault(key,{})[d]=doc
        buf = export_calendar_pdf(st.session_state.generated_schedule, edits_map)
        st.download_button("⬇️ Download PDF", data=buf, file_name="calendar.pdf")
