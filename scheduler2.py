# doctor_shift_scheduler_streamlit.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta, datetime
from collections import defaultdict
from fpdf import FPDF
import pickle

# ---------------------------
# Helper Functions
# ---------------------------

def get_current_week_dates(reference=None):
    """Return list of 7 dates for current week Monday-Sunday."""
    today = reference or date.today()
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]

def all_dates_in_month(year, month):
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    return [first + timedelta(days=i) for i in range(last_day)]

def assign_backwards_rotation(initial_week_assignments, doctors, all_dates):
    """Propagate backwards-2-day rotation from initial week."""
    assign_map = {}
    # find reference index per doctor
    ref_index = {doc: i for i, doc in enumerate(doctors)}
    # order of doctors in initial week
    week_doctors = [initial_week_assignments[d] for d in sorted(initial_week_assignments)]
    initial_dates = sorted(initial_week_assignments)
    if len(week_doctors) != 7:
        st.error("Πρέπει να έχετε ορίσει και τους 7 γιατρούς για την αρχική εβδομάδα!")
        return {}
    # Map each doctor to their reference weekday
    ref_doc_day = {week_doctors[i]: initial_dates[i] for i in range(7)}
    
    for d in all_dates:
        # Find which doctor should be assigned on this date
        # Calculate weeks difference from the reference week
        delta_days = (d - initial_dates[0]).days
        weeks_diff = delta_days // 7
        # Weekday rotation: backward 2 days per week
        weekday_offset = (delta_days % 7)
        for doc in doctors:
            ref_day = ref_doc_day[doc]
            ref_wd = ref_day.weekday()
            target_wd = (ref_wd - 2*weeks_diff) % 7
            if d.weekday() == target_wd:
                assign_map[d] = doc
    return assign_map

# ---------------------------
# Streamlit App
# ---------------------------

st.set_page_config(page_title="Προγραμματισμός Εφημεριών", layout="wide")

# Initialize session state
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}  # {date: doctor}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)  # {(y,m): set(date objects)}
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Έλενα","Εύα","Μαρία","Αθηνά","Αλέξανδρος","Έλια","Χριστίνα"]
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []  # list of (year,month)
if 'initial_week' not in st.session_state:
    st.session_state.initial_week = {}  # {date: doctor}

st.title("Προγραμματισμός Εφημεριών — Πίσω 2 ημέρες ανά εβδομάδα")

# ---------------------------
# User selects initial week
# ---------------------------
st.subheader("Επιλογή αρχικής εβδομάδας για χειροκίνητη ανάθεση")
week_ref_date = st.date_input("Επιλέξτε ημερομηνία αναφοράς για εβδομάδα", value=date.today())
week_dates = get_current_week_dates(week_ref_date)

week_df = pd.DataFrame({
    "Ημέρα": [calendar.day_name[d.weekday()] for d in week_dates],
    "Ημερομηνία": week_dates,
    "Γιατρός": [st.session_state.initial_week.get(d,"") for d in week_dates]
})

edited_df = st.experimental_data_editor(week_df, key="initial_week_editor", num_rows="fixed")

# Save initial week assignment
if st.button("Αποθήκευση αρχικής εβδομάδας"):
    for idx,row in edited_df.iterrows():
        if row["Γιατρός"] not in st.session_state.doctors:
            st.error(f"Ο γιατρός '{row['Γιατρός']}' δεν είναι στη λίστα γιατρών.")
            break
        st.session_state.initial_week[row["Ημερομηνία"]] = row["Γιατρός"]
    st.success("Η αρχική εβδομάδα αποθηκεύτηκε.")

# ---------------------------
# Generate schedule for selected month
# ---------------------------
st.subheader("Γεννήτρια εφημεριών για μήνα")
col1,col2 = st.columns(2)
with col1:
    year = st.number_input("Έτος", min_value=2000,max_value=2100,value=date.today().year)
    month = st.selectbox("Μήνας", list(range(1,13)), index=date.today().month-1)
with col2:
    if st.button("Γεννήστε εφημερίες"):
        ym = (year,month)
        dates = all_dates_in_month(year, month)
        assign_map = assign_backwards_rotation(st.session_state.initial_week, st.session_state.doctors, dates)
        st.session_state.prev_assignments.update(assign_map)
        if ym not in st.session_state.generated_months:
            st.session_state.generated_months.append(ym)
        st.success(f"Εφημερίες για {calendar.month_name[month]} {year} δημιουργήθηκαν.")

# ---------------------------
# View generated month & holidays
# ---------------------------
if st.session_state.generated_months:
    selected_ym = st.selectbox("Επιλέξτε μήνα για προβολή", st.session_state.generated_months)
    y,m = selected_ym
    dates = all_dates_in_month(y,m)
    df_rows = []
    for d in dates:
        doc = st.session_state.prev_assignments.get(d,"")
        hol = "Ναι" if d in st.session_state.holidays[selected_ym] else ""
        df_rows.append({"Ημερομηνία":d,"Ημέρα":calendar.day_name[d.weekday()],"Γιατρός":doc,"Αργία":hol})
    df = pd.DataFrame(df_rows)
    st.dataframe(df, height=500)

    # Select holidays interactively
    hol_dates = st.multiselect("Επιλέξτε αργίες (δεν επηρεάζουν εναλλαγή)", dates, default=list(st.session_state.holidays[selected_ym]))
    if st.button("Εφαρμογή αργιών"):
        st.session_state.holidays[selected_ym] = set(hol_dates)
        st.success("Οι αργίες εφαρμόστηκαν.")

    # Balance panel
    balance_rows = []
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_nonweek = 0
        for (ym_k,holset) in st.session_state.holidays.items():
            for hd in holset:
                if st.session_state.prev_assignments.get(hd)==doc and hd.weekday() not in (5,6):
                    hol_nonweek +=1
        balance_rows.append({"Γιατρός":doc,"Παρασκευές":fr,"Σάββατα":sa,"Κυριακές":su,"Αργίες (μη Σ/Κ)":hol_nonweek})
    st.subheader("Πίνακας ισορροπίας")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Γιατρός"))

# ---------------------------
# PDF export
# ---------------------------
st.subheader("Εξαγωγή PDF")
if st.button("Εκτύπωση PDF"):
    if not st.session_state.generated_months:
        st.warning("Δεν υπάρχουν δεδομένα για εκτύπωση.")
    else:
        selected_ym = st.session_state.generated_months[-1]
        y,m = selected_ym
        dates = all_dates_in_month(y,m)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial","B",14)
        pdf.cell(0,10,f"Εφημερίες {calendar.month_name[m]} {y}",ln=True,align="C")
        pdf.ln(5)
        pdf.set_font("Arial","",12)
        for d in dates:
            doc = st.session_state.prev_assignments.get(d,"")
            hol = " (Αργία)" if d in st.session_state.holidays.get(selected_ym,set()) else ""
            pdf.cell(0,8,f"{d} - {calendar.day_name[d.weekday()]}: {doc}{hol}",ln=True)
        pdf_file = f"schedule_{y}_{m}.pdf"
        pdf.output(pdf_file)
        st.success(f"PDF δημιουργήθηκε: {pdf_file}")
        st.download_button("Κατέβασμα PDF", pdf_file, file_name=pdf_file)
