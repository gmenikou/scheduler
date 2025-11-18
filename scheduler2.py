import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from collections import defaultdict

st.set_page_config(page_title="Προγραμματιστής Βαρδιών Ιατρών", layout="wide")

# -----------------------
# Session State Init
# -----------------------
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}  # {date: doctor}
if 'first_week_manual' not in st.session_state:
    st.session_state.first_week_manual = {}  # {date: doctor}
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []

# -----------------------
# Helper Functions
# -----------------------
def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def populate_rotation(dates, doctors, first_week_manual):
    """
    Given a manual first week assignment, populate the rest of the month
    forward and backward according to the backward-2-day-per-week rotation.
    """
    if not first_week_manual:
        return {}

    N = len(doctors)
    assign_map = {}

    # Sort dates
    dates_sorted = sorted(dates)
    first_week_dates = sorted(first_week_manual.keys())

    # Assign first week manually
    for d in first_week_dates:
        assign_map[d] = first_week_manual[d]

    # Compute forward rotation
    prev_date = first_week_dates[-1]
    prev_doc_idx = doctors.index(first_week_manual[prev_date])

    for d in dates_sorted:
        if d in assign_map:
            continue
        delta_weeks = ((d - prev_date).days) // 7
        doc_idx = (prev_doc_idx + delta_weeks) % N
        assign_map[d] = doctors[doc_idx]
        prev_date = d
        prev_doc_idx = doc_idx

    # Compute backward rotation for dates before first week
    first_date = first_week_dates[0]
    prev_date = first_date
    prev_doc_idx = doctors.index(first_week_manual[prev_date])
    for d in reversed(dates_sorted):
        if d in assign_map:
            continue
        delta_weeks = ((prev_date - d).days) // 7
        doc_idx = (prev_doc_idx - delta_weeks) % N
        assign_map[d] = doctors[doc_idx]
        prev_date = d
        prev_doc_idx = doc_idx

    return assign_map

# -----------------------
# UI Controls
# -----------------------
st.title("Προγραμματισμός Βαρδιών Ιατρών — Πλήρης Χειροκίνητη Πρώτη Εβδομάδα")

# Column layout
left, mid, right = st.columns([2,1,1])

with left:
    today = date.today()
    year = st.number_input("Έτος", min_value=2000, max_value=2100, value=today.year)
    month = st.selectbox("Μήνας", list(range(1,13)), index=today.month-1)
    dates = month_dates(year, month)

    # Determine first week of the month (Monday → Sunday)
    first_week_start = dates[0] - timedelta(days=dates[0].weekday())  # Monday
    first_week_dates = [first_week_start + timedelta(days=i) for i in range(7) if (first_week_start + timedelta(days=i)).month == month]

    st.subheader("Χειροκίνητη Ανάθεση Πρώτης Εβδομάδας")
    for d in first_week_dates:
        key = f"first_week_{d}"
        default_doc = st.session_state.first_week_manual.get(d, st.session_state.doctors[0])
        selected_doc = st.selectbox(f"{d.isoformat()} ({calendar.day_name[d.weekday()]})", st.session_state.doctors,
                                    index=st.session_state.doctors.index(default_doc), key=key)
        st.session_state.first_week_manual[d] = selected_doc

with mid:
    st.subheader("Ενέργειες")
    if st.button("Δημιουργία Βαρδιών"):
        # populate month based on first week
        assign_map = populate_rotation(dates, st.session_state.doctors, st.session_state.first_week_manual)
        st.session_state.prev_assignments.update(assign_map)
        if (year, month) not in st.session_state.generated_months:
            st.session_state.generated_months.append((year, month))
        st.success(f"Η βάρδια για τον μήνα {calendar.month_name[month]} {year} δημιουργήθηκε!")

    if st.button("Επαναφορά Όλων"):
        st.session_state.prev_assignments.clear()
        st.session_state.first_week_manual.clear()
        st.session_state.generated_months.clear()
        st.success("Επαναφορά ολοκληρώθηκε!")

with right:
    st.subheader("Εκτύπωση")
    if st.button("Εκτύπωση τελευταίου μήνα"):
        if not st.session_state.generated_months:
            st.warning("Δεν υπάρχει μήνας προς εκτύπωση.")
        else:
            ym = st.session_state.generated_months[-1]
            y,m = ym
            dates = month_dates(y,m)
            st.write(f"Προγραμματισμός για {calendar.month_name[m]} {y}:")
            for d in dates:
                doc = st.session_state.prev_assignments.get(d,"")
                st.write(f"{d.isoformat()} - {calendar.day_name[d.weekday()]} - {doc}")

# -----------------------
# Display schedule & balance
# -----------------------
st.markdown("---")

if st.session_state.generated_months:
    selected_ym = st.selectbox("Προβολή μήνα", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)

    rows = []
    for d in dates:
        rows.append({
            "Ημερομηνία": d.isoformat(),
            "Ημέρα": calendar.day_name[d.weekday()],
            "Ιατρός": st.session_state.prev_assignments.get(d,"")
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, height=480)

    # Balance panel
    balance_rows = []
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        balance_rows.append({"Ιατρός": doc, "Παρασκευές": fr, "Σάββατα": sa, "Κυριακές": su})
    st.subheader("Πίνακας Ισορροπίας (Σωρευτικά)")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Ιατρός"))
