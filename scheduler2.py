# doctor_shift_scheduler_streamlit_full.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
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

# Rotation population function
def assign_rotation_for_month(year, month, doctors, first_week_assign):
    # first_week_assign: dict {date: doctor} manual initial week
    # returns dict {date: doctor} for entire month
    assign_map = {}
    N = len(doctors)
    first_week_dates = sorted(first_week_assign.keys())
    if not first_week_dates:
        return {}
    ref_date = first_week_dates[0]
    ref_doc_index = doctors.index(first_week_assign[ref_date])
    # iterate all days in month
    dates = month_dates(year, month)
    for d in dates:
        # compute weeks offset from reference date
        weeks_between = ((d - ref_date).days) // 7
        day_offset = (d.weekday() - ref_date.weekday())
        # backward 2-day rotation per week
        shift_index = (ref_doc_index + weeks_between) % N
        assign_map[d] = doctors[shift_index]
    # overwrite initial week
    assign_map.update(first_week_assign)
    return assign_map

# ---------------------------
# Streamlit App

st.set_page_config(page_title="Προγραμματιστής Βαριδιών Γιατρών", layout="wide")

# Initialize session state
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'first_week_assign' not in st.session_state:
    st.session_state.first_week_assign = {}  # {date: doctor}
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}  # cumulative
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []

st.title("Προγραμματιστής Βαριδιών Γιατρών — Backwards 2-days rotation")

# ---------------------------
# Επιλογή αρχικής εβδομάδας
st.subheader("Επιλογή αρχικής εβδομάδας")

start_monday = st.date_input("Δευτέρα αρχικής εβδομάδας", value=date.today() - timedelta(days=date.today().weekday()))
first_week_dates = [start_monday + timedelta(days=i) for i in range(7)]

# DataFrame για DataEditor (μετατρέπουμε dates σε string)
week_df = pd.DataFrame({
    "Ημερομηνία": [d.isoformat() for d in first_week_dates],
    "Ημέρα": [calendar.day_name[d.weekday()] for d in first_week_dates],
    "Γιατρός": [st.session_state.first_week_assign.get(d,"") for d in first_week_dates]
})

st.markdown("**Εισαγωγή Γιατρού ανά ημέρα για την αρχική εβδομάδα**")
edited_df = st.experimental_data_editor(week_df, key="initial_week_editor", num_rows="fixed")

if st.button("Αποθήκευση αρχικής εβδομάδας"):
    st.session_state.first_week_assign.clear()
    for i,row in edited_df.iterrows():
        d = datetime.fromisoformat(row["Ημερομηνία"]).date()
        if row["Γιατρός"] in st.session_state.doctors:
            st.session_state.first_week_assign[d] = row["Γιατρός"]
    st.success("Η αρχική εβδομάδα αποθηκεύτηκε.")

# ---------------------------
# Επιλογή μήνα για population
st.subheader("Δημιουργία προγράμματος για μήνα")
col1, col2 = st.columns(2)
with col1:
    year = st.number_input("Έτος", min_value=2000, max_value=2100, value=date.today().year)
    month = st.selectbox("Μήνας", list(range(1,13)), index=date.today().month-1)
with col2:
    if st.button("Γεννήστε πρόγραμμα μήνα"):
        if not st.session_state.first_week_assign:
            st.warning("Αποθηκεύστε πρώτα την αρχική εβδομάδα!")
        else:
            assign_map = assign_rotation_for_month(year, month, st.session_state.doctors, st.session_state.first_week_assign)
            st.session_state.prev_assignments.update(assign_map)
            if (year, month) not in st.session_state.generated_months:
                st.session_state.generated_months.append((year, month))
            st.success(f"Γεννήθηκε πρόγραμμα για {calendar.month_name[month]} {year}")

# ---------------------------
# Εμφάνιση παραγόμενου μήνα
if st.session_state.generated_months:
    selected_ym = st.selectbox("Προβολή μήνα", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)
    df = pd.DataFrame({
        "Ημερομηνία": dates,
        "Ημέρα": [calendar.day_name[d.weekday()] for d in dates],
        "Γιατρός": [st.session_state.prev_assignments.get(d,"") for d in dates]
    })

    # Πολυ-επιλογή αργιών
    holiday_options = [d for d in dates]
    holiday_selection = st.multiselect("Αργίες (δεν επηρεάζουν rotation)", holiday_options,
                                       default=list(st.session_state.holidays.get(selected_ym,set())))
    if st.button("Εφαρμογή Αργιών"):
        st.session_state.holidays[selected_ym] = set(holiday_selection)
        st.success("Αργίες αποθηκεύτηκαν. Οι ισορροπίες υπολογίζονται.")

    # Εμφάνιση πίνακα
    df['Αργία'] = df['Ημερομηνία'].apply(lambda d: "Ναι" if d in st.session_state.holidays.get(selected_ym,set()) else "")
    st.dataframe(df.style.applymap(lambda v: 'background-color: yellow' if v=="Ναι" else '', subset=['Αργία']), height=400)

    # ---------------------------
    # Ισοζύγιο
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
            "Γιατρός": doc,
            "Παρασκευή": fr,
            "Σάββατο": sa,
            "Κυριακή": su,
            "Αργίες (μη Σ/Κ)": hol_non_weekday
        })
    st.subheader("Ισοζύγιο (αθροιστικά)")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Γιατρός"))

# ---------------------------
# Εκτύπωση PDF
if st.button("Εκτύπωση σε PDF"):
    if not st.session_state.generated_months:
        st.warning("Δεν υπάρχει μήνας για εκτύπωση")
    else:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        for ym in st.session_state.generated_months:
            y,m = ym
            pdf.cell(0,10,f"Πρόγραμμα {calendar.month_name[m]} {y}", ln=True)
            dates = month_dates(y,m)
            pdf.set_font("Arial", "", 12)
            for d in dates:
                doc = st.session_state.prev_assignments.get(d,"")
                hol_flag = "Αργία" if d in st.session_state.holidays.get(ym,set()) else ""
                pdf.cell(0,8,f"{d.isoformat()} ({calendar.day_name[d.weekday()]}) - {doc} {hol_flag}", ln=True)
            pdf.ln(5)
        pdf.output("schedule.pdf")
        st.success("Το PDF δημιουργήθηκε: schedule.pdf")
