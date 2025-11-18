# doctor_shift_scheduler_streamlit.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
from collections import defaultdict
import pickle
from fpdf import FPDF

# ---------------------------
# Βοηθητικές συναρτήσεις

def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def week_dates_from_monday(start_monday):
    """Επιστρέφει τις 7 ημερομηνίες της εβδομάδας ξεκινώντας από Monday"""
    return [start_monday + timedelta(days=i) for i in range(7)]

def assign_backwards_rotation(initial_week_assignment, doctors, all_dates):
    """Γεμίζει το μήνα βάσει backwards-2-days rotation, αρχής γενομένης από την αρχική εβδομάδα"""
    assign_map = {}
    # αρχική εβδομάδα
    sorted_initial_dates = sorted(initial_week_assignment.keys())
    N = len(doctors)
    # βρίσκουμε το index του γιατρού για κάθε μέρα στην αρχική εβδομάδα
    ref_index_map = {d: doctors.index(initial_week_assignment[d]) for d in sorted_initial_dates}
    
    # γεμίζουμε προς τα εμπρός
    current_date = sorted_initial_dates[-1] + timedelta(days=1)
    while current_date <= max(all_dates):
        prev_date = current_date - timedelta(days=7)
        if prev_date in assign_map:
            prev_doc_idx = doctors.index(assign_map[prev_date])
        else:
            # αν προηγούμενη εβδομάδα είναι αρχική
            prev_doc_idx = ref_index_map.get(prev_date, 0)
        # backwards 2-day rotation
        doc_idx = (prev_doc_idx + 1) % N  # +1 κάθε μέρα (backwards effect)
        assign_map[current_date] = doctors[doc_idx]
        current_date += timedelta(days=1)
        
    # γεμίζουμε προς τα πίσω
    current_date = sorted_initial_dates[0] - timedelta(days=1)
    while current_date >= min(all_dates):
        next_date = current_date + timedelta(days=7)
        if next_date in assign_map:
            next_doc_idx = doctors.index(assign_map[next_date])
        else:
            next_doc_idx = ref_index_map.get(next_date, 0)
        doc_idx = (next_doc_idx -1) % N
        assign_map[current_date] = doctors[doc_idx]
        current_date -= timedelta(days=1)
        
    # προσθέτουμε την αρχική εβδομάδα
    assign_map.update(initial_week_assignment)
    
    return assign_map

# ---------------------------
# Streamlit App

st.set_page_config(page_title="Πρόγραμμα Γιατρών", layout="wide")

# αρχικοποίηση session state
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}
if 'initial_week' not in st.session_state:
    st.session_state.initial_week = {}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Elena","Eva","Maria","Athina","Alexandros","Elia","Christina"]
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []
if 'initial_week_range' not in st.session_state:
    st.session_state.initial_week_range = []

st.title("Πρόγραμμα Γιατρών - Backwards 2-day Rotation")

# Επιλογή αρχικής εβδομάδας
st.subheader("Επιλογή αρχικής εβδομάδας")
today = date.today()
monday_this_week = today - timedelta(days=today.weekday())
start_week = st.date_input("Δευτέρα αρχικής εβδομάδας", value=monday_this_week)
initial_week_dates = week_dates_from_monday(start_week)
st.session_state.initial_week_range = initial_week_dates

# Χειροκίνητη ανάθεση για αρχική εβδομάδα
st.subheader("Χειροκίνητη ανάθεση για αρχική εβδομάδα")
initial_week_df = pd.DataFrame({
    "Ημερομηνία": [d.isoformat() for d in initial_week_dates],
    "Ημέρα": [calendar.day_name[d.weekday()] for d in initial_week_dates],
    "Γιατρός": [st.session_state.initial_week.get(d, st.session_state.doctors[0]) for d in initial_week_dates]
})

edited_df = st.experimental_data_editor(initial_week_df, num_rows="fixed", key="initial_week_editor")

# Αποθήκευση χειροκίνητης ανάθεσης
if st.button("Αποθήκευση αρχικής εβδομάδας"):
    st.session_state.initial_week = {datetime.fromisoformat(row["Ημερομηνία"]).date(): row["Γιατρός"] for i,row in edited_df.iterrows()}
    st.success("Αρχική εβδομάδα αποθηκεύτηκε")

