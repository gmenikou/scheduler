# doctor_shift_scheduler_streamlit.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta, datetime
from collections import defaultdict, deque
from fpdf import FPDF
import pickle

# ---------------------------
# Helper functions
# ---------------------------

def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def week_dates(selected_date):
    """Return Monday-Sunday week around selected date"""
    monday = selected_date - timedelta(days=selected_date.weekday())
    return [monday + timedelta(days=i) for i in range(7)]

def assign_backwards_rotation(initial_week, doctors, all_dates):
    """Populate the month based on initial week with backward 2-day rotation per week"""
    assign_map = {}
    # map initial week
    for d, doc in initial_week.items():
        assign_map[d] = doc
    # sort dates
    sorted_dates = sorted(all_dates)
    # generate forward
    for i, d in enumerate(sorted_dates):
        if d in assign_map:
            continue
        # find previous week assigned doctor to rotate
        prev_dates = sorted([dt for dt in assign_map if dt < d])
        if not prev_dates:
            continue
        last_assigned = max(prev_dates)
        last_doc = assign_map[last_assigned]
        last_index = doctors.index(last_doc)
        # backward 2-day rotation
        next_index = (last_index + 1) % len(doctors)
        assign_map[d] = doctors[next_index]
    # generate backward
    for i, d in enumerate(reversed(sorted_dates)):
        if d in assign_map:
            continue
        next_dates = sorted([dt for dt in assign_map if dt > d])
        if not next_dates:
            continue
        next_assigned = min(next_dates)
        next_doc = assign_map[next_assigned]
        next_index = (doctors.index(next_doc) - 1) % len(doctors)
        assign_map[d] = doctors[next_index]
    return assign_map

def print_pdf(df, filename="schedule.pdf", holidays=set()):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Πρόγραμμα Γιατρών", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(5)
    # header
    pdf.cell(40, 8, "Ημερομηνία", border=1)
    pdf.cell(40, 8, "Ημέρα", border=1)
    pdf.cell(80, 8, "Γιατρός", border=1)
    pdf.cell(30, 8, "Αργία", border=1)
    pdf.ln()
    for idx, row in df.iterrows():
        pdf.cell(40, 8, row["Ημερομηνία"].strftime("%d/%m/%Y"), border=1)
        pdf.cell(40, 8, row["Ημέρα"], border=1)
        pdf.cell(80, 8, row["Γιατρός"], border=1)
        hol = "Ναι" if row["Ημερομηνία"] in holidays else ""
        pdf.cell(30, 8, hol, border=1)
        pdf.ln()
    pdf.output(filename)

# ---------------------------
# Streamlit app
# ---------------------------

st.set_page_config(page_title="Πρόγραμμα Γιατρών", layout="wide")

# initialize session state
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'initial_week' not in st.session_state:
    st.session_state.initial_week = {}  # {date: doctor}
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}  # {date: doctor}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)  # {(y,m): set(date)}
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []

st.title("Πρόγραμμα Γιατρών — Περιστροφή 2 ημέρες πίσω")

# ---------------------------
# Controls

col1, col2 = st.columns([2,1])

with col1:
    st.subheader("Επιλογή Μήνα / Αρχικής Εβδομάδας")
    year = st.number_input("Έτος", min_value=2000, max_value=2100, value=date.today().year)
    month = st.selectbox("Μήνας", list(range(1,13)), index=date.today().month-1)
    start_balance = st.checkbox("Ξεκίνημα ισορροπιών από αυτόν τον μήνα", value=False)
    st.markdown("**Αρχική εβδομάδα για χειροκίνητη ανάθεση**")
    ref_date = st.date_input("Επιλογή ημερομηνίας εντός της αρχικής εβδομάδας", value=date.today())

