# doctor_shift_scheduler_streamlit_full.py
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

def month_dates(year, month):
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    return [first + timedelta(days=i) for i in range(last_day)]

def week_start(d):
    """Return Monday of the week containing d."""
    return d - timedelta(days=d.weekday())

def week_dates(start_monday):
    """Return 7 dates from Monday to Sunday."""
    return [start_monday + timedelta(days=i) for i in range(7)]

def rotate_weekday(d, week_offset):
    """Backward 2-day rotation per week."""
    return (d - 2*week_offset) % 7

def propagate_schedule(initial_week_assign, initial_week_dates, doctors, month_dates_list):
    """
    Propagate the schedule forward and backward using rotation rules.
    initial_week_assign: dict {date: doctor} for manually assigned week.
    initial_week_dates: list of 7 dates of initial week.
    doctors: list of 7 doctors.
    month_dates_list: list of dates in the month.
    Returns {date: doctor} covering all month dates.
    """
    N = len(doctors)
    assign_map = {}
    # determine week offset from initial week for each date
    initial_monday = initial_week_dates[0]

    for d in month_dates_list:
        delta_weeks = (d - initial_monday).days // 7
        if delta_weeks >= 0:
            # forward propagation
            weekday_idx = (d.weekday() - 2*delta_weeks) % 7
        else:
            # backward propagation
            weekday_idx = (d.weekday() - 2*delta_weeks) % 7
        # assign doctor
        ref_date_in_week = initial_week_dates[d.weekday()]  # pick initial doctor for that weekday
        doc = initial_week_assign.get(ref_date_in_week, doctors[d.weekday()%N])
        assign_map[d] = doc
    return assign_map

# ---------------------------
# Streamlit App Setup

st.set_page_config(page_title="Πρόγραμμα Ιατρών", layout="wide")

# Session state initialization
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}  # {date: doctor}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)  # {(y,m): set of dates}
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []  # list of (year,month)
if 'initial_week' not in st.session_state:
    st.session_state.initial_week = {}  # {date: doctor}

# ---------------------------
# Controls

st.title("Πρόγραμμα Ιατρών — Περιστροφή 7 εβδομάδων")

col1, col2, col3 = st.columns([2,1,1])

with col1:
    st.subheader("Επιλογές Μήνα / Αρχική Εβδομάδα")
    year = st.number_input("Έτος", min_value=2000, max_value=2100, value=date.today().year)
    month = st.selectbox("Μήνας", list(range(1,13)), index=date.today().month-1)
    start_balance = st.checkbox("Επαναφορά ισορροπίας από αυτόν τον μήνα", value=False)

    # Determine current week dates
    today = date.today()
    this_week_monday = week_start(today)
    initial_week_dates = week_dates(this_week_monday)
    st.markdown("**Επιλογή αρχικής εβδομάδας για χειροκίνητη ανάθεση**")
    manual_week_choice = st.date_input("Δευτέρα της αρχικής εβδομάδας", value=this_week_monday)
    manual_week_dates = week_dates(week_start(manual_week_choice))

with col2:
    st.subheader("Χειρισμοί")
    if st.button("Αποθήκευση χειροκίνητης εβδομάδας"):
        # show small grid for manual assignment
        first_week_df = pd.DataFrame({
            calendar.day_name[d.weekday()]: [st.session_state.prev_assignments.get(d,"")] 
            for d in manual_week_dates
        }, index=[0])
        st.session_state.initial_week = {d: "" for d in manual_week_dates}
        st.success("Μπορείτε να εκχωρήσετε ιατρό ανά ημέρα παρακάτω και μετά να πατήσετε 'Εφαρμογή αρχικής εβδομάδας'")

    if 'first_week_df' in locals():
        edited_df = st.experimental_data_editor(first_week_df, num_rows="fixed", key="first_week_editor")
        if st.button("Εφαρμογή αρχικής εβδομάδας"):
            for i,d in enumerate(manual_week_dates):
                st.session_state.initial_week[d] = edited_df.iloc[0,i]
            st.success("Αρχική εβδομάδα αποθηκεύτηκε. Η περιστροφή θα προχωρήσει αυτόματα.")

