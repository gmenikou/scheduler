# doctor_shift_scheduler_streamlit_full_v2.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from collections import defaultdict
import pickle

# ---------------------------
# Helper functions

def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

# ---------------------------
# Rotation assignment function (day-by-day backward 2-day rotation)
def assign_rotation_from_first_week(first_week_manual, doctors, month_dates_list):
    """Populate all remaining days in the month based on first-week manual assignment"""
    assign_map = dict(first_week_manual)  # start with manual first week
    N = len(doctors)

    # Sort first week dates
    manual_dates_sorted = sorted(first_week_manual.keys())

    if not manual_dates_sorted:
        return assign_map

    # Start from last day of manual week
    last_manual_date = manual_dates_sorted[-1]
    last_doc = first_week_manual[last_manual_date]
    doc_index = doctors.index(last_doc)

    # Forward population
    all_dates_sorted = sorted(month_dates_list)
    for d in all_dates_sorted:
        if d in assign_map:
            continue
        # rotate doctor forward
        doc_index = (doc_index + 1) % N
        assign_map[d] = doctors[doc_index]

    return assign_map

# ---------------------------
# Streamlit App

st.set_page_config(page_title="Πρόγραμμα Εφημεριών", layout="wide")

# Initialize session state
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []
if 'first_week_manual' not in st.session_state:
    st.session_state.first_week_manual = {}

st.title("Πρόγραμμα Εφημεριών — Περιστροφή 2 ημερών προς τα πίσω")

# ---------------------------
# Controls
left, mid, right = st.columns([2,1,1])

with left:
    st.subheader("Ρυθμίσεις Μήνα / Αφετηρίας")
    year = st.number_input("Έτος", min_value=2000, max_value=2100, value=2026)
    month = st.selectbox("Μήνας", list(range(1,13)), index=0)
    start_balance = st.checkbox("Ξεκίνημα ισορροπίας από αυτόν τον μήνα", value=False)

    # Manual first week
    st.subheader("Χειροκίνητη Ανάθεση Πρώτης Εβδομάδας")
    manual_start_date = st.date_input("Επιλέξτε ημερομηνία έναρξης πρώτης εβδομάδας", value=date(2026,1,12))
    monday = manual_start_date - timedelta(days=manual_start_date.weekday())
    first_week_dates = [monday + timedelta(days=i) for i in range(7)]
    for d in first_week_dates:
        key = f"first_week_{d}"
        default_doc = st.session_state.first_week_manual.get(d, st.session_state.doctors[0])
        selected_doc = st.selectbox(f"{d.isoformat()} ({calendar.day_name[d.weekday()]})", 
                                    st.session_state.doctors,
                                    index=st.session_state.doctors.index(default_doc), key=key)
        st.session_state.first_week_manual[d] = selected_doc

with mid:
    st.subheader("Ενέργειες")
    if st.button("Δημιουργία Προγράμματος"):
        if start_balance:
            st.session_state.prev_assignments = {}
            st.session_state.generated_months = []

        ym = (year, month)
        dates_list = month_dates(year, month)
        assign_map = assign_rotation_from_first_week(st.session_state.first_week_manual, st.session_state.doctors, dates_list)
        st.session_state.prev_assignments.update(assign_map)
        if ym not in st.session_state.generated_months:
            st.session_state.generated_months.append(ym)
        st.success(f"Δημιουργήθηκε πρόγραμμα για {calendar.month_name[month]} {year}")

    if st.button("Επαναφορά Όλων"):
        st.session_state.prev_assignments = {}
        st.session_state.holidays = defaultdict(set)
        st.session_state.generated_months = []
        st.session_state.first_week_manual = {}
        st.success("Επαναφορά όλων των δεδομένων")

    if st.button("Αποθήκευση Κατάστασης"):
        data = {
            "prev_assignments": {d.isoformat(): doc for d,doc in st.session_state.prev_assignments.items()},
            "holidays": {f"{y}-{m}": [d.isoformat() for d in s] for (y,m),s in st.session_state.holidays.items()},
            "generated_months": st.session_state.generated_months,
            "first_week_manual": {d.isoformat(): doc for d,doc in st.session_state.first_week_manual.items()}
        }
        with open("schedule_state.pkl","wb") as f:
            pickle.dump(data,f)
        st.success("Κατάσταση αποθηκεύτηκε σε schedule_state.pkl")

    if st.button("Φόρτωση Κατάστασης"):
        try:
            with open("schedule_state.pkl","rb") as f:
                data = pickle.load(f)
            st.session_state.prev_assignments = {pd.to_datetime(k).date(): v for k,v in data["prev_assignments"].items()}
            st.session_state.holidays = defaultdict(set)
            for key,lst in data.get("holidays",{}).items():
                y,m = map(int,key.split("-"))
                st.session_state.holidays[(y,m)] = set(pd.to_datetime(d).date() for d in lst)
            st.session_state.generated_months = data.get("generated_months", [])
            st.session_state.first_week_manual = {pd.to_datetime(k).date(): v for k,v in data.get("first_week_manual",{}).items()}
            st.success("Κατάσταση φορτώθηκε")
        except Exception as e:
            st.error(f"Αποτυχία φόρτωσης: {e}")