with col2:
    st.subheader("Ενέργειες")
    if st.button("Δημιουργία Προγράμματος Μήνα"):
        ym = (year, month)
        dates = month_dates(year, month)
        # populate using initial_week if exists
        assign_map = assign_backwards_rotation(st.session_state.initial_week, st.session_state.doctors, dates)
        st.session_state.prev_assignments.update(assign_map)
        if ym not in st.session_state.generated_months:
            st.session_state.generated_months.append(ym)
        st.success(f"Δημιουργήθηκε πρόγραμμα για {calendar.month_name[month]} {year}")

    if st.button("Επαναφορά όλων"):
        st.session_state.initial_week = {}
        st.session_state.prev_assignments = {}
        st.session_state.holidays = defaultdict(set)
        st.session_state.generated_months = []
        st.success("Όλα επαναφέρθηκαν")

    if st.button("Αποθήκευση Κατάστασης"):
        with open("schedule_state.pkl","wb") as f:
            pickle.dump({
                "initial_week": {d.isoformat():doc for d,doc in st.session_state.initial_week.items()},
                "prev_assignments": {d.isoformat():doc for d,doc in st.session_state.prev_assignments.items()},
                "holidays": {f"{y}-{m}":[d.isoformat() for d in s] for (y,m),s in st.session_state.holidays.items()},
                "generated_months": st.session_state.generated_months
            }, f)
        st.success("Κατάσταση αποθηκεύτηκε")

    if st.button("Φόρτωση Κατάστασης"):
        try:
            with open("schedule_state.pkl","rb") as f:
                data = pickle.load(f)
            st.session_state.initial_week = {datetime.fromisoformat(d).date():doc for d,doc in data.get("initial_week", {}).items()}
            st.session_state.prev_assignments = {datetime.fromisoformat(d).date():doc for d,doc in data.get("prev_assignments", {}).items()}
            st.session_state.holidays = defaultdict(set)
            for key, lst in data.get("holidays", {}).items():
                y,m = map(int,key.split("-"))
                st.session_state.holidays[(y,m)] = set(datetime.fromisoformat(d).date() for d in lst)
            st.session_state.generated_months = data.get("generated_months", [])
            st.success("Κατάσταση φορτώθηκε")
        except Exception as e:
            st.error(f"Αποτυχία φόρτωσης: {e}")

# ---------------------------
# Initial week manual assignment

st.markdown("---")
st.subheader("Χειροκίνητη Ανάθεση Αρχικής Εβδομάδας")

initial_week_dates = week_dates(ref_date)
df_week = pd.DataFrame({
    "Ημερομηνία": initial_week_dates,
    "Ημέρα": [calendar.day_name[d.weekday()] for d in initial_week_dates],
    "Γιατρός": [st.session_state.initial_week.get(d,"") for d in initial_week_dates]
})

# Manual assignment grid
edited_df = st.experimental_data_editor(df_week, key="initial_week_editor", num_rows="fixed")

if st.button("Αποθήκευση Αρχικής Εβδομάδας"):
    # Validate all assigned
    for d, doc in zip(edited_df["Ημερομηνία"], edited_df["Γιατρός"]):
        if doc not in st.session_state.doctors:
            st.error(f"Όλα τα κελιά πρέπει να έχουν γιατρό. Λείπει για {d}")
            break
    else:
        st.session_state.initial_week = {d:doc for d,doc in zip(edited_df["Ημερομηνία"], edited_df["Γιατρός"])}
        st.success("Αρχική εβδομάδα αποθηκεύτηκε")

# ---------------------------
# Month viewer, holidays & balances

st.markdown("---")
if st.session_state.generated_months:
    selected_ym = st.selectbox("Επιλέξτε μήνα για προβολή", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)

    # Holidays
    st.subheader(f"Αργίες για {calendar.month_name[m]} {y}")
    default_hols = list(st.session_state.holidays.get(selected_ym,set()))
    date_strs = [d.isoformat()+" - "+calendar.day_name[d.weekday()] for d in dates]
    date_map = {date_strs[i]: dates[i] for i in range(len(dates))}
    default_sel = [d.isoformat()+" - "+calendar.day_name[d.weekday()] for d in default_hols if d in dates]
    hol_selection = st.multiselect("Επιλογή αργιών (δεν επηρεάζουν περιστροφή)", date_strs, default=default_sel)
    st.session_state.holidays[selected_ym] = set(date_map[s] for s in hol_selection)

    # Display schedule table
    rows=[]
    for d in dates:
        rows.append({
            "Ημερομηνία": d,
            "Ημέρα": calendar.day_name[d.weekday()],
            "Γιατρός": st.session_state.prev_assignments.get(d,""),
            "Αργία": "Ναι" if d in st.session_state.holidays[selected_ym] else ""
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, height=480)

    # Balance panel
    balance_rows=[]
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_non_weekday = sum(1 for (ym_k,hols) in st.session_state.holidays.items() for hd in hols if hd.weekday() not in (5,6) and st.session_state.prev_assignments.get(hd)==doc)
        balance_rows.append({"Γιατρός":doc,"Παρασκευή":fr,"Σάββατο":sa,"Κυριακή":su,"Αργίες (μη Σαβ/Κυρ)":hol_non_weekday})
    st.subheader("Πίνακας Ισορροπίας (αθροιστικά)")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Γιατρός"))

    # PDF export
    if st.button("Εξαγωγή σε PDF"):
        print_pdf(df, filename=f"Πρόγραμμα_{y}_{m}.pdf", holidays=st.session_state.holidays[selected_ym])
        st.success("Το PDF δημιουργήθηκε: Πρόγραμμα_{y}_{m}.pdf")

else:
    st.info("Δεν έχει δημιουργηθεί ακόμη μήνας. Χρησιμοποιήστε τα controls για να δημιουργήσετε πρόγραμμα.")
