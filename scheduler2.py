import streamlit as st
import datetime
import calendar
import pandas as pd
from fpdf import FPDF
import os

# ----------------------------
# 1. CONSTANTS
# ----------------------------
DOCTORS = ["Elena", "Eva", "Maria", "Athina", "Alexandros", "Elia", "Christina"]

DOCTOR_COLORS = {
    "Elena": (255, 200, 200),
    "Eva": (200, 255, 200),
    "Maria": (200, 200, 255),
    "Athina": (255, 255, 200),
    "Alexandros": (255, 200, 255),
    "Elia": (200, 255, 255),
    "Christina": (220, 220, 220)
}

# ----------------------------
# 2. HELPERS
# ----------------------------
def get_week_dates(any_date):
    monday = any_date - datetime.timedelta(days=any_date.weekday())
    return [monday + datetime.timedelta(days=i) for i in range(7)]

# ----------------------------
# 3. SCHEDULE GENERATION
# ----------------------------
def generate_schedule(initial_week, start_date, end_date):
    schedule = {}
    doctor_to_weekday = {doc: i for i, doc in enumerate(initial_week)}

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

    return schedule

# ----------------------------
# 4. BALANCE TABLE
# ----------------------------
def compute_balance(schedule):
    counts = {doc: {"Mon":0,"Tue":0,"Wed":0,"Thu":0,"Fri":0,"Sat":0,"Sun":0} for doc in DOCTORS}
    for date, doc in schedule.items():
        wd = date.weekday()
        if wd == 0: counts[doc]["Mon"] += 1
        elif wd == 1: counts[doc]["Tue"] += 1
        elif wd == 2: counts[doc]["Wed"] += 1
        elif wd == 3: counts[doc]["Thu"] += 1
        elif wd == 4: counts[doc]["Fri"] += 1
        elif wd == 5: counts[doc]["Sat"] += 1
        elif wd == 6: counts[doc]["Sun"] += 1

    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df = df.rename(columns={"index":"Doctor"})
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]
    df["Weekend"] = df["Fri"] + df["Sat"] + df["Sun"]
    df["Total"] = df["Weekdays"] + df["Weekend"]
    return df[["Doctor","Weekdays","Fri","Sat","Sun","Weekend","Total"]]

# ----------------------------
# 5. CALENDAR DISPLAY
# ----------------------------
def display_calendar(schedule):
    last_month = None

    # safe manual_dates
    manual_dates = st.session_state.get("manual_dates")
    if manual_dates is None:
        manual_dates = set()
    else:
        manual_dates = set(d if isinstance(d, datetime.date) else d.date() for d in manual_dates)

    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            st.markdown(f"## {month_name}")
            last_month = month_name

            headers = st.columns(7)
            for i, d in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
                headers[i].markdown(f"**{d}**")

            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(date.year, date.month)

            for week in weeks:
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day.month == date.month:
                        doc = schedule.get(day,"")
                        icon = " ✏️" if day in manual_dates else ""
                        color = '#%02x%02x%02x' % DOCTOR_COLORS.get(doc,(220,220,220))
                        cols[i].markdown(
                            f"<div style='background:{color}; padding:6px; border-radius:4px; text-align:center'>"
                            f"<b>{day.day}</b><br>{doc}{icon}</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        cols[i].markdown("")

# ----------------------------
# 6. BALANCE PDF EXPORT (UTF-8 Safe)
# ----------------------------
def create_balance_pdf(df, start_date, end_date, filename="balance_summary.pdf"):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not os.path.isfile(font_path):
        font_path = "DejaVuSans.ttf"
    pdf.add_font("DejaVu","",font_path,uni=True)
    pdf.set_font("DejaVu","B",16)
    pdf.cell(0,10,"Doctor Balance Summary",ln=True,align="C")

    pdf.set_font("DejaVu","",12)
    pdf.cell(
        0,8,f"Period: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
        ln=True,align="C"
    )
    pdf.ln(6)

    col_widths = [40,30,20,20,20,30,25]

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

# ----------------------------
# 7. STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="📅 Programma Giatron", layout="wide")
st.title("📅 Programma Giatron – Backwards Rotation")

# session state defaults
for key in ["initial_week","start_date","end_date","schedule","balance","manual_dates"]:
    if key not in st.session_state or st.session_state[key] is None:
        if key == "manual_dates":
            st.session_state[key] = set()
        else:
            st.session_state[key] = None

left_col, right_col = st.columns([0.35,0.65])

# LEFT PANEL: BALANCE + MANUAL ASSIGNMENT + PDF
with left_col:
    st.subheader("📊 Balance (Range)")

    if st.session_state.balance is not None:
        st.dataframe(st.session_state.balance,use_container_width=True,height=260)

        # MANUAL ASSIGNMENT UNDER BALANCE
        st.markdown("### ✏️ Manual Assignment")
        manual_date = st.date_input(
            "Pick a date to manually assign",
            min_value=st.session_state.start_date,
            max_value=st.session_state.end_date,
            key="manual_date_picker"
        )
        manual_doctor = st.selectbox("Select Doctor", DOCTORS, key="manual_doctor_select")

        if st.button("✅ Assign Doctor"):
            day_only = manual_date  # date object
            st.session_state.schedule[day_only] = manual_doctor
            st.session_state.manual_dates.add(day_only)
            st.session_state.balance = compute_balance(st.session_state.schedule)
            st.success(f"{manual_doctor} assigned to {day_only.strftime('%d/%m/%Y')}")

        # PDF export
        if st.button("📄 Export Balance PDF"):
            pdf_file = create_balance_pdf(
                st.session_state.balance,
                st.session_state.start_date,
                st.session_state.end_date
            )
            with open(pdf_file,"rb") as f:
                st.download_button("⬇️ Download Balance PDF",f,file_name=pdf_file)

# RIGHT PANEL: MAIN FLOW
with right_col:
    selected_date = st.date_input("Pick a date in the initial week:", datetime.date.today())
    week_dates = get_week_dates(selected_date)

    # INITIAL WEEK SELECTBOXES WITH DEFAULT ORDER
    default_order = ["Elena", "Eva", "Maria", "Athina", "Alexandros", "Elia", "Christina"]

    initial_week = {}
    cols = st.columns(7)
    for i,d in enumerate(week_dates):
        with cols[i]:
            default_idx = DOCTORS.index(default_order[i % len(default_order)])
            initial_week[d] = st.selectbox(
                d.strftime("%a %d/%m"),
                DOCTORS,
                index=default_idx,
                key=f"doc_{d}"
            )

    if st.button("💾 Save Initial Week"):
        st.session_state.initial_week = [initial_week[d] for d in sorted(initial_week)]
        st.session_state.start_date = week_dates[0]

    if st.session_state.initial_week is None:
        st.stop()

    c1,c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start date",st.session_state.start_date)
    with c2:
        end_date = st.date_input("End date",st.session_state.start_date+datetime.timedelta(days=30))

    if st.button("🗓️ Generate Schedule"):
        st.session_state.start_date = start_date
        st.session_state.end_date = end_date
        st.session_state.schedule = generate_schedule(
            st.session_state.initial_week,start_date,end_date
        )
        st.session_state.balance = compute_balance(st.session_state.schedule)

    # DISPLAY CALENDAR IF SCHEDULE EXISTS
    if st.session_state.schedule is not None:
        display_calendar(st.session_state.schedule)
