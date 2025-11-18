# doctor_shift_scheduler_streamlit.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta, datetime
from collections import defaultdict, deque
import pickle
from fpdf import FPDF

# ---------------------------
# Helper Functions
# ---------------------------

def get_week_dates(start_date):
    """Return list of 7 dates for the week containing start_date (Monday to Sunday)."""
    monday = start_date - timedelta(days=start_date.weekday())
    return [monday + timedelta(days=i) for i in range(7)]

def assign_backwards_rotation(initial_week, doctors, all_dates):
    """
    Given the manual assignment of the initial week (dict {date: doctor}),
    populate remaining dates forward and backward according to backwards 2-days per week rotation.
    """
    all_dates_sorted = sorted(all_dates)
    N = len(doctors)
    dates_to_assign = [d for d in all_dates_sorted if d not in initial_week]
    assign_map = dict(initial_week)

    # Prepare reference sequence from initial week
    ref_week = sorted(initial_week.keys())
    ref_doc_order = [initial_week[d] for d in ref_week]

    # Forward propagation
    for i, d in enumerate(dates_to_assign):
        # number of weeks from the initial reference
        weeks_offset = (d - ref_week[-1]).days // 7 + 1
        prev_doc = assign_map[ref_week[-1]]
        idx = (doctors.index(prev_doc) + weeks_offset) % N
        assign_map[d] = doctors[idx]

    # Backward propagation
    for i, d in enumerate(reversed(all_dates_sorted)):
        if d in assign_map:
            continue
        # number of weeks backward from first reference week
        weeks_offset = (ref_week[0] - d).days // 7 + 1
        prev_doc = assign_map[ref_week[0]]
        idx = (doctors.index(prev_doc) - weeks_offset) % N
        assign_map[d] = doctors[idx]

    return assign_map

def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def print_schedule_pdf(assign_map, holidays, filename="schedule.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Doctor Shift Schedule", ln=True, align="C")
    pdf.ln(5)
    pdf.cell(40, 8, "Date", 1)
    pdf.cell(40, 8, "Weekday", 1)
    pdf.cell(60, 8, "Doctor", 1)
    pdf.cell(40, 8, "Holiday", 1)
    pdf.ln()
    for d in sorted(assign_map.keys()):
        pdf.cell(40, 8, d.isoformat(), 1)
        pdf.cell(40, 8, calendar.day_name[d.weekday()], 1)
        pdf.cell(60, 8, assign_map[d], 1)
        pdf.cell(40, 8, "Yes" if d in holidays else "", 1)
        pdf.ln()
    pdf.output(filename)
    return filename

# ---------------------------
# Streamlit App

st.set_page_config(page_title="Doctor Shift Scheduler", layout="wide")

# Initialize session state
if 'initial_week' not in st.session_state:
    st.session_state.initial_week = {}  # {date: doctor}
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}  # {date: doctor}
if 'holidays' not in st.session_state:
    st.session_state.holidays = set()
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Έλενα", "Εύα", "Μαρία", "Αθηνά", "Αλέξανδρος", "Έλια", "Χριστίνα"]

st.title("Πρόγραμμα Εφημεριών Ιατρών — Περιστροφή 2-ημέρες ανά εβδομάδα")

# ---------------------------
# Select initial week for manual assignment
st.subheader("Επιλογή αρχικής εβδομάδας")
ref_start_date = st.date_input("Επιλέξτε την αρχική Δευτέρα της εβδομάδας", value=date(2026,1,12))

week_dates_list = get_week_dates(ref_start_date)

# Prepare dataframe for manual assignment
week_df = pd.DataFrame({
    "Ημέρα": [calendar.day_name[d.weekday()] for d in week_dates_list],
    "Ημερομηνία": week_dates_list,
    "Γιατρός": [st.session_state.initial_week.get(d, "") for d in week_dates_list]
})

st.write("Αναθέστε χειροκίνητα τους γιατρούς για κάθε ημέρα της εβδομάδας:")
edited_df = st.data_editor(week_df, key="initial_week_editor", num_rows="fixed")

# Apply manual assignment
if st.button("Αποθήκευση αρχικής εβδομάδας"):
    for idx, row in edited_df.iterrows():
        st.session_state.initial_week[row["Ημερομηνία"]] = row["Γιατρός"]
    st.success("Αρχική εβδομάδα αποθηκεύτηκε.")

# ---------------------------
# Generate month schedule using rotation
st.subheader("Δημιουργία προγράμματος για μήνα")
col1, col2 = st.columns(2)
with col1:
    year = st.number_input("Έτος", min_value=2000, max_value=2100, value=2026)
    month = st.selectbox("Μήνας", list(range(1,13)), index=0)
    start_balance = st.checkbox("Επαναφορά ισορροπίας από αυτόν τον μήνα", value=False)
