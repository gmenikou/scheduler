import streamlit as st
import datetime
import calendar
import pandas as pd
from fpdf import FPDF

# ----------------------------
# 1. CONSTANTS
# ----------------------------
DOCTORS = ["Elena", "Eva", "Maria", "Athina", "Alexandros", "Elia", "Christina"]

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
# 4. BALANCE (COMPACT, NO SCROLL)
# ----------------------------
def compute_balance(schedule):
    counts = {
        doc: {"Mon":0,"Tue":0,"Wed":0,"Thu":0,"Fri":0,"Sat":0,"Sun":0}
        for doc in DOCTORS
    }

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
    df = df.rename(columns={"index": "Doctor"})

    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]
    df["Weekend"] = df["Fri"] + df["Sat"] + df["Sun"]
    df["Total"] = df["Weekdays"] + df["Weekend"]

    return df[["Doctor", "Weekdays", "Fri", "Sat", "Sun", "Weekend", "Total"]]

# ----------------------------
# 5. BALANCE PDF
# ----------------------------
def create_balance_pdf(df, start_date, end_date, filename="balance_summary.pdf"):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Doctor Balance Summary", ln=True, align="C")

    pdf.set_font("Arial", "", 12)
    pdf.cell(
        0, 8,
        f"Period: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
        ln=True, align="C"
    )
    pdf.ln(6)

    col_widths = [40, 30, 20, 20, 20, 30, 25]

    pdf.set_font("Arial", "B", 12)
    for h, w in zip(df.columns, col_widths):
        pdf.cell(w, 8, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("Arial", "", 12)
    for _, row in df.iterrows():
        for val, w in zip(row, col_widths):
            pdf.cell(w, 8, str(val), border=1, align="C")
        pdf.ln()

    pdf.output(filename)
    return filename

# ----------------------------
# 6. STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="📅 Programma Giatron", layout="wide")
st.title("📅 Programma Giatron – Backwards Rotation")

for key in ["initial_week", "start_date", "end_date", "schedule", "balance"]:
    if key not in st.session_state:
        st.session_state[key] = None

left_col, right_col = st.columns([0.35, 0.65])

# LEFT: BALANCE
with left_col:
    st.subheader("📊 Balance (Range)")
    if st.session_state.balance is not None:
        st.dataframe(st.session_state.balance, use_container_width=True, height=260)

        if st.button("📄 Export Balance PDF"):
            pdf = create_balance_pdf(
                st.session_state.balance,
                st.session_state.start_date,
                st.session_state.end_date
            )
            with open(pdf, "rb") as f:
                st.download_button("⬇️ Download Balance PDF", f, file_name=pdf)

# RIGHT: MAIN FLOW
with right_col:
    selected_date = st.date_input("Pick a date in the initial week:", datetime.date.today())
    week_dates = get_week_dates(selected_date)

    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            initial_week[d] = st.selectbox(d.strftime("%a %d/%m"), DOCTORS, key=f"doc_{d}")

    if st.button("💾 Save Initial Week"):
        st.session_state.initial_week = [initial_week[d] for d in sorted(initial_week)]
        st.session_state.start_date = week_dates[0]

    if st.session_state.initial_week is None:
        st.stop()

    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start date", st.session_state.start_date)
    with c2:
        end_date = st.date_input("End date", st.session_state.start_date + datetime.timedelta(days=30))

    if st.button("🗓️ Generate Schedule"):
        st.session_state.start_date = start_date
        st.session_state.end_date = end_date

        st.session_state.schedule = generate_schedule(
            st.session_state.initial_week, start_date, end_date
        )

        # ✅ balance computed immediately
        st.session_state.balance = compute_balance(
            st.session_state.schedule
        )
