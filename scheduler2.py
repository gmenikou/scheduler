# doctor_shift_scheduler_streamlit_full.py
import streamlit as st
from datetime import date, timedelta, datetime
import calendar
import pickle
import pandas as pd

st.set_page_config(page_title="Προγραμματιστής Εφημεριών", layout="wide")

# --- Session state ---
if 'initial_week' not in st.session_state:
    st.session_state.initial_week = {}
if 'ref_monday' not in st.session_state:
    st.session_state.ref_monday = None
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]

# --- Επιλογή αρχικής εβδομάδας ---
st.title("Αρχική Εβδομάδα - Χειροκίνητη Ανάθεση")
ref_monday = st.date_input("Επέλεξε Δευτέρα αρχικής εβδομάδας", value=st.session_state.ref_monday or date.today())
st.session_state.ref_monday = ref_monday
week_dates = [ref_monday + timedelta(days=i) for i in range(7)]

# --- Dropdowns για κάθε ημέρα ---
st.subheader("Ανάθεση γιατρών ανά ημέρα")
cols = st.columns(7)
for i,d in enumerate(week_dates):
    current_doc = st.session_state.initial_week.get(d,"")
    selected_doc = cols[i].selectbox(f"{calendar.day_name[d.weekday()]} {d.isoformat()}", [""] + st.session_state.doctors,
                                     index=(st.session_state.doctors.index(current_doc)+1 if current_doc else 0),
                                     key=f"init_{i}")
    if selected_doc:
        st.session_state.initial_week[d] = selected_doc

# --- Αποθήκευση ---
if st.button("Αποθήκευση Αρχικής Εβδομάδας"):
    with open("initial_week.pkl","wb") as f:
        pickle.dump({d.isoformat():doc for d,doc in st.session_state.initial_week.items()}, f)
    st.success("Αρχική εβδομάδα αποθηκεύτηκε")

# --- Reset ---
if st.button("Reset Αρχικής Εβδομάδας"):
    st.session_state.initial_week = {}
    st.session_state.ref_monday = None
    try:
        import os
        os.remove("initial_week.pkl")
    except:
        pass
    st.success("Αρχική εβδομάδα διαγράφηκε")

# --- Προβολή αρχικής εβδομάδας ---
if st.session_state.initial_week:
    st.subheader("Αρχική Εβδομάδα")
    df_week = pd.DataFrame({"Ημερομηνία":list(st.session_state.initial_week.keys()),
                            "Ημέρα":[calendar.day_name[d.weekday()] for d in st.session_state.initial_week.keys()],
                            "Γιατρός":[st.session_state.initial_week[d] for d in st.session_state.initial_week.keys()]})
    st.dataframe(df_week)

# ---------------------------
# Γέμισμα μήνα με rotation
st.subheader("Γέμισμα μήνα με rotation")

month = st.number_input("Μήνας", min_value=1, max_value=12, value=date.today().month)
year = st.number_input("Έτος", min_value=2000, max_value=2100, value=date.today().year)

def month_dates(year, month):
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    return [first + timedelta(days=i) for i in range(last_day)]

def populate_month(prev_assignments, initial_week, doctors, ref_monday, year, month):
    """Populate the month using backward 2-days-per-week rotation starting from initial_week."""
    if not initial_week:
        return {}
    assign_map = {}
    dates_in_month = month_dates(year, month)
    # sort dates
    dates_in_month.sort()
    # find initial assignment mapping weekday -> doctor
    week_start = ref_monday
    initial_assignments = {d.weekday():doc for d,doc in initial_week.items()}
    N = len(doctors)

    # for each date in month
    for d in dates_in_month:
        # calculate weeks offset from reference week
        weeks_offset = ((d - week_start).days)//7
        # calculate which weekday of rotation
        shift_day = (d.weekday() + 2*weeks_offset)%7  # backwards 2 days per week
        doc = initial_assignments.get(shift_day)
        if not doc:
            # fallback if somehow missing: rotate sequentially
            doc = doctors[(shift_day)%N]
        assign_map[d] = doc
    return assign_map

if st.button("Γέμισμα Μήνα"):
    if not st.session_state.initial_week:
        st.warning("Πρέπει να ορίσετε πρώτα την αρχική εβδομάδα!")
    else:
        month_assignments = populate_month(st.session_state.prev_assignments,
                                           st.session_state.initial_week,
                                           st.session_state.doctors,
                                           st.session_state.ref_monday,
                                           year, month)
        st.session_state.prev_assignments.update(month_assignments)
        st.success(f"Ο μήνας {calendar.month_name[month]} {year} γεμίστηκε με rotation")

# --- Προβολή μήνα ---
if st.session_state.prev_assignments:
    dates = month_dates(year, month)
    df_month = pd.DataFrame({"Ημερομηνία":dates,
                             "Ημέρα":[calendar.day_name[d.weekday()] for d in dates],
                             "Γιατρός":[st.session_state.prev_assignments[d] for d in dates]})
    st.subheader(f"Προγραμματισμός {calendar.month_name[month]} {year}")
    st.dataframe(df_month)