# Επιλογή μήνα για πλήρωση
st.subheader("Επιλογή μήνα για πλήρωση")
year = st.number_input("Έτος", min_value=2000, max_value=2100, value=today.year)
month = st.selectbox("Μήνας", list(range(1,13)), index=today.month-1)

dates_in_month = month_dates(year, month)

# Γέμισμα μήνα
if st.button("Γέμισμα μήνα βάσει αρχικής εβδομάδας"):
    if not st.session_state.initial_week:
        st.warning("Πρέπει πρώτα να ορίσετε την αρχική εβδομάδα!")
    else:
        assign_map = assign_backwards_rotation(st.session_state.initial_week, st.session_state.doctors, dates_in_month)
        st.session_state.prev_assignments.update(assign_map)
        if (year, month) not in st.session_state.generated_months:
            st.session_state.generated_months.append((year, month))
        st.success(f"Μήνας {calendar.month_name[month]} {year} γεμίστηκε.")

# Επιλογή αργιών
st.subheader("Χειροκίνητη επιλογή αργιών")
if st.session_state.generated_months:
    selected_ym = st.selectbox("Επιλέξτε μήνα για αργίες", st.session_state.generated_months)
    y,m = selected_ym
    month_dates_list = month_dates(y,m)
    date_strs = [d.isoformat() + " - " + calendar.day_name[d.weekday()] for d in month_dates_list]
    default_hols = [d.isoformat() + " - " + calendar.day_name[d.weekday()] for d in st.session_state.holidays.get(selected_ym,set()) if d in month_dates_list]
    selected_hols = st.multiselect("Αργίες (μόνο για ενημέρωση balance)", date_strs, default=default_hols)
    st.session_state.holidays[selected_ym] = set(datetime.fromisoformat(s.split(" - ")[0]).date() for s in selected_hols)

# Εμφάνιση προγράμματος και balance
st.subheader("Πρόγραμμα & Balance")
if st.session_state.generated_months:
    for ym in st.session_state.generated_months:
        y,m = ym
        df = pd.DataFrame({
            "Ημερομηνία": month_dates(y,m),
            "Ημέρα": [calendar.day_name[d.weekday()] for d in month_dates(y,m)],
            "Γιατρός": [st.session_state.prev_assignments.get(d,"") for d in month_dates(y,m)],
            "Αργία": ["Yes" if d in st.session_state.holidays.get(ym,set()) else "" for d in month_dates(y,m)]
        })
        st.write(f"Μήνας {calendar.month_name[m]} {y}")
        st.dataframe(df, height=400)

# Balance panel
st.subheader("Πίνακας ισορροπίας (Συσσωρευτικά)")
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
    balance_rows.append({"Γιατρός": doc, "Παρασκευή": fr, "Σάββατο": sa, "Κυριακή": su, "Αργίες (εκτός Σαββατοκύριακου)": hol_non_weekday})
st.dataframe(pd.DataFrame(balance_rows).set_index("Γιατρός"))

# Εκτύπωση σε PDF
st.subheader("Εκτύπωση σε PDF")
if st.button("Δημιουργία PDF για τελευταίο μήνα"):
    if not st.session_state.generated_months:
        st.warning("Δεν υπάρχει μήνας για εκτύπωση")
    else:
        last_ym = st.session_state.generated_months[-1]
        y,m = last_ym
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(0,10,f"Πρόγραμμα {calendar.month_name[m]} {y}",ln=1)
        pdf.ln(5)
        pdf.set_font("Arial", size=10)
        dates_list = month_dates(y,m)
        for d in dates_list:
            doc = st.session_state.prev_assignments.get(d,"")
            hol_flag = " (Αργία)" if d in st.session_state.holidays.get(last_ym,set()) else ""
            pdf.cell(0,8,f"{d.isoformat()} {calendar.day_name[d.weekday()]} : {doc}{hol_flag}",ln=1)
        pdf.output("schedule.pdf")
        st.success("PDF δημιουργήθηκε: schedule.pdf")
