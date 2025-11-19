# app.py
import streamlit as st
import datetime
import calendar
import json
import os
import colorsys
from fpdf import FPDF
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
            rotated_week = rotate_week_list(week_list, -2*week_counter)
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
        year, month = current.year, current.month
        num_days = calendar.monthrange(year, month)[1]
        month_dates = [datetime.date(year, month, d) for d in range(1, num_days+1)]
        schedule = generate_schedule(initial_week, month_dates)
        all_schedules[(year, month)] = schedule
        # move to next month
        if month == 12:
            current = datetime.date(year+1, 1, 1)
        else:
            current = datetime.date(year, month+1, 1)
    return all_schedules

# -------------------------------
# Color helpers
# -------------------------------
def generate_doctor_colors(doctor_list):
    colors = {}
    n = max(1, len(doctor_list))
    for i, doc in enumerate(doctor_list):
        hue = i/n
        r,g,b = colorsys.hsv_to_rgb(hue, 0.35, 0.95)
        colors[doc] = '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))
    return colors

DOCTOR_COLORS = generate_doctor_colors(DOCTORS)

# -------------------------------
# Schedule editing helpers
# -------------------------------
def apply_edits_to_schedule(schedule, edits):
    merged = dict(schedule)
    merged.update(edits)
    return merged

# -------------------------------
# Weekend balance
# -------------------------------
def calculate_weekend_balance(schedule, edits=None):
    if edits:
        schedule = apply_edits_to_schedule(schedule, edits)
    balance = {doc: {"Fri":0,"Sat":0,"Sun":0} for doc in DOCTORS}
    for d, doc in schedule.items():
        if not doc:
            continue
        weekday = d.weekday()
        if weekday==4: balance[doc]["Fri"]+=1
        elif weekday==5: balance[doc]["Sat"]+=1
        elif weekday==6: balance[doc]["Sun"]+=1
    return balance

# -------------------------------
# PDF Export
# -------------------------------
class CalendarPDFColored(FPDF):
    def header(self):
        pass

    def add_calendar_page(self, year, month, schedule, edits=None):
        if edits is None: edits = {}
        self.add_page()
        self.set_font("Arial","B",16)
        self.cell(0,10,f"{calendar.month_name[month]} {year}",0,1,"C")
        self.ln(4)
        col_w,row_h = 26,16
        left_margin = (self.w - col_w*7)/2
        self.set_x(left_margin)
        self.set_font("Arial","B",10)
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            self.cell(col_w,row_h,d,1,0,"C")
        self.ln(row_h)
        self.set_x(left_margin)
        self.set_font("Arial","",9)
        cal = calendar.Calendar(firstweekday=0)
        merged = apply_edits_to_schedule(schedule, edits)
        for week in cal.monthdatescalendar(year, month):
            for d in week:
                if d.month != month:
                    self.cell(col_w,row_h,"",1,0,"C")
                    continue
                doc = merged.get(d,"")
                text = f"{d.day} {doc if doc else ''}"
                # set background color
                color = DOCTOR_COLORS.get(doc,(200,200,200))
                if isinstance(color,str):
                    color = tuple(int(color[i:i+2],16) for i in (1,3,5))
                self.set_fill_color(*color)
                self.cell(col_w,row_h,text,1,0,"C",fill=True)
            self.ln(row_h)
            self.set_x(left_margin)

