# doctor_shift_scheduler_streamlit.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta, datetime
from collections import defaultdict
import pickle
from fpdf import FPDF

# ---------------------------
# Helper functions

def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def weekday_monday(d: date):
    return d - timedelta(days=d.weekday())

def weeks_in_month(year, month):
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    cur = weekday_monday(first)
    mondays = []
    while cur <= last:
        mondays.append(cur)
        cur += timedelta(days=7)
    return mondays

# ---------------------------
# Rotation logic
def populate_month_with_rotation(year, month, doctors, initial_week):
    """
    initial_week: dict {date: doctor} for the manually assigned first week
    """
    # collect first week's monday
    min_date = min(initial_week.keys())
    max_date = max(initial_week.keys())
    first_week_monday = weekday_monday(min_date)
    
    # assign_map starts with initial_week
    assign_map = initial_week.copy()
    N = len(doctors)

    # compute subsequent weeks
    mondays = weeks_in_month(year, month)
    for week_monday in mondays:
        # skip first week
        if week_monday >= first_week_monday and week_monday <= max_date:
            continue
        weeks_between = (week_monday - first_week_monday).days // 7
        for doc in doctors:
            # find doc's day in first week
            for d, ddoc in initial_week.items():
                if ddoc == doc:
                    ref_day = d.weekday()
                    break
            else:
                continue
            shift_weekday = (ref_day - 2*weeks_between) % 7
            shift_date = week_monday + timedelta(days=shift_weekday)
            if shift_date.month == month:
                assign_map[shift_date] = doc
    return assign_map

# ---------------------------
# Streamlit App

st.set_page_config(page_title="Doctor Shift Scheduler", layout="wide")

# Initialize session state
if 'initial_week' not in st.session_state:
    st.session_state.initial_week = {}  # {date: doctor}
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}  # cumulative
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)  # {(y,m): set(date)}
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []

st.title("Προγραμματιστής Εφημεριών Γιατρών")

# ---------------------------
# 1. Επιλογή αρχικής εβδομάδας χειροκίνητα
st.subheader("Επιλογή αρχικής εβδομάδας (χειροκίνητη)")

today = date.today()
start_of_week = weekday_monday(today)
week_dates = [start_of_week + timedelta(days=i) for i in range(7)]

# Prepare DataFrame for user selection
df_week = pd.DataFrame({
    "Ημερομηνία": week_dates,
    "Ημέρα": [calendar.day_name[d.weekday()] for d in week_dates],
    "Γιατρός": [st.session_state.initial_week.get(d,"") for d in week_dates]
})

edited_df = st.experimental_data_editor(df_week, key="initial_week_editor", num_rows="fixed")

if st.button("Αποθήκευση Αρχικής Εβδομάδας"):
    for idx, row in edited_df.iterrows():
        if row["Γιατρός"] in st.session_state.doctors:
            st.session_state.initial_week[row["Ημερομηνία"]] = row["Γιατρός"]
    st.success("Αρχική εβδομάδα αποθηκεύτηκε.")

if st.button("Reset Αρχικής Εβδομάδας"):
    st.session_state.initial_week = {}
    st.success("Αρχική εβδομάδα διαγράφηκε.")

# ---------------------------
# 2. Επιλογή μήνα προς γέμισμα
st.subheader("Γέμισμα Μήνα")
year = st.number_input("Έτος", min_value=2000, max_value=2100, value=today.year)
month = st.selectbox("Μήνας", list(range(1,13)), index=today.month-1)

if st.button("Γέμισμα μήνα με κανόνες περιστροφής"):
    if not st.session_state.initial_week:
        st.warning("Πρέπει να ορίσετε αρχική εβδομάδα πρώτα.")
    else:
        assign_map = populate_month_with_rotation(year, month, st.session_state.doctors, st.session_state.initial_week)
        st.session_state.prev_assignments.update(assign_map)
        if (year, month) not in st.session_state.generated_months:
            st.session_state.generated_months.append((year, month))
        st.success(f"Μήνας {calendar.month_name[month]} {year} γέμισε με βάση την αρχική εβδομάδα.")

# ---------------------------
# 3. Επιλογή αργιών
st.subheader("Χειρισμός Αργιών")
if st.session_state.generated_months:
    selected_ym = st.selectbox("Επιλέξτε μήνα για αργίες", st.session_state.generated_months)
    y,m = selected_ym
    dates = month_dates(y,m)
    date_strs = [d.isoformat() + " - " + calendar.day_name[d.weekday()] for d in dates]
    default_hols = [d.isoformat() + " - " + calendar.day_name[d.weekday()] for d in st.session_state.holidays.get(selected_ym,set())]
    hol_selection = st.multiselect("Επιλογή αργιών", date_strs, default=default_hols)
    date_map = {date_strs[i]: dates[i] for i in range(len(dates))}
    if st.button("Apply Holidays"):
        st.session_state.holidays[selected_ym] = set(date_map[s] for s in hol_selection)
        st.success("Αργίες εφαρμοσμένες.")

# ---------------------------
# 4. Προβολή προγράμματος και balance
if st.session_state.generated_months:
    selected_ym = st.selectbox("Προβολή μήνα", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)
    rows = []
    for d in dates:
        doc = st.session_state.prev_assignments.get(d,"")
        hol = "Yes" if d in st.session_state.holidays.get(selected_ym,set()) else ""
        rows.append({"Ημερομηνία":d, "Ημέρα":calendar.day_name[d.weekday()], "Γιατρός":doc, "Αργία":hol})
    df_month = pd.DataFrame(rows)
    st.dataframe(df_month, height=400)

    # balance panel
    balance_rows = []
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_non_weekday = 0
        for (ym_k, holset) in st.session_state.holidays.items():
            for hd in holset:
                if st.session_state.prev_assignments.get(hd) == doc and hd.weekday() not in (5,6):
                    hol_non_weekday += 1
        balance_rows.append({"Γιατρός":doc,"Παρασκευή":fr,"Σάββατο":sa,"Κυριακή":su,"Αργίες (μη Σ/Κ)":hol_non_weekday})
    st.subheader("Balance Panel")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Γιατρός"))

# ---------------------------
# 5. Εκτύπωση σε PDF
st.subheader("Εκτύπωση PDF")
if st.button("Print to PDF"):
    if not st.session_state.generated_months:
        st.warning("Δεν υπάρχουν δεδομένα για εκτύπωση.")
    else:
        ym = st.session_state.generated_months[-1]
        y,m = ym
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0,10,f"Πρόγραμμα {calendar.month_name[m]} {y}", ln=1, align="C")
        pdf.set_font("Arial","",12)
        dates = month_dates(y,m)
        for d in dates:
            doc = st.session_state.prev_assignments.get(d,"")
            hol = " (Αργία)" if d in st.session_state.holidays.get(ym,set()) else ""
            pdf.cell(0,8,f"{d.isoformat()} {calendar.day_name[d.weekday()]}: {doc}{hol}", ln=1)
        pdf.output("schedule.pdf")
        st.success("PDF δημιουργήθηκε: schedule.pdf")
