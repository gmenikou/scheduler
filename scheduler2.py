# doctor_shift_scheduler_streamlit_grid.py
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

def propagate_rotation(first_week_assignment, start_date, doctors, target_dates):
    assignments = {}
    first_week_dates = sorted(first_week_assignment.keys())
    ref_date = first_week_dates[0]
    ref_assignment = {d:first_week_assignment[d] for d in first_week_dates}

    for d in target_dates:
        week_offset = (weekday_monday(d) - weekday_monday(ref_date)).days // 7
        day_offset = (d - weekday_monday(d)).days
        found = False
        for fw_day, doc in ref_assignment.items():
            fw_weekday = (fw_day - weekday_monday(fw_day)).days
            rotated_weekday = (fw_weekday - 2*week_offset)%7
            if rotated_weekday == day_offset:
                assignments[d] = doc
                found = True
                break
        if not found:
            assignments[d] = doctors[0]
    return assignments

# ---------------------------
# Streamlit App
st.set_page_config(page_title="Πρόγραμμα Ιατρών", layout="wide")

if 'first_week_assignment' not in st.session_state:
    st.session_state.first_week_assignment = {}
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]

st.title("Πρόγραμμα Ιατρών — Περιστροφή 2 ημερών ανά εβδομάδα")

# ---------------------------
# Determine first week dynamically
today = date.today()
monday_of_week = weekday_monday(today)
week_dates = [monday_of_week + timedelta(days=i) for i in range(7)]
st.subheader(f"Χειροκίνητη ανάθεση για την πρώτη εβδομάδα ({week_dates[0]} έως {week_dates[-1]})")

# Build a DataFrame for table selection
df_manual = pd.DataFrame({"Ημέρα":[calendar.day_name[d.weekday()] for d in week_dates],
                          "Ημερομηνία":[d.isoformat() for d in week_dates]})
for doc in st.session_state.doctors:
    df_manual[doc] = [False]*7

# Fill defaults if saved previously
for i,d in enumerate(week_dates):
    if d in st.session_state.first_week_assignment:
        assigned_doc = st.session_state.first_week_assignment[d]
        for doc in st.session_state.doctors:
            df_manual.at[i, doc] = (doc==assigned_doc)

# Display table with checkboxes (radio per row)
manual_assign = {}
for i, row in df_manual.iterrows():
    st.write(f"{row['Ημέρα']} - {row['Ημερομηνία']}")
    cols = st.columns(len(st.session_state.doctors))
    selected_doc = None
    for j, doc in enumerate(st.session_state.doctors):
        checked = row[doc]
        if cols[j].checkbox(doc, value=checked, key=f"{row['Ημερομηνία']}_{doc}"):
            selected_doc = doc
    if selected_doc:
        manual_assign[week_dates[i]] = selected_doc

if st.button("Αποθήκευση χειροκίνητης ανάθεσης"):
    if len(manual_assign) != 7:
        st.warning("Πρέπει να επιλέξετε έναν ιατρό για κάθε ημέρα.")
    else:
        st.session_state.first_week_assignment = manual_assign
        st.success("Αποθηκεύτηκε η πρώτη εβδομάδα.")

# ---------------------------
# Month selection
st.subheader("Δημιουργία προγράμματος μήνα")
year = st.number_input("Έτος", min_value=2000, max_value=2100, value=today.year)
month = st.selectbox("Μήνας", list(range(1,13)), index=today.month-1)

if st.button("Δημιουργία προγράμματος"):
    dates = month_dates(year, month)
    if not st.session_state.first_week_assignment:
        st.warning("Πρώτα ορίστε την αρχική εβδομάδα χειροκίνητα.")
    else:
        assign_map = propagate_rotation(st.session_state.first_week_assignment,
                                        week_dates[0], st.session_state.doctors, dates)
        st.session_state.prev_assignments.update(assign_map)
        ym = (year, month)
        if ym not in st.session_state.generated_months:
            st.session_state.generated_months.append(ym)
        st.success(f"Δημιουργήθηκε πρόγραμμα για τον μήνα {calendar.month_name[month]} {year}")

# ---------------------------
# Display month and balances
st.markdown("---")
if st.session_state.generated_months:
    selected_ym = st.selectbox("Επιλογή μήνα για προβολή", st.session_state.generated_months,
                               index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)
    rows=[]
    for d in dates:
        doc = st.session_state.prev_assignments.get(d,"")
        is_hol = d in st.session_state.holidays.get(selected_ym,set())
        rows.append({
            "Ημερομηνία":d,
            "Ημέρα":calendar.day_name[d.weekday()],
            "Ιατρός":doc,
            "Αργία": "Ναι" if is_hol else ""
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, height=480)

    # Balance panel
    balance_rows=[]
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_non_weekday=0
        for (ymk,holset) in st.session_state.holidays.items():
            for hd in holset:
                if st.session_state.prev_assignments.get(hd)==doc and hd.weekday() not in (5,6):
                    hol_non_weekday+=1
        balance_rows.append({
            "Ιατρός":doc,
            "Παρασκευή":fr,
            "Σάββατο":sa,
            "Κυριακή":su,
            "Αργίες (μη Σ/Κ)":hol_non_weekday
        })
    st.subheader("Πίνακας Ισορροπίας (συσσωρευτικός)")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Ιατρός"))