with col2:
    if st.button("Γεννήστε πρόγραμμα για μήνα"):
        if start_balance:
            st.session_state.prev_assignments = {}
            st.session_state.generated_months = []
        dates = month_dates(year, month)
        assign_map = assign_backwards_rotation(st.session_state.initial_week, st.session_state.doctors, dates)
        st.session_state.prev_assignments.update(assign_map)
        if (year,month) not in st.session_state.generated_months:
            st.session_state.generated_months.append((year,month))
        st.success(f"Πρόγραμμα για {calendar.month_name[month]} {year} δημιουργήθηκε.")

# ---------------------------
# Holiday selection
st.subheader("Αναθέσεις Αργιών")
if st.session_state.generated_months:
    selected_ym = st.selectbox("Επιλέξτε μήνα για αργίες", st.session_state.generated_months)
    y,m = selected_ym
    dates = month_dates(y,m)
    date_strs = [d.isoformat() + " - " + calendar.day_name[d.weekday()] for d in dates]
    date_map = {date_strs[i]: dates[i] for i in range(len(dates))}
    default_hols = [d.isoformat() + " - " + calendar.day_name[d.weekday()] for d in st.session_state.holidays if d in dates]
    hol_selection = st.multiselect("Επιλογή αργιών", date_strs, default=default_hols)
    st.session_state.holidays.update({date_map[s] for s in hol_selection})

# ---------------------------
# Display schedule table
if st.session_state.generated_months:
    st.subheader("Πρόγραμμα Εφημεριών")
    display_dates = month_dates(year, month)
    df_rows = []
    for d in display_dates:
        df_rows.append({
            "Ημερομηνία": d,
            "Ημέρα": calendar.day_name[d.weekday()],
            "Γιατρός": st.session_state.prev_assignments.get(d, ""),
            "Αργία": "Ναι" if d in st.session_state.holidays else ""
        })
    df_display = pd.DataFrame(df_rows)
    st.dataframe(df_display, height=480)

# ---------------------------
# Balance panel
st.subheader("Πίνακας Ισορροπίας")
balance_rows = []
for doc in st.session_state.doctors:
    fr = sum(1 for d, dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
    sa = sum(1 for d, dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
    su = sum(1 for d, dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
    hol_non_weekday = sum(1 for d in st.session_state.holidays if d.weekday() not in (5,6) and st.session_state.prev_assignments.get(d)==doc)
    balance_rows.append({
        "Γιατρός": doc,
        "Παρασκευές": fr,
        "Σάββατα": sa,
        "Κυριακές": su,
        "Αργίες (μη Σ/Κ)": hol_non_weekday
    })
st.dataframe(pd.DataFrame(balance_rows).set_index("Γιατρός"))

# ---------------------------
# Print to PDF
st.subheader("Εκτύπωση σε PDF")
if st.button("Εκτύπωση τρέχοντος μήνα"):
    filename = print_schedule_pdf(st.session_state.prev_assignments, st.session_state.holidays)
    st.success(f"Αρχείο PDF δημιουργήθηκε: {filename}")

# ---------------------------
# Save / Load / Reset state
st.subheader("Αποθήκευση / Φόρτωση / Επαναφορά Προγράμματος")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Αποθήκευση κατάστασης"):
        data = {
            "initial_week": {d.isoformat(): doc for d, doc in st.session_state.initial_week.items()},
            "prev_assignments": {d.isoformat(): doc for d, doc in st.session_state.prev_assignments.items()},
            "holidays": [d.isoformat() for d in st.session_state.holidays],
            "generated_months": st.session_state.generated_months
        }
        with open("schedule_state.pkl","wb") as f:
            pickle.dump(data, f)
        st.success("Κατάσταση προγράμματος αποθηκεύτηκε.")

with col2:
    if st.button("Φόρτωση κατάστασης"):
        try:
            with open("schedule_state.pkl","rb") as f:
                data = pickle.load(f)
            st.session_state.initial_week = {datetime.fromisoformat(d).date(): doc for d, doc in data.get("initial_week", {}).items()}
            st.session_state.prev_assignments = {datetime.fromisoformat(d).date(): doc for d, doc in data.get("prev_assignments", {}).items()}
            st.session_state.holidays = set(datetime.fromisoformat(d).date() for d in data.get("holidays", []))
            st.session_state.generated_months = data.get("generated_months", [])
            st.success("Κατάσταση προγράμματος φορτώθηκε.")
        except Exception as e:
            st.error(f"Αποτυχία φόρτωσης: {e}")

with col3:
    if st.button("Επαναφορά / Διαγραφή προγράμματος"):
        st.session_state.initial_week = {}
        st.session_state.prev_assignments = {}
        st.session_state.holidays = set()
        st.session_state.generated_months = []
        st.success("Όλα διαγράφηκαν.")
