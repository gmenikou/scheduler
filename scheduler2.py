import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from collections import defaultdict, deque

st.set_page_config(page_title="Προγραμματιστής Βαρδιών Ιατρών", layout="wide")

# --- State initialization ---
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}  # {date: doctor}
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []
if 'first_week_manual' not in st.session_state:
    st.session_state.first_week_manual = {}  # {date: doctor}

# --- Helper ---
def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def populate_rotation(dates, doctors, first_week_manual):
    N = len(doctors)
    assign_map = {}
    # sort dates
    dates = sorted(dates)
    # find first week dates
    first_week = sorted(first_week_manual.keys())
    if not first_week:
        return assign_map
    first_date = first_week[0]
    # reference doctor indices
    ref_index_map = {first_week_manual[d]: i for i,d in enumerate(first_week)}
    # assign first week manually
    for d,doc in first_week_manual.items():
        assign_map[d] = doc
    # now populate remaining dates forward
    prev_doc_idx = doctors.index(first_week_manual[first_week[-1]])
    prev_date = first_week[-1]
    for d in dates:
        if d in assign_map:
            continue
        # rotation: backward 2 days per week relative to previous assigned date
        delta_days = (d - prev_date).days
        shift_steps = delta_days // 7  # approximate weekly steps
        doc_idx = (prev_doc_idx + shift_steps) % N
        assign_map[d] = doctors[doc_idx]
        prev_date = d
        prev_doc_idx = doc_idx
    return assign_map

# --- Controls ---
st.title("Προγραμματισμός Βαρδιών Ιατρών")

col1, col2 = st.columns([2,1])

with col1:
    st.subheader("Επιλογή Μήνα")
    today = date.today()
    year = st.number_input("Έτος", min_value=2000, max_value=2100, value=today.year)
    month = st.selectbox("Μήνας", list(range(1,13)), index=today.month-1)
    dates = month_dates(year, month)
    
    # --- First week manual assignment ---
    st.subheader("Χειροκίνητη Ανάθεση Πρώτης Εβδομάδας")
    first_week_start = dates[0] - timedelta(days=dates[0].weekday())  # Monday
    first_week_dates = [first_week_start + timedelta(days=i) for i in range(7)]
    
    for d in first_week_dates:
        if d.month != month:
            continue
        key = f"first_week_{d}"
        default_doc = st.session_state.first_week_manual.get(d, st.session_state.doctors[0])
        selected_doc = st.selectbox(f"{d.isoformat()} ({calendar.day_name[d.weekday()]})", st.session_state.doctors, index=st.session_state.doctors.index(default_doc), key=key)
        st.session_state.first_week_manual[d] = selected_doc

with col2:
    st.subheader("Ενέργειες")
    if st.button("Δημιουργία Βαρδιών"):
        assign_map = populate_rotation(dates, st.session_state.doctors, st.session_state.first_week_manual)
        st.session_state.prev_assignments.update(assign_map)
        if (year,month) not in st.session_state.generated_months:
            st.session_state.generated_months.append((year,month))
        st.success(f"Η βάρδια για τον μήνα {calendar.month_name[month]} {year} δημιουργήθηκε!")

    if st.button("Επαναφορά Όλων"):
        st.session_state.prev_assignments.clear()
        st.session_state.generated_months.clear()
        st.session_state.first_week_manual.clear()
        st.success("Επαναφορά ολοκληρώθηκε")

# --- Display ---
if st.session_state.generated_months:
    st.subheader("Προβολή Βαρδιών")
    selected_ym = st.selectbox("Επιλέξτε μήνα", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)
    df_rows = []
    for d in dates:
        df_rows.append({
            "Ημερομηνία": d.isoformat(),
            "Ημέρα": calendar.day_name[d.weekday()],
            "Ιατρός": st.session_state.prev_assignments.get(d,"")
        })
    df = pd.DataFrame(df_rows)
    st.dataframe(df, height=480)
