# doctor_shift_scheduler_streamlit_full.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta, datetime
from collections import defaultdict, deque
import pickle
from fpdf import FPDF

# ---------------------------
# Helper functions

def week_dates(start_date):
    """Return 7 dates starting from start_date (assumed Monday)."""
    return [start_date + timedelta(days=i) for i in range(7)]

def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def assign_rotation(dates, doctors, first_week_assign):
    """
    Assign doctors according to backwards 2-day rotation,
    using first_week_assign as starting reference.
    """
    if not first_week_assign:
        return {}
    # Get list of first week dates in order
    first_week_dates = sorted(first_week_assign.keys())
    N = len(doctors)
    assign_map = {}
    # assign first week
    assign_map.update(first_week_assign)
    
    # Flatten list of all dates to assign
    all_dates = sorted(dates)
    
    # Determine rotation offsets based on first week
    # Create deque starting from first week assignments
    first_week_doctors = [first_week_assign[d] for d in first_week_dates]
    dq = deque(first_week_doctors)
    
    # Map from date to weekday number
    date_to_weekday = {d: d.weekday() for d in all_dates}
    
    # For each date outside first week, assign following backward 2-day rule
    for d in all_dates:
        if d in assign_map:
            continue
        # compute shift relative to last assigned date
        last_date = max(assign_map.keys())
        last_doc = assign_map[last_date]
        # Find index of last_doc in deque
        try:
            idx = dq.index(last_doc)
        except ValueError:
            idx = 0
        # rotate deque for backward 2-day rotation
        dq.rotate(-1)
        assign_map[d] = dq[0]
    return assign_map

# ---------------------------
# Streamlit App

st.set_page_config(page_title="Προγραμματιστής Βαρδιών Γιατρών", layout="wide")

# Initialize session state
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}  # {date: doctor}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)  # {(y,m): set(date)}
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []
if 'first_week_assign' not in st.session_state:
    st.session_state.first_week_assign = {}  # manual assignment

st.title("Προγραμματιστής Βαρδιών Γιατρών — Περιστροφή ανά 2 ημέρες")

# ---------------------------
# Επιλογή αρχικής εβδομάδας για χειροκίνητη ανάθεση

st.subheader("Επιλογή αρχικής εβδομάδας για χειροκίνητη ανάθεση")
initial_monday = st.date_input("Επιλέξτε Δευτέρα πρώτης εβδομάδας", value=date(2026,1,12))
week_dates_list = week_dates(initial_monday)
week_df = pd.DataFrame({
    "Ημερομηνία": week_dates_list,
    "Ημέρα": [calendar.day_name[d.weekday()] for d in week_dates_list],
    "Γιατρός": [st.session_state.first_week_assign.get(d,"") for d in week_dates_list]
})

edited_df = st.experimental_data_editor(week_df, key="initial_week_editor", num_rows="fixed")

if st.button("Αποθήκευση αρχικής εβδομάδας"):
    # Save manual assignments
    for i,row in edited_df.iterrows():
        if row["Γιατρός"] in st.session_state.doctors:
            st.session_state.first_week_assign[row["Ημερομηνία"]] = row["Γιατρός"]
    st.success("Η αρχική εβδομάδα αποθηκεύτηκε.")

if st.button("Reset Αρχικής Εβδομάδας"):
    st.session_state.first_week_assign = {}
    st.success("Η αρχική εβδομάδα καθαρίστηκε.")

# ---------------------------
# Επιλογή μήνα για παραγωγή βαρδιών

st.subheader("Παραγωγή βαρδιών για μήνα")
col1, col2 = st.columns(2)
with col1:
    year = st.number_input("Έτος", min_value=2000, max_value=2100, value=2026)
    month = st.selectbox("Μήνας", list(range(1,13)), index=0)

with col2:
    if st.button("Δημιουργία Βαρδιών"):
        dates = month_dates(year, month)
        assign_map = assign_rotation(dates, st.session_state.doctors, st.session_state.first_week_assign)
        st.session_state.prev_assignments.update(assign_map)
        ym = (year, month)
        if ym not in st.session_state.generated_months:
            st.session_state.generated_months.append(ym)
        st.success(f"Βάρδιες δημιουργήθηκαν για {calendar.month_name[month]} {year}")

# ---------------------------
# Διαχείριση διακοπών

if st.session_state.generated_months:
    selected_ym = st.selectbox("Επιλέξτε μήνα για προβολή/διαχείριση", st.session_state.generated_months)
    y,m = selected_ym
    dates = month_dates(y,m)

    st.subheader("Διαχείριση διακοπών")
    default_hols = list(st.session_state.holidays.get(selected_ym, []))
    date_strs = [d.isoformat()+" - "+calendar.day_name[d.weekday()] for d in dates]
    date_map = {date_strs[i]:dates[i] for i in range(len(dates))}
    selected_hols = st.multiselect("Επιλογή διακοπών", date_strs, default=[d.isoformat()+" - "+calendar.day_name[d.weekday()] for d in default_hols])
    if st.button("Εφαρμογή διακοπών"):
        st.session_state.holidays[selected_ym] = set(date_map[s] for s in selected_hols)
        st.success("Διακοπές εφαρμόστηκαν.")

# ---------------------------
# Προβολή βαρδιών & balances

if st.session_state.generated_months:
    ym = selected_ym
    y,m = ym
    dates = month_dates(y,m)
    df = pd.DataFrame({
        "Ημερομηνία": dates,
        "Ημέρα": [calendar.day_name[d.weekday()] for d in dates],
        "Γιατρός": [st.session_state.prev_assignments.get(d,"") for d in dates],
        "Διακοπή": ["Ναι" if d in st.session_state.holidays.get(ym,set()) else "" for d in dates]
    })
    st.dataframe(df, height=480)

    # Balance panel
    balance_rows = []
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_non_week = sum(1 for d in st.session_state.holidays.get(ym,set()) if st.session_state.prev_assignments.get(d)==doc and d.weekday() not in (5,6))
        balance_rows.append({"Γιατρός":doc,"Παρασκευές":fr,"Σάββατα":sa,"Κυριακές":su,"Διακοπές (μη Σ/Κ)":hol_non_week})
    st.subheader("Πίνακας ισορροπίας")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Γιατρός"))

# ---------------------------
# Εκτύπωση PDF

if st.button("Εκτύπωση PDF τρέχοντος μήνα"):
    if not st.session_state.generated_months:
        st.warning("Δεν έχει δημιουργηθεί μήνας ακόμα.")
    else:
        ym = st.session_state.generated_months[-1]
        y,m = ym
        dates = month_dates(y,m)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial","B",14)
        pdf.cell(0,10,f"Βάρδιες για {calendar.month_name[m]} {y}",0,1,"C")
        pdf.set_font("Arial","",12)
        for d in dates:
            doc = st.session_state.prev_assignments.get(d,"")
            hol = "Διακοπή" if d in st.session_state.holidays.get(ym,set()) else ""
            pdf.cell(0,8,f"{d.isoformat()} ({calendar.day_name[d.weekday()]}): {doc} {hol}",0,1)
        pdf_file = f"Βάρδιες_{y}_{m}.pdf"
        pdf.output(pdf_file)
        st.success(f"PDF δημιουργήθηκε: {pdf_file}")
        st.download_button("Κατέβασε PDF", pdf_file, file_name=pdf_file)
