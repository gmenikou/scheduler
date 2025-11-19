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
    all_dates = [start_date + datetime.timedelta(days=i) for i in range((end_date-start_date).days+1)]
    schedule = generate_schedule(initial_week, all_dates)
    return schedule

def generate_doctor_colors(doctor_list):
    colors = {}
    n = max(1, len(doctor_list))
    for i, doc in enumerate(doctor_list):
        hue = (i/n)
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

    def add_calendar_page(self, schedule, edits=None):
        if edits is None:
            edits = {}
        self.add_page()
        self.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        self.set_font('DejaVu', '', 12)

        # Determine month range
        dates = sorted(schedule.keys())
        if not dates:
            return
        start = dates[0]
        end = dates[-1]
        current = start.replace(day=1)
        while current <= end:
            year = current.year
            month = current.month
            self.set_font('DejaVu', 'B', 14)
            self.cell(0, 10, f"{calendar.month_name[month]} {year}", 0, 1, "C")
            self.ln(2)

            col_width = 26
            row_height = 16
            left_margin = (self.w - (col_width*7))/2
            self.set_x(left_margin)
            self.set_font('DejaVu', '', 10)
            # Weekday header
            for wd in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
                self.cell(col_width,row_height,wd,1,0,'C')
            self.ln(row_height)
            self.set_x(left_margin)

            cal = calendar.Calendar(firstweekday=0)
            for week in cal.monthdatescalendar(year,month):
                for d in week:
                    if d.month != month:
                        self.cell(col_width,row_height,"",1,0,'C')
                    else:
                        doc = edits.get(d,schedule.get(d,""))
                        bg = DOCTOR_COLORS.get(doc,"#ffffff") if doc else "#ffffff"
                        try:
                            r=int(bg[1:3],16)
                            g=int(bg[3:5],16)
                            b=int(bg[5:7],16)
                        except:
                            r=g=b=255
                        self.set_fill_color(r,g,b)
                        self.cell(col_width,row_height,f"{d.day}\n{doc}",1,0,'C',fill=True)
                self.ln(row_height)
                self.set_x(left_margin)
            current = current + datetime.timedelta(days=calendar.monthrange(year,month)[1])

def export_calendar_pdf(schedule, edits):
    pdf = CalendarPDF()
    pdf.add_calendar_page(schedule, edits)
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# -------------------------------
# Streamlit UI
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron - Calendar")

st.title("📅 Programma Giatron – Calendar View")

# Session state
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
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    if os.path.exists(INIT_FILE):
        os.remove(INIT_FILE)
    st.experimental_rerun()

# Step 1: Select initial week
st.subheader("1️⃣ Select a date in the initial week")
selected_date = st.date_input("Choose a date:", datetime.date.today())
week_dates = get_week_dates(selected_date)
st.write("The week is:")
cols = st.columns(7)
for i,d in enumerate(week_dates):
    cols[i].write(f"**{d.strftime('%a %d/%m/%Y')}**")

# Step 2: Assign initial week
st.subheader("2️⃣ Assign doctors for the first week")
if st.session_state.initial_week is None:
    initial_week = {}
    cols = st.columns(7)
    for i,d in enumerate(week_dates):
        with cols[i]:
            doc = st.selectbox(d.strftime("%a %d/%m"), DOCTORS, key=f"manual_{d}")
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

# Step 3: Generate schedule for date range
st.subheader("3️⃣ Generate schedule")
start_range = st.date_input("Start date", datetime.date.today())
end_range = st.date_input("End date", datetime.date.today()+datetime.timedelta(days=365))
if st.button("Generate Schedule"):
    st.session_state.generated_schedule = generate_schedule_for_range(
        st.session_state.initial_week, start_range, end_range
    )
    st.success("Schedule generated!")

# Left panel: Balance table
if st.session_state.generated_schedule:
    st.subheader("📊 Balance (Fri/Sat/Sun per doctor)")
    balance = {doc: {"Fri":0,"Sat":0,"Sun":0} for doc in DOCTORS}
    for d,doc in st.session_state.generated_schedule.items():
        if doc in DOCTORS:
            wd = d.weekday()
            if wd==4: balance[doc]["Fri"]+=1
            elif wd==5: balance[doc]["Sat"]+=1
            elif wd==6: balance[doc]["Sun"]+=1
    # Display table with colors
    table_data = []
    for doc in DOCTORS:
        row = f'<td style="background:{DOCTOR_COLORS[doc]};padding:4px">{doc}</td>'
        for day in ["Fri","Sat","Sun"]:
            row += f'<td style="padding:4px">{balance[doc][day]}</td>'
        table_data.append(f"<tr>{row}</tr>")
    html_table = f"""
    <table border="1" style="border-collapse:collapse;text-align:center;">
        <tr><th>Doctor</th><th>Fri</th><th>Sat</th><th>Sun</th></tr>
        {''.join(table_data)}
    </table>
    """
    st.markdown(html_table, unsafe_allow_html=True)

# Calendar display
if st.session_state.generated_schedule:
    st.subheader("📋 Calendar")
    merged = st.session_state.generated_schedule.copy()
    for d in sorted(merged.keys()):
        doc = merged[d]
        key_assign = f"assign_{d.year}_{d.month}_{d.day}"
        key_clear = f"clear_{d.year}_{d.month}_{d.day}"
        col1, col2 = st.columns([1,1])
        col1.write(f"{d.strftime('%d/%m/%Y')} → {doc}")
        if col1.button("Assign", key=key_assign):
            st.session_state.edits[d] = doc
            st.experimental_rerun()
        if col2.button("Clear", key=key_clear):
            st.session_state.edits[d] = ""
            st.experimental_rerun()

# PDF export
if st.session_state.generated_schedule:
    edits = st.session_state.edits
    if st.button("Export PDF"):
        buf = export_calendar_pdf(st.session_state.generated_schedule, edits)
        st.download_button("⬇️ Download PDF", data=buf, file_name="calendar.pdf")