with col3:
    st.subheader("Ενέργειες")
    if st.button("Επαναφορά Όλων"):
        st.session_state.prev_assignments.clear()
        st.session_state.holidays.clear()
        st.session_state.generated_months.clear()
        st.session_state.initial_week.clear()
        st.success("Όλα επαναφέρθηκαν.")

    if st.button("Εκτύπωση PDF μήνα"):
        if (year,month) not in st.session_state.generated_months:
            st.warning("Δεν έχει δημιουργηθεί πρόγραμμα για αυτόν τον μήνα.")
        else:
            dates = month_dates(year, month)
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0,10,f"Πρόγραμμα Ιατρών {calendar.month_name[month]} {year}", ln=1)
            pdf.set_font("Arial","",12)
            for d in dates:
                doc = st.session_state.prev_assignments.get(d,"")
                hol_flag = " (Αργία)" if d in st.session_state.holidays.get((year,month),set()) else ""
                pdf.cell(0,8,f"{d.isoformat()} {calendar.day_name[d.weekday()]}: {doc}{hol_flag}", ln=1)
            pdf.output("schedule.pdf")
            st.success("Το PDF δημιουργήθηκε: schedule.pdf")

# ---------------------------
# Generate schedule

if st.button("Δημιουργία προγράμματος μήνα"):
    dates = month_dates(year, month)
    if start_balance:
        st.session_state.prev_assignments.clear()
        st.session_state.generated_months.clear()

    if st.session_state.initial_week:
        assign_map = propagate_schedule(st.session_state.initial_week, list(st.session_state.initial_week.keys()),
                                        st.session_state.doctors, dates)
    else:
        st.warning("Πρέπει πρώτα να ορίσετε χειροκίνητα την αρχική εβδομάδα.")
        assign_map = {}
    st.session_state.prev_assignments.update(assign_map)
    if (year,month) not in st.session_state.generated_months:
        st.session_state.generated_months.append((year,month))
    st.success(f"Πρόγραμμα για {calendar.month_name[month]} {year} δημιουργήθηκε.")

# ---------------------------
# View month, holidays, balance

if st.session_state.generated_months:
    selected_ym = st.selectbox("Προβολή μήνα", st.session_state.generated_months)
    y,m = selected_ym
    dates = month_dates(y,m)

    # Holidays selection
    st.subheader(f"Πρόγραμμα για {calendar.month_name[m]} {y}")
    holiday_options = [d.isoformat()+" - "+calendar.day_name[d.weekday()] for d in dates]
    holiday_map = {d.isoformat()+" - "+calendar.day_name[d.weekday()]: d for d in dates}
    selected_holidays = st.multiselect("Ορισμός αργιών (δεν επηρεάζουν την περιστροφή)", holiday_options,
                                       default=[d.isoformat()+" - "+calendar.day_name[d.weekday()] for d in st.session_state.holidays.get((y,m),set())])
    st.session_state.holidays[(y,m)] = set(holiday_map[s] for s in selected_holidays)

    # Show table
    table_data = []
    for d in dates:
        table_data.append({
            "Ημερομηνία": d,
            "Ημέρα": calendar.day_name[d.weekday()],
            "Ιατρός": st.session_state.prev_assignments.get(d,""),
            "Αργία": "Ναι" if d in st.session_state.holidays.get((y,m),set()) else ""
        })
    df = pd.DataFrame(table_data)
    st.dataframe(df, height=480)

    # Balance panel
    balance_rows = []
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_non_weekday = sum(1 for (ym_k, holset) in st.session_state.holidays.items()
                              for hd in holset
                              if st.session_state.prev_assignments.get(hd)==doc and hd.weekday() not in (5,6))
        balance_rows.append({
            "Ιατρός": doc,
            "Παρασκευές": fr,
            "Σάββατα": sa,
            "Κυριακές": su,
            "Αργίες (εκτός Σαββατοκύριακου)": hol_non_weekday
        })
    st.subheader("Πίνακας Ισορροπίας (συσσωρευτικά)")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Ιατρός"))
