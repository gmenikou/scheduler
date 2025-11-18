import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from collections import defaultdict

# ---------------------------
# Helper Functions

def week_range(start_date):
    """Return list of 7 dates for the week starting from Monday of the week containing start_date."""
    monday = start_date - timedelta(days=start_date.weekday())
    return [monday + timedelta(days=i) for i in range(7)]

def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def populate_rotation(first_week_assignment, doctors, start_date, target_dates):
    """Populate assignments based on backward 2-day rotation rule."""
    N = len(doctors)
    ref_week_dates = sorted(first_week_assignment.keys())
    ref_week_monday = min(ref_week_dates)
    ref_doc_list = [first_week_assignment[d] for d in ref_week_dates]

    assign_map = {}
    for d in target_dates:
        days_diff = (d - ref_week_monday).days
        week_offset = days_diff // 7
        day_idx = days_diff % 7
        ref_doc_idx = doctors.index(ref_doc_list[day_idx])
        assign_map[d] = doctors[(ref_doc_idx + week_offset) % N]
    return assign_map

# ---------------------------
# Session state

if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'first_week_assigned' not in st.session_state:
    st.session_state.first_week_assigned = {}
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []

# ---------------------------
# UI: Titles

st.title("Προγραμματισμός Βαρδιών Ιατρών — Περιστροφή 2 ημέρες")
st.markdown("Ορισμός Αρχικής Εβδομάδας και αυτόματη συμπλήρωση υπόλοιπων ημερών του μήνα.")

# ---------------------------
# Manual First-Week Assignment

st.subheader("Χειροκίνητος ορισμός πρώτης εβδομάδας")
first_week_start = st.date_input("Δευτέρα πρώτης εβδομάδας", value=date(2026,1,12))
first_week_dates = week_range(first_week_start)

new_assignment = {}
for d in first_week_dates:
    col1, col2 = st.columns([2,3])
    with col1:
        st.write(f"{d} ({calendar.day_name[d.weekday()]})")
    with col2:
        current_doc = st.session_state.first_week_assigned.get(d, st.session_state.doctors[0])
        new_assignment[d] = st.selectbox(f"Ιατρός {d}", st.session_state.doctors,
                                         index=st.session_state.doctors.index(current_doc),
                                         key=str(d))

if st.button("Αποθήκευση Αρχικής Εβδομάδας"):
    st.session_state.first_week_assigned.update(new_assignment)
    st.success("Αρχική εβδομάδα αποθηκεύτηκε.")

# ---------------------------
# Generate Month

st.subheader("Δημιουργία Βαρδιών Μήνα")
col_year, col_month, col_generate = st.columns([1,1,1])
year = col_year.number_input("Έτος", min_value=2000, max_value=2100, value=2026)
month = col_month.selectbox("Μήνας", list(range(1,13)), index=0)

if col_generate.button("Δημιουργία Μήνα"):
    month_all_dates = month_dates(year, month)
    assign_map = populate_rotation(st.session_state.first_week_assigned,
                                   st.session_state.doctors,
                                   first_week_start,
                                   month_all_dates)
    st.session_state.prev_assignments.update(assign_map)
    ym = (year, month)
    if ym not in st.session_state.generated_months:
        st.session_state.generated_months.append(ym)
    st.success(f"Βάρδιες για {calendar.month_name[month]} {year} δημιουργήθηκαν.")

# ---------------------------
# Month Viewer, Holidays, and Balance

st.markdown("---")
if st.session_state.generated_months:
    selected_ym = st.selectbox("Προβολή μήνα", st.session_state.generated_months,
                               index=len(st.session_state.generated_months)-1)
    y, m = selected_ym
    dates = month_dates(y, m)

    # Toggle Holidays
    st.subheader(f"Βάρδιες για {calendar.month_name[m]} {y}")
    default_hols = list(st.session_state.holidays.get(selected_ym, []))
    date_strs = [d.isoformat() + " - " + calendar.day_name[d.weekday()] for d in dates]
    date_map = {date_strs[i]: dates[i] for i in range(len(dates))}
    selected_defaults = [s.isoformat() + " - " + calendar.day_name[s.weekday()] for s in default_hols if s in dates]
    hol_selection = st.multiselect("Σήμανση Αργιών (δεν επηρεάζει περιστροφή)", date_strs,
                                   default=selected_defaults)
    st.session_state.holidays[selected_ym] = set(date_map[s] for s in hol_selection)

    # Display table
    rows = []
    for d in dates:
        doc = st.session_state.prev_assignments.get(d, "")
        is_hol = d in st.session_state.holidays.get(selected_ym, set())
        rows.append({
            "Ημερομηνία": d,
            "Ημέρα": calendar.day_name[d.weekday()],
            "Ιατρός": doc,
            "Αργία": "Ναι" if is_hol else ""
        })
    df = pd.DataFrame(rows)
    st.dataframe(df.style.applymap(lambda v: 'background-color: yellow' if v=="Ναι" else '', subset=['Αργία']),
                 height=500)

    # Balance Panel
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
        balance_rows.append({
            "Ιατρός": doc,
            "Παρασκευές": fr,
            "Σάββατα": sa,
            "Κυριακές": su,
            "Αργίες (εκτός Σ/Κ)": hol_non_weekday
        })
    st.subheader("Πίνακας Ισορροπίας")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Ιατρός"))
else:
    st.info("Δεν έχει δημιουργηθεί κανένας μήνας ακόμη.")
