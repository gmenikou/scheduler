# doctor_shift_scheduler_streamlit_pdf.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
from collections import defaultdict
import calendar
import pickle
from fpdf import FPDF
import io

# ---------------------------
# Helper functions

def week_dates(start_date):
    return [start_date + timedelta(days=i) for i in range(7)]

def assign_backwards_rotation(initial_week_assignments, doctors, target_dates):
    N = len(doctors)
    first_week_dates = sorted(initial_week_assignments.keys())
    ref_date = first_week_dates[0]
    ref_doc = initial_week_assignments[ref_date]
    ref_index = doctors.index(ref_doc)
    prev_assignments = initial_week_assignments.copy()

    last_date = max(first_week_dates)
    remaining_dates = [d for d in target_dates if d > last_date]

    for i, d in enumerate(remaining_dates):
        # backward rotation 2 days/week per doctor
        week_offset = (d - last_date).days // 7
        doc_idx = (ref_index + week_offset) % N
        doc = doctors[doc_idx]
        prev_assignments[d] = doc

    return prev_assignments

def month_dates(year, month):
    from calendar import monthrange
    first = date(year, month, 1)
    _, last_day = monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def create_pdf(schedule_df, holidays_set, balance_df, month_name, year):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Πρόγραμμα Ιατρών — {month_name} {year}", ln=True, align='C')
    pdf.ln(5)

    # Schedule Table
    pdf.set_font("Arial", "B", 12)
    pdf.cell(40, 8, "Ημερομηνία", 1)
    pdf.cell(35, 8, "Ημέρα", 1)
    pdf.cell(50, 8, "Γιατρός", 1)
    pdf.cell(50, 8, "Αργία", 1)
    pdf.ln()
    pdf.set_font("Arial", "", 12)

    for idx, row in schedule_df.iterrows():
        pdf.cell(40, 8, row['Ημερομηνία'].strftime("%d/%m/%Y"), 1)
        pdf.cell(35, 8, row['Ημέρα'], 1)
        pdf.cell(50, 8, row['Γιατρός'], 1)
        pdf.cell(50, 8, "Ναι" if row['Ημερομηνία'] in holidays_set else "", 1)
        pdf.ln()

    pdf.ln(5)
    # Balance table
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Πίνακας Ισορροπίας", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "B", 12)
    # headers
    col_w = 38
    for col in balance_df.columns:
        pdf.cell(col_w, 8, str(col), 1)
    pdf.ln()
    pdf.set_font("Arial", "", 12)
    for idx, row in balance_df.iterrows():
        for col in balance_df.columns:
            pdf.cell(col_w, 8, str(row[col]), 1)
        pdf.ln()

    # Return PDF bytes
    pdf_bytes = pdf.output(dest='S').encode('latin1')
    return pdf_bytes

# ---------------------------
# Session State
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}
if 'initial_week' not in st.session_state:
    st.session_state.initial_week = {}
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []

st.title("Προγραμματιστής Βαριδιών Ιατρών — Περιστροφή 2 ημερών")

# ---------------------------
# Initial week manual assignment
st.subheader("Αρχική Εβδομάδα")
initial_monday = st.date_input("Επιλέξτε Δευτέρα αρχικής εβδομάδας:", value=date(2026,1,12))
week_dates_list = week_dates(initial_monday)
week_df = pd.DataFrame({
    "Ημερομηνία": week_dates_list,
    "Ημέρα": [calendar.day_name[d.weekday()] for d in week_dates_list],
    "Γιατρός": [st.session_state.initial_week.get(d,"") for d in week_dates_list]
})
st.write("Αναθέστε χειροκίνητα γιατρό ανά ημέρα:")
edited_df = st.data_editor(week_df, key="initial_week_editor")
if st.button("Αποθήκευση αρχικής εβδομάδας"):
    for idx, row in edited_df.iterrows():
        st.session_state.initial_week[row["Ημερομηνία"]] = row["Γιατρός"]
    st.session_state.prev_assignments.update(st.session_state.initial_week)
    st.success("Αρχική εβδομάδα αποθηκεύτηκε")

# ---------------------------
# Generate month
st.subheader("Γεννήστε πρόγραμμα μήνα")
year = st.number_input("Έτος", min_value=2000, max_value=2100, value=date.today().year)
month = st.selectbox("Μήνας", list(range(1,13)), index=date.today().month-1)

if st.button("Γεννήστε πρόγραμμα"):
    all_dates = month_dates(year, month)
    assignments = assign_backwards_rotation(st.session_state.initial_week, st.session_state.doctors, all_dates)
    st.session_state.prev_assignments.update(assignments)
    st.success(f"Πρόγραμμα για {calendar.month_name[month]} {year} δημιουργήθηκε")

# ---------------------------
# Display schedule & holidays
if st.session_state.prev_assignments:
    sorted_dates = sorted([d for d in st.session_state.prev_assignments if d.month==month and d.year==year])
    schedule_df = pd.DataFrame({
        "Ημερομηνία": sorted_dates,
        "Ημέρα": [calendar.day_name[d.weekday()] for d in sorted_dates],
        "Γιατρός": [st.session_state.prev_assignments[d] for d in sorted_dates]
    })

    st.subheader(f"Πρόγραμμα {calendar.month_name[month]} {year}")
    # Holidays selection
    holiday_selection = st.multiselect("Αργίες", sorted_dates, default=list(st.session_state.holidays.get((year,month),set())))
    st.session_state.holidays[(year,month)] = set(holiday_selection)

    schedule_df['Αργία'] = schedule_df['Ημερομηνία'].apply(lambda d: "Ναι" if d in st.session_state.holidays[(year,month)] else "")
    st.dataframe(schedule_df, height=400)

    # Balance
    balance_rows = []
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_non_weekday = sum(1 for hd in st.session_state.holidays.get((year,month),set())
                              if st.session_state.prev_assignments.get(hd)==doc and hd.weekday() not in (5,6))
        balance_rows.append({"Γιατρός":doc,"Παρασκευή":fr,"Σάββατο":sa,"Κυριακή":su,"Αργίες (μη Σ/Κ)":hol_non_weekday})
    balance_df = pd.DataFrame(balance_rows).set_index("Γιατρός")
    st.subheader("Πίνακας ισορροπίας")
    st.dataframe(balance_df)

    # ---------------------------
    # PDF Export
    if st.button("Εξαγωγή PDF"):
        pdf_bytes = create_pdf(schedule_df, st.session_state.holidays[(year,month)], balance_df, calendar.month_name[month], year)
        st.download_button(label="Κατέβασμα PDF", data=pdf_bytes, file_name=f"schedule_{year}_{month}.pdf", mime="application/pdf")
        st.success("PDF έτοιμο για κατέβασμα!")
