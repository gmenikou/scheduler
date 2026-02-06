import streamlit as st
import datetime
import calendar
import pandas as pd
from fpdf import FPDF

# ----------------------------
# CONSTANTS
# ----------------------------
DOCTORS = ["Έλενα", "Εύα", "Μαρία", "Αθηνά", "Αλέξανδρος", "Έλια", "Χριστίνα"]

DOCTOR_COLORS = {
    "Έλενα": (255, 200, 200),
    "Εύα": (200, 255, 200),
    "Μαρία": (200, 200, 255),
    "Αθηνά": (255, 255, 200),
    "Αλέξανδρος": (255, 200, 255),
    "Έλια": (200, 255, 255),
    "Χριστίνα": (220, 220, 220)
}

# ----------------------------
# HELPERS
# ----------------------------
def get_week_dates(any_date):
    monday = any_date - datetime.timedelta(days=any_date.weekday())
    return [monday + datetime.timedelta(days=i) for i in range(7)]

def generate_schedule(initial_week, start_date, end_date, manual_assignments=None):
    schedule = {}
    doctor_to_weekday = {doc: i for i, doc in enumerate(initial_week)}
    # Fill initial week
    for i, doc in enumerate(initial_week):
        schedule[start_date + datetime.timedelta(days=i)] = doc
    current_week_start = start_date + datetime.timedelta(days=7)
    while current_week_start <= end_date:
        new_map = {doc: (wd - 2) % 7 for doc, wd in doctor_to_weekday.items()}
        for doc, wd in new_map.items():
            day = current_week_start + datetime.timedelta(days=wd)
            if day <= end_date:
                schedule[day] = doc
        doctor_to_weekday = new_map
        current_week_start += datetime.timedelta(days=7)
    # Inject manual assignments
    if manual_assignments:
        for d, doc in manual_assignments.items():
            schedule[d] = doc
    return schedule

def compute_balance(schedule):
    counts = {doc: {wd:0 for wd in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]} for doc in DOCTORS}
    for date, doc in schedule.items():
        wd = date.weekday()
        days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        counts[doc][days[wd]] += 1
    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index":"Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]
    df["Total"] = df["Weekdays"] + df["Fri"] + df["Sat"] + df["Sun"]
    return df[["Doctor","Weekdays","Fri","Sat","Sun","Total"]]

# ----------------------------
# CALENDAR DISPLAY
# ----------------------------
def display_calendar(schedule):
    manual_assignments = st.session_state.get("manual_assignments", {})
    last_month = None
    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            st.markdown(f"## {month_name}")
            last_month = month_name
            headers = st.columns(7)
            for i,d in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
                headers[i].markdown(f"**{d}**")
            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(date.year, date.month)
            for week in weeks:
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day.month == date.month:
                        doc = schedule.get(day,"")
                        icon = " ✏️" if day in manual_assignments else ""
                        color = '#%02x%02x%02x' % DOCTOR_COLORS.get(doc,(220,220,220))
                        cols[i].markdown(
                            f"<div style='background-color:{color}; padding:6px; border-radius:4px; text-align:center'>"
                            f"<b>{day.day}</b><br>{doc}{icon}</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        cols[i].markdown("")

# ----------------------------
# PDF EXPORT
# ----------------------------
def create_balance_pdf(df, start_date, end_date, filename="balance_summary.pdf"):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'DejaVuSans.ttf', uni=True)

    pdf.set_font("DejaVu","B",16)
    pdf.cell(0,10,"Doctor Balance Summary",ln=True,align="C")
    pdf.set_font("DejaVu","",12)
    pdf.cell(0,8,f"Period: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",ln=True,align="C")
    pdf.ln(6)
    col_widths = [50,30,20,20,20,25]
    pdf.set_font("DejaVu","B",12)
    for h,w in zip(df.columns,col_widths):
        pdf.cell(w,8,h,border=1,align="C")
    pdf.ln()
    pdf.set_font("DejaVu","",12)
    for _, row in df.iterrows():
        for val,w in zip(row,col_widths):
            pdf.cell(w,8,str(val),border=1,align="C")
        pdf.ln()
    pdf.output(filename)
    return filename

