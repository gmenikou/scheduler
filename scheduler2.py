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
# Schedule helpers
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
        month_dates = [datetime.date(year, month, d) for d in range(1, num_days+1)]
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
        hue = i / n
        r, g, b = colorsys.hsv_to_rgb(hue, 0.35, 0.95)
        hexcol = '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))
        colors[doc] = hexcol
    return colors

DOCTOR_COLORS = generate_doctor_colors(DOCTORS)

# -------------------------------
# PDF calendar with colors & edits
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
        left_margin = (self.w - (col_width*7))/2
        self.set_x(left_margin)

        self.set_font("Arial", "B", 10)
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            self.cell(col_width, row_height, d, 1, 0, "C")
        self.ln(row_height)
        self.set_x(left_margin)

        self.set_font("Arial","",9)
        cal = calendar.Calendar(firstweekday=0)
        for week in cal.monthdatescalendar(year, month):
            for d in week:
                if d.month != month:
                    self.cell(col_width, row_height, "",1,0,"C")
                else:
                    doc = edits.get(d, schedule.get(d,""))
                    # ✎ edit symbol
                    if d in edits and edits[d] != schedule.get(d,""):
                        text = f"{d.day} {doc} ✎"
                    else:
                        text = f"{d.day} {doc}"
                    self.set_fill_color(*tuple(int(DOCTOR_COLORS.get(doc,"#e0e0e0")[i:i+2],16) for i in (1,3,5)))
                    self.cell(col_width,row_height,text,1,0,"C",fill=True)
            self.ln(row_height)
            self.set_x(left_margin)

def export_calendar_pdf(all_schedules, edits_map):
    pdf = CalendarPDF()
    for (year, month), schedule in all_schedules.items():
        pdf.add_calendar_page(year, month, schedule, edits=edits_map.get((year,month),{}))
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# -------------------------------
# Streamlit helpers
# -------------------------------
def apply_edits_to_schedule(schedule, edits):
    merged = dict(schedule)
    merged.update(edits)
    return merged

def display_month_calendar(year, month, schedule, edits, selected_doctor, enable_assign=True, dark_mode=False):
    merged = apply_edits_to_schedule(schedule, edits)
    st.markdown(f"### 🗓️ {calendar.month_name[month]} {year}")
    cal = calendar.Calendar(firstweekday=0)
    month_weeks = cal.monthdatescalendar(year, month)

    cols = st.columns(7)
    for i, name in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
        cols[i].markdown(f"**{name}**")

    for week in month_weeks:
        cols = st.columns(7)
        for i, d in enumerate(week):
            col = cols[i]
            if d.month != month:
                col.markdown("<div style='height:70px;background:#f6f6f6;border-radius:6px'></div>", unsafe_allow_html=True)
                continue
            doc = merged.get(d,"")
            is_edited = d in edits and edits[d] != schedule.get(d,"")  # ✎ EDIT SYMBOL
            bg = DOCTOR_COLORS.get(doc,"#ffffff") if doc else "#ffffff"
            text_color="#000000"
            if dark_mode:
                r=int(bg[1:3],16);g=int(bg[3:5],16);b=int(bg[5:7],16)
                lum=0.2126*r+0.7152*g+0.0722*b
                if lum<140: text_color="#ffffff"
            display_text = f"{d.day}"
            if doc: display_text+=f"\n{doc}"
            if is_edited: display_text+=" ✎"  # ✎ EDIT SYMBOL

            key=f"cell_{year}_{month}_{d.isoformat()}"
            html=f"""
            <div style="
            border-radius:8px;padding:6px;min-height:70px;
            display:flex;flex-direction:column;justify-content:space-between;
            align-items:center;background:{bg};color:{text_color};border:1px solid #ccc
            ">{display_text}</div>
            """
            col.write(html, unsafe_allow_html=True)
            c1,c2=st.columns([1,1])
            if enable_assign:
                if c1.button("Assign", key=key+"_assign"):
                    if selected_doctor:
                        st.session_state.edits[d]=selected_doctor
                        st.rerun()
                    else:
                        st.warning("Select doctor before assigning")
            if c2.button("Clear", key=key+"_clear"):
                if d in st.session_state.edits:
                    del st.session_state.edits[d]
                else:
                    st.session_state.edits[d] = ""
                st.rerun()

# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron")
st.title("📅 Programma Giatron – Calendar Grid with Edits")

# Session state
if "initial_week" not in st.session_state: st.session_state.initial_week=load_initial_week()
if "start_date" not in st.session_state: st.session_state.start_date=None
if "generated_schedule" not in st.session_state: st.session_state.generated_schedule={}
if "edits" not in st.session_state: st.session_state.edits={}
if "dark_mode" not in st.session_state: st.session_state.dark_mode=False

# Reset / Dark mode
col1,col2,col3=st.columns([1,2,1])
with col1:
    if st.button("🔄 Reset All"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        if os.path.exists(INIT_FILE): os.remove(INIT_FILE)
        st.rerun()
with col3:
    st.session_state.dark_mode=st.checkbox("🌙 Dark Mode",value=st.session_state.dark_mode)

if st.session_state.dark_mode:
    st.markdown("""<style>.stApp{background:#0f1115;color:#e6eef8;}</style>""", unsafe_allow_html=True)

# Step1: initial week
st.subheader("1️⃣ Select a date in the initial week")
if st.session_state.start_date is None:
    selected_date = st.date_input("Choose a date:", datetime.date.today())
else: selected_date = st.session_state.start_date
week_dates = get_week_dates(selected_date)
st.write("The week is:")
cols = st.columns(7)
for i,d in enumerate(week_dates): cols[i].write(f"**{d.strftime('%a %d/%m/%Y')}**")

# Step2: assign doctors
st.subheader("2️⃣ Assign doctors for first week")
if st.session_state.initial_week is None:
    initial_week={}
    cols=st.columns(7)
    for i,d in enumerate(week_dates):
        with cols[i]:
            doc=st.selectbox(d.strftime("%a\n%d/%m"),DOCTORS,key=f"manual_{d}")
            initial_week[d]=doc
    if st.button("💾 Save initial week"):
        st.session_state.initial_week=initial_week
        st.session_state.start_date=selected_date
        save_initial_week(initial_week)
        st.success("Initial week saved!")
else:
    st.info("Initial week already saved.")

# Step3: generate schedule
if st.session_state.initial_week:
    st.subheader("3️⃣ Generate schedule")
    today=datetime.date.today()
    months_options=[(today+datetime.timedelta(days=30*i)).replace(day=1) for i in range(12)]
    months_display=[d.strftime("%B %Y") for d in months_options]
    selected_month_index=st.selectbox("Start month",list(range(12)),format_func=lambda x:months_display[x])
    selected_month_date=months_options[selected_month_index]
    num_months=st.number_input("Number of months",min_value=1,max_value=12,value=1,step=1)
    if st.button("Generate Schedule"):
        st.session_state.generated_schedule=generate_schedule_for_months(
            st.session_state.initial_week, selected_month_date, num_months)
        st.success("Schedule generated. Scroll down for calendar view.")

# -------------------------------
# Calendar & Controls
# -------------------------------
if st.session_state.generated_schedule:
    left_col,right_col=st.columns([1,3])
    with left_col:
        st.write("### 📊 Weekend Balance")
        # count Fri/Sat/Sun per doctor
        counts={doc:{"Fri":0,"Sat":0,"Sun":0} for doc in DOCTORS}
        for sched in st.session_state.generated_schedule.values():
            for d,doc in sched.items():
                if d.weekday()==4: counts[doc]["Fri"]+=1
                elif d.weekday()==5: counts[doc]["Sat"]+=1
                elif d.weekday()==6: counts[doc]["Sun"]+=1
        # display table nicely
        st.markdown("| Doctor | Fri | Sat | Sun | Total |")
        st.markdown("|---|---|---|---|---|")
        for doc in DOCTORS:
            f=counts[doc]["Fri"];s=counts[doc]["Sat"];u=counts[doc]["Sun"]
            total=f+s+u
            color=DOCTOR_COLORS.get(doc,"#ffffff")
            st.markdown(f"<tr style='background:{color}'><td>{doc}</td><td>{f}</td><td>{s}</td><td>{u}</td><td>{total}</td></tr>",unsafe_allow_html=True)

        st.write("---")
        selected_doctor = st.selectbox("Select doctor to assign",[""]+DOCTORS)
        if st.button("Clear all edits"):
            st.session_state.edits={}
            st.rerun()
        if st.button("Export PDF (with edits)"):
            edits_map={}
            for d,doc in st.session_state.edits.items():
                key=(d.year,d.month)
                edits_map.setdefault(key,{})[d]=doc
            buf=export_calendar_pdf(st.session_state.generated_schedule,edits_map)
            st.download_button("⬇️ Download PDF",data=buf,file_name="calendar.pdf")

    with right_col:
        months=sorted(st.session_state.generated_schedule.items())
        for (year,month),schedule in months:
            # collect edits for this month
            month_edits={d:doc for d,doc in st.session_state.edits.items() if d.year==year and d.month==month}
            display_month_calendar(year,month,schedule,month_edits,selected_doctor,enable_assign=True,dark_mode=st.session_state.dark_mode)

    if st.session_state.edits:
        st.subheader("📝 Current edits")
        for d,doc in sorted(st.session_state.edits.items()):
            st.write(f"{d.strftime('%d/%m/%Y')} → {doc if doc else '(cleared)'}")
# app.py
import streamlit as st
import datetime
import calendar
from fpdf import FPDF
import json
import os
import colorsys
import io
import pandas as pd

# -------------------------------
# Constants
# -------------------------------
DOCTORS = ["Elena", "Eva", "Maria", "Athina", "Alexandros", "Elia", "Christina"]
INIT_FILE = "initial_week.json"

# -------------------------------
# Helpers: scheduling
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
        month_dates = [datetime.date(year, month, d) for d in range(1, num_days+1)]
        schedule = generate_schedule(initial_week, month_dates)
        all_schedules[(year, month)] = schedule
        # next month
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
        hue = i/n
        r,g,b = colorsys.hsv_to_rgb(hue, 0.35, 0.95)
        colors[doc] = '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))
    return colors
DOCTOR_COLORS = generate_doctor_colors(DOCTORS)

# -------------------------------
# PDF calendar with color
# -------------------------------
class CalendarPDFColored(FPDF):
    def header(self):
        pass

    def add_calendar_page(self, year, month, schedule, edits=None):
        if edits is None:
            edits = {}
        self.add_page()
        # Title
        self.set_font("Arial","B",16)
        self.cell(0,10,f"{calendar.month_name[month]} {year}",0,1,"C")
        self.ln(4)

        col_width = 26
        row_height = 16
        left_margin = (self.w - (col_width*7))/2
        self.set_x(left_margin)

        # Weekday header
        self.set_font("Arial","B",10)
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            self.cell(col_width,row_height,d,1,0,"C")
        self.ln(row_height)
        self.set_x(left_margin)

        self.set_font("Arial","",9)
        cal = calendar.Calendar(firstweekday=0)
        for week in cal.monthdatescalendar(year, month):
            for d in week:
                if d.month != month:
                    self.cell(col_width,row_height,"",1,0,"C")
                else:
                    doc = edits.get(d,schedule.get(d,""))
                    text = f"{d.day} {doc}"
                    # color background
                    bg_color = DOCTOR_COLORS.get(doc,"#ffffff") if doc else "#ffffff"
                    r = int(bg_color[1:3],16)
                    g = int(bg_color[3:5],16)
                    b = int(bg_color[5:7],16)
                    self.set_fill_color(r,g,b)
                    self.cell(col_width,row_height,text,1,0,"C",fill=True)
            self.ln(row_height)
            self.set_x(left_margin)

def export_calendar_pdf(all_schedules, edits_map):
    pdf = CalendarPDFColored()
    for (year,month), schedule in sorted(all_schedules.items()):
        month_edits = edits_map.get((year,month),{})
        pdf.add_calendar_page(year,month,schedule,month_edits)
    pdf_bytes = pdf.output(dest='S').encode('latin1')
    buf = io.BytesIO(pdf_bytes)
    buf.seek(0)
    return buf

# -------------------------------
# Weekend balance panel
# -------------------------------
def apply_edits_to_schedule(schedule, edits):
    merged = dict(schedule)
    merged.update(edits)
    return merged

def display_weekend_balance(schedule, edits=None):
    if edits:
        schedule = apply_edits_to_schedule(schedule, edits)
    rows=[]
    for doc in DOCTORS:
        fri=sat=sun=0
        for d,a_doc in schedule.items():
            if a_doc!=doc: continue
            wd=d.weekday()
            if wd==4: fri+=1
            elif wd==5: sat+=1
            elif wd==6: sun+=1
        rows.append({"Doctor":doc,"Fri":fri,"Sat":sat,"Sun":sun})
    df=pd.DataFrame(rows)
    def color_doctor(val):
        color=DOCTOR_COLORS.get(val,"#ffffff")
        return f'background-color:{color}; font-weight:bold;'
    styled_df=df.style.applymap(lambda v: color_doctor(v) if v in DOCTOR_COLORS else '', subset=["Doctor"])
    st.dataframe(styled_df,use_container_width=True)

# -------------------------------
# Calendar grid display
# -------------------------------
def display_month_calendar(year, month, schedule, edits, selected_doctor, dark_mode=False):
    merged=apply_edits_to_schedule(schedule,edits)
    st.markdown(f"### 🗓️ {calendar.month_name[month]} {year}")
    cal=calendar.Calendar(firstweekday=0)
    month_weeks=cal.monthdatescalendar(year,month)

    # Weekday header
    cols=st.columns(7)
    weekday_names=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    for i,c in enumerate(cols):
        c.markdown(f"**{weekday_names[i]}**")

    for week in month_weeks:
        cols=st.columns(7)
        for c_idx,d in enumerate(week):
            cell_col=cols[c_idx]
            if d.month!=month:
                cell_col.markdown("<div style='height:70px;background:#f6f6f6;border-radius:6px'></div>",unsafe_allow_html=True)
                continue
            doc=merged.get(d,"")
            bg=DOCTOR_COLORS.get(doc,"#ffffff") if doc else "#ffffff"
            text_color="#000000"
            if dark_mode:
                try:
                    r=int(bg[1:3],16); g=int(bg[3:5],16); b=int(bg[5:7],16)
                    lum=0.2126*r+0.7152*g+0.0722*b
                    if lum<140: text_color="#ffffff"
                except: text_color="#ffffff"
            display_text=f"{d.day}"
            if doc: display_text+=f"\n{doc}"
            key=f"cell_{year}_{month}_{d.isoformat()}"
            with cell_col:
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
                    <div style="font-size:12px;white-space:pre-wrap;">{doc if doc else ''}</div>
                </div>
                """
                st.write(html,unsafe_allow_html=True)
                # Buttons side by side
                c1,c2=st.columns([1,1])
                if c1.button("Assign",key=key+"_assign"):
                    if selected_doctor:
                        st.session_state.edits[d]=selected_doctor
                        st.experimental_rerun()
                    else:
                        st.warning("Select doctor before assigning.")
                if c2.button("Clear",key=key+"_clear"):
                    if d in st.session_state.edits:
                        del st.session_state.edits[d]
                    else:
                        st.session_state.edits[d]=""
                    st.experimental_rerun()

# -------------------------------
# Streamlit app
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron")
st.title("📅 Programma Giatron – Calendar Grid")

# Session state
if "initial_week" not in st.session_state: st.session_state.initial_week=load_initial_week()
if "start_date" not in st.session_state: st.session_state.start_date=None
if "edits" not in st.session_state: st.session_state.edits={}
if "generated_schedule" not in st.session_state: st.session_state.generated_schedule={}
if "dark_mode" not in st.session_state: st.session_state.dark_mode=False

# Reset + Dark mode
col1,col2,col3=st.columns([1,2,1])
with col1:
    if st.button("🔄 Reset All"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        if os.path.exists(INIT_FILE): os.remove(INIT_FILE)
        st.success("Reset done. Reloading...")
        st.experimental_rerun()
with col3:
    st.session_state.dark_mode=st.checkbox("🌙 Dark Mode",value=st.session_state.dark_mode)

if st.session_state.dark_mode:
    DARK_MODE_CSS="""
    <style>
    .stApp { background-color:#0f1115; color:#e6eef8; }
    .stButton>button { background-color:#2b2f36; color:#e6eef8; }
    </style>
    """
    st.markdown(DARK_MODE_CSS,unsafe_allow_html=True)

# Step 1: initial week
st.subheader("1️⃣ Select a date in the initial week")
selected_date=st.session_state.start_date or st.date_input("Choose a date:", datetime.date.today())
week_dates=get_week_dates(selected_date)
st.write("The week is:")
cols=st.columns(7)
for i,d in enumerate(week_dates): cols[i].write(f"**{d.strftime('%a %d/%m/%Y')}**")

# Step 2: assign doctors
st.subheader("2️⃣ Assign doctors for first week")
if st.session_state.initial_week is None:
    initial_week={}
    cols=st.columns(7)
    for i,d in enumerate(week_dates):
        with cols[i]:
            doc=st.selectbox(d.strftime("%a\n%d/%m"),DOCTORS,key=f"manual_{d}")
            initial_week[d]=doc
    if st.button("💾 Save initial week"):
        st.session_state.initial_week=initial_week
        st.session_state.start_date=selected_date
        save_initial_week(initial_week)
        st.success("Initial week saved!")
else:
    st.info("Initial week already saved. Use Reset to change it.")
    st.write("Your initial week:")
    for d in sorted(st.session_state.initial_week.keys()):
        st.write(f"{d.strftime('%d/%m/%Y')} ({d.strftime('%a')}) → {st.session_state.initial_week[d]}")

# Step 3: generate schedule
if st.session_state.initial_week:
    st.subheader("3️⃣ Generate schedule for months")
    today=datetime.date.today()
    months_options=[(today + datetime.timedelta(days=30*i)).replace(day=1) for i in range(12)]
    months_display=[d.strftime("%B %Y") for d in months_options]
    selected_month_index=st.selectbox("Choose start month:",list(range(12)),format_func=lambda x: months_display[x])
    selected_month_date=months_options[selected_month_index]
    num_months=st.number_input("Number of months:",min_value=1,max_value=12,value=1,step=1)
    if st.button("Generate Schedule"):
        multi_schedule=generate_schedule_for_months(st.session_state.initial_week,selected_month_date,num_months)
        st.session_state.generated_schedule=multi_schedule
        st.success("Schedule generated. Scroll down to view calendar.")

# Calendar + balance panel
if st.session_state.generated_schedule:
    st.subheader("⚖️ Weekend Balance & Calendar")
    left_col,right_col=st.columns([1,3])
    with left_col:
        st.write("### ⚖️ Weekend Balance")
        combined_schedule={}
        for sched in st.session_state.generated_schedule.values(): combined_schedule.update(sched)
        display_weekend_balance(combined_schedule,st.session_state.edits)

        st.write("---")
        st.write("### Assign doctor")
        selected_doctor=st.selectbox("Select doctor to assign:",[""]+DOCTORS,index=0)
        if st.button("Clear all edits"):
            st.session_state.edits={}
            st.experimental_rerun()
        if st.button("Export calendar PDF (with edits)"):
            edits_map={}
            for d,doc in st.session_state.edits.items():
                d_obj=d if isinstance(d,datetime.date) else datetime.datetime.strptime(d,"%Y-%m-%d").date()
                key=(d_obj.year,d_obj.month)
                edits_map.setdefault(key,{})[d_obj]=doc
            buf=export_calendar_pdf(st.session_state.generated_schedule,edits_map)
            st.download_button("⬇️ Download Calendar PDF",data=buf,file_name="calendar.pdf")

    with right_col:
        for (year,month), schedule in sorted(st.session_state.generated_schedule.items()):
            month_edits={}
            for d,doc in st.session_state.edits.items():
                d_obj=d if isinstance(d,datetime.date) else datetime.datetime.strptime(d,"%Y-%m-%d").date()
                if d_obj.year==year and d_obj.month==month:
                    month_edits[d_obj]=doc
            display_month_calendar(year,month,schedule,month_edits,selected_doctor,st.session_state.dark_mode)

    # Show edits list
    if st.session_state.edits:
        st.subheader("📝 Current edits")
        for d in sorted(st.session_state.edits.keys()):
            val=st.session_state.edits[d]
            st.write(f"{d.strftime('%d/%m/%Y')} → {val if val else '(cleared)'}")
        if st.button("💾 Save edits to file"):
            serializable={d.strftime('%Y-%m-%d'): doc for d,doc in st.session_state.edits.items()}
            with open("edits.json","w",encoding="utf-8") as f: json.dump(serializable,f,ensure_ascii=False,indent=2)
            st.success("Edits saved to edits.json")