def export_calendar_pdf(all_schedules, edits_map):
    pdf = CalendarPDFColored()
    for (year,month), schedule in sorted(all_schedules.items()):
        month_edits = edits_map.get((year,month),{})
        pdf.add_calendar_page(year,month,schedule,month_edits)
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# -------------------------------
# Calendar display
# -------------------------------
def display_month_calendar(year, month, schedule, edits, selected_doctor, dark_mode=False):
    merged = apply_edits_to_schedule(schedule, edits)
    st.markdown(f"### {calendar.month_name[month]} {year}")
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)

    # Weekday header
    header_cols = st.columns(7)
    for i, dname in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
        header_cols[i].markdown(f"**{dname}**")

    for week in weeks:
        row_cols = st.columns(7)
        for i, d in enumerate(week):
            col = row_cols[i]
            if d.month != month:
                col.markdown("<div style='height:70px;background:#f6f6f6;border-radius:6px'></div>",unsafe_allow_html=True)
                continue
            doc = merged.get(d,"")
            bg = DOCTOR_COLORS.get(doc,"#ffffff") if doc else "#ffffff"
            if d in edits and edits[d] != schedule.get(d,""):
                doc += " *"  # mark edited day
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
                color:#000;
                border:1px solid #ccc;
            ">
                <div style="font-weight:700">{d.day}</div>
                <div style="font-size:12px;white-space:pre-wrap;">{doc if doc else ''}</div>
            </div>
            """
            col.write(html,unsafe_allow_html=True)
            # Side-by-side buttons
            btn1, btn2 = col.columns([1,1])
            key = f"{year}_{month}_{d}"
            if btn1.button("Assign", key=key+"_assign"):
                if selected_doctor:
                    st.session_state.edits[d] = selected_doctor
                    st.rerun()
                else:
                    st.warning("Select a doctor first")
            if btn2.button("Clear", key=key+"_clear"):
                st.session_state.edits[d] = ""
                st.rerun()

# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(layout="wide",page_title="Programma Giatron")

st.title("📅 Programma Giatron – Calendar Grid")

if "initial_week" not in st.session_state:
    st.session_state.initial_week = load_initial_week()
if "start_date" not in st.session_state:
    st.session_state.start_date = None
if "edits" not in st.session_state:
    st.session_state.edits = {}
if "generated_schedule" not in st.session_state:
    st.session_state.generated_schedule = {}

# Top controls
col1,col2,col3 = st.columns([1,2,1])
with col1:
    if st.button("🔄 Reset All"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        if os.path.exists(INIT_FILE):
            os.remove(INIT_FILE)
        st.success("Reset complete")
        st.experimental_rerun()

with col3:
    st.session_state.dark_mode = st.checkbox("🌙 Dark Mode",value=st.session_state.get("dark_mode",False))

# Step 1: initial week
st.subheader("1️⃣ Select a date in the initial week")
selected_date = st.date_input("Choose a date:", datetime.date.today())
week_dates = get_week_dates(selected_date)
colsw = st.columns(7)
for i,d in enumerate(week_dates):
    colsw[i].write(f"**{d.strftime('%a %d/%m/%Y')}**")

st.subheader("2️⃣ Assign doctors for initial week")
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
        st.success("Saved!")
else:
    st.info("Initial week already saved")
    for d in sorted(st.session_state.initial_week.keys()):
        st.write(f"{d.strftime('%d/%m/%Y')} → {st.session_state.initial_week[d]}")

# Step 3: Generate schedule
if st.session_state.initial_week:
    st.subheader("3️⃣ Generate schedule for forthcoming months")
    today = datetime.date.today()
    months_options = [(today + datetime.timedelta(days=30*i)).replace(day=1) for i in range(12)]
    months_display = [d.strftime("%B %Y") for d in months_options]
    selected_month_index = st.selectbox("Choose start month:", list(range(12)),
                                        format_func=lambda x: months_display[x])
    selected_month_date = months_options[selected_month_index]
    num_months = st.number_input("Number of months to generate:",1,12,1,1)
    if st.button("Generate Schedule"):
        st.session_state.generated_schedule = generate_schedule_for_months(st.session_state.initial_week,
                                                                           selected_month_date,num_months)
        st.success("Schedule generated")

# Display calendar with weekend balance
if st.session_state.generated_schedule:
    left_col, right_col = st.columns([1,3])
    with left_col:
        st.markdown("### ⚖️ Weekend Balance")
        combined_schedule = {}
        for sched in st.session_state.generated_schedule.values():
            combined_schedule.update(sched)
        balance = calculate_weekend_balance(combined_schedule, st.session_state.edits)
        st.write("|Doctor|Fri|Sat|Sun|")
        st.write("|------|---|---|---|")
        for doc,cnts in balance.items():
            st.write(f"|{doc}|{cnts['Fri']}|{cnts['Sat']}|{cnts['Sun']}|")
    with right_col:
        months = sorted(st.session_state.generated_schedule.items())
        for (year,month), schedule in months:
            month_edits = {d:doc for d,doc in st.session_state.edits.items() if d.year==year and d.month==month}
            display_month_calendar(year,month,schedule,month_edits,
                                   selected_doctor=None,dark_mode=st.session_state.dark_mode)
    if st.button("Export PDF"):
        edits_map = {}
        for d, doc in st.session_state.edits.items():
            key = (d.year,d.month)
            edits_map.setdefault(key,{})[d]=doc
        buf = export_calendar_pdf(st.session_state.generated_schedule, edits_map)
        st.download_button("⬇️ Download PDF",buf,file_name="calendar.pdf")