def create_calendar_pdf(schedule, filename="calendar.pdf"):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'DejaVuSans.ttf', uni=True)
    pdf.set_font("DejaVu","",12)

    manual_assignments = st.session_state.get("manual_assignments", {})
    last_month = None
    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            pdf.add_page()
            pdf.set_font("DejaVu","B",16)
            pdf.cell(0,10,month_name,ln=True,align="C")
            pdf.ln(4)
            pdf.set_font("DejaVu","B",12)
            col_width = 40
            # Weekday headers
            for wd in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
                pdf.cell(col_width,8,wd,border=1,align="C")
            pdf.ln()
            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(date.year, date.month)
            pdf.set_font("DejaVu","",12)
            cell_height = 20
            for week in weeks:
                x_start = pdf.get_x()
                y_start = pdf.get_y()
                for i, day in enumerate(week):
                    pdf.set_xy(x_start + i*col_width, y_start)
                    if day.month == date.month:
                        doc = schedule.get(day,"")
                        icon = "✏️" if day in manual_assignments else ""
                        pdf.set_fill_color(*DOCTOR_COLORS.get(doc,(220,220,220)))
                        # Combine day number and doctor name without extra gap
                        text = f"{day.day} {icon}\n{doc}"
                        pdf.multi_cell(col_width, 5, text, border=1, align="C", fill=True)
                    else:
                        pdf.set_fill_color(240,240,240)
                        pdf.cell(col_width, cell_height,"",border=1,fill=True)
                pdf.ln(cell_height)
            last_month = month_name
    pdf.output(filename)
    return filename

# ----------------------------
# STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="📅 Πρόγραμμα εφημεριών", layout="wide")
st.title("📅 Πρόγραμμα Εφημεριών")

# Initialize session state
if "manual_assignments" not in st.session_state:
    st.session_state.manual_assignments = {}
for key in ["initial_week","start_date","end_date","schedule","balance"]:
    if key not in st.session_state:
        st.session_state[key] = None

left_col, right_col = st.columns([0.35,0.65])

# ----------------------------
# LEFT: Balance & Manual Assignment
# ----------------------------
with left_col:
    st.subheader("📊 Κατάσταση Εφημεριών Εύρους")

    if st.session_state.start_date and st.session_state.end_date:
        manual_date = st.date_input(
            "Επιλέξετε ημερομηνία για αλλαγή",
            min_value=st.session_state.start_date,
            max_value=st.session_state.end_date
        )
        manual_doctor = st.selectbox("Επιλογή Ακτινολόγου", DOCTORS)
        if st.button("✅ Επικύρωση"):
            st.session_state.manual_assignments[manual_date] = manual_doctor
            st.session_state.schedule[manual_date] = manual_doctor
            st.session_state.balance = compute_balance(st.session_state.schedule)
            st.success(f"{manual_doctor} assigned to {manual_date.strftime('%d/%m/%Y')}")

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        st.dataframe(st.session_state.balance,use_container_width=True,height=260)

        if st.button("📄 Εξαγωγή κατάστασης σε PDF"):
            pdf_file = create_balance_pdf(
                st.session_state.balance,
                st.session_state.start_date,
                st.session_state.end_date
            )
            with open(pdf_file,"rb") as f:
                st.download_button("⬇️ Κατέβασε κατάσταση σε PDF", f, file_name=pdf_file)
        if st.button("🖨️ Εξαγωγή ημερολογίου σε PDF"):
            pdf_file = create_calendar_pdf(st.session_state.schedule)
            with open(pdf_file,"rb") as f:
                st.download_button("⬇️ Κατέβασε ημερολόγιο σε PDF", f, file_name=pdf_file)

# ----------------------------
# RIGHT: Initial Week + Schedule Generation
# ----------------------------
with right_col:
    selected_date = st.date_input("Pick a date in the initial week:", datetime.date.today())
    week_dates = get_week_dates(selected_date)

    # Default initial week order
    default_order = ["Έλενα","Εύα","Μαρία","Αθηνά","Αλέξανδρος","Έλια","Χριστίνα"]
    initial_week = {}
    cols = st.columns(7)
    for i,d in enumerate(week_dates):
        with cols[i]:
            default_idx = DOCTORS.index(default_order[i%7])
            initial_week[d] = st.selectbox(
                d.strftime("%a %d/%m"),
                DOCTORS,
                index=default_idx,
                key=f"doc_{d}"
            )

    if st.button("💾 Επιλογή Ημερομηνίας Έναρξης"):
        st.session_state.initial_week = [initial_week[d] for d in sorted(initial_week)]
        st.session_state.start_date = week_dates[0]

    if st.session_state.initial_week is None:
        st.stop()

    c1,c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start date",st.session_state.start_date)
    with c2:
        end_date = st.date_input("End date",st.session_state.start_date + datetime.timedelta(days=30))

    if st.button("🗓️ Δημιουργία Προγράμματος"):
        st.session_state.schedule = generate_schedule(
            st.session_state.initial_week,
            start_date,
            end_date,
            manual_assignments=st.session_state.manual_assignments
        )
        st.session_state.start_date = start_date
        st.session_state.end_date = end_date
        st.session_state.balance = compute_balance(st.session_state.schedule)

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule)