with right:
    st.subheader("Εκτύπωση")
    if st.button("Εκτύπωση τελευταίου μήνα"):
        if not st.session_state.generated_months:
            st.warning("Δεν έχει δημιουργηθεί μήνας ακόμα")
        else:
            ym = st.session_state.generated_months[-1]
            y,m = ym
            print(f"\nΠρόγραμμα για {calendar.month_name[m]} {y}:")
            for d in month_dates(y,m):
                doc = st.session_state.prev_assignments.get(d,"")
                hol_flag = "ΑΡΓΙΑ" if d in st.session_state.holidays.get(ym,set()) else ""
                print(f"{d.isoformat()}\t{calendar.day_name[d.weekday()]}\t{doc}\t{hol_flag}")
            st.success("Το πρόγραμμα εκτυπώθηκε στην κονσόλα του server")

# ---------------------------
# Viewer
st.markdown("---")
if st.session_state.generated_months:
    selected_ym = st.selectbox("Επιλέξτε μήνα για προβολή", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)

    # Holidays
    st.subheader(f"Πρόγραμμα {calendar.month_name[m]} {y}")
    default_hols = list(st.session_state.holidays.get(selected_ym,set()))
    date_strs = [d.isoformat() + " - " + calendar.day_name[d.weekday()] for d in dates]
    date_map = {date_strs[i]: dates[i] for i in range(len(dates))}
    selected_defaults = [s.isoformat() + " - " + calendar.day_name[s.weekday()] for s in default_hols if s in dates]
    hol_selection = st.multiselect("Αργίες (δεν επηρεάζουν περιστροφή)", date_strs, default=selected_defaults)
    st.session_state.holidays[selected_ym] = set(date_map[s] for s in hol_selection)

    # Display schedule
    rows = []
    for d in dates:
        doc = st.session_state.prev_assignments.get(d,"")
        is_hol = d in st.session_state.holidays.get(selected_ym,set())
        rows.append({
            "Ημερομηνία": d,
            "Ημέρα": calendar.day_name[d.weekday()],
            "Γιατρός": doc,
            "Αργία": "Ναι" if is_hol else ""
        })
    df = pd.DataFrame(rows)
    st.dataframe(df.style.applymap(lambda v:'background-color:yellow' if v=="Ναι" else '', subset=['Αργία']), height=480)

    # Balance panel
    balance_rows = []
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_non_weekday = sum(1 for (y_m, holset) in st.session_state.holidays.items() for hd in holset if st.session_state.prev_assignments.get(hd)==doc and hd.weekday() not in (5,6))
        balance_rows.append({
            "Γιατρός": doc,
            "Παρασκευές": fr,
            "Σάββατα": sa,
            "Κυριακές": su,
            "Αργίες (εκτός Σαβ/Κυρ)": hol_non_weekday
        })
    st.subheader("Πίνακας Ισορροπίας (συσσωρευτικά)")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Γιατρός"))

else:
    st.info("Δεν έχει δημιουργηθεί ακόμα μήνας. Χρησιμοποιήστε τα κουμπιά παραπάνω.")
