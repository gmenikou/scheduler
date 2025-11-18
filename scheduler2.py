# doctor_shift_scheduler_streamlit_gr.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
from collections import defaultdict
from io import BytesIO
import pickle

# ---------------------------
# Βοηθητικές Συναρτήσεις

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

def assign_rotation_for_month(year, month, doctors, ref_date, ref_doc, manual_assign=None):
    """Ανάθεση βάρδιας για τον μήνα, με κανόνα οπισθοδρομικής περιστροφής 2 ημερών/εβδομάδα"""
    mondays = weeks_in_month(year, month)
    N = len(doctors)
    try:
        ref_index = doctors.index(ref_doc)
    except ValueError:
        ref_index = 0
    ref_monday = weekday_monday(ref_date)
    assign_map = {}

    for week_idx, week_monday in enumerate(mondays):
        weeks_between = (week_monday - ref_monday).days // 7
        doc_idx = (ref_index + weeks_between) % N
        doc = doctors[doc_idx]
        shift_weekday = (ref_date.weekday() - 2 * weeks_between) % 7
        shift_date = week_monday + timedelta(days=shift_weekday)
        if shift_date.year == year and shift_date.month == month:
            if manual_assign and shift_date in manual_assign:
                assign_map[shift_date] = manual_assign[shift_date]
            else:
                assign_map[shift_date] = doc
    return assign_map

# ---------------------------
# Streamlit App Setup

st.set_page_config(page_title="Προγραμματιστής Βαρδιών", layout="wide")

# State
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []
if 'ref_date' not in st.session_state:
    st.session_state.ref_date = date.today()
if 'ref_doc' not in st.session_state:
    st.session_state.ref_doc = st.session_state.doctors[0]

st.title("Προγραμματιστής Βαρδιών — Οπισθοδρομική Περιστροφή 2 ημερών/εβδομάδα")

# ---------------------------
# Controls

left, mid, right = st.columns([2,1,1])

with left:
    st.subheader("Ρυθμίσεις Μήνα / Αναφοράς")
    year = st.number_input("Έτος", min_value=2000, max_value=2100, value=date.today().year)
    month = st.selectbox("Μήνας", list(range(1,13)), index=date.today().month-1)
    start_balance = st.checkbox("Επαναφορά ισοζυγίων από αυτόν τον μήνα", value=False)
    st.markdown("**Βάση Αναφοράς (εβδομάδα και ημέρα)**")
    ref_date = st.date_input("Ημερομηνία αναφοράς", value=st.session_state.ref_date)
    ref_doc = st.selectbox("Ιατρός αναφοράς", st.session_state.doctors, index=st.session_state.doctors.index(st.session_state.ref_doc))

with mid:
    st.subheader("Ενέργειες")
    if st.button("Δημιουργία Βαρδιών"):
        st.session_state.ref_date = ref_date
        st.session_state.ref_doc = ref_doc
        ym = (year, month)

        # Τρέχουσα εβδομάδα Δευτέρα–Κυριακή
        today = date.today()
        week_monday = weekday_monday(today)
        week_dates = [week_monday + timedelta(days=i) for i in range(7)]

        # Editable first-week table
        st.write("### Ανάθεση πρώτης εβδομάδας (Δευτέρα–Κυριακή)")
        first_week_df = pd.DataFrame({
            "Ημερομηνία": week_dates,
            "Ημέρα": [calendar.day_name[d.weekday()] for d in week_dates],
            "Ιατρός": [st.session_state.doctors[0]]*7
        })
        edited_df = st.experimental_data_editor(first_week_df, num_rows="fixed", key="first_week_editor")

        manual_assign = {row["Ημερομηνία"]: row["Ιατρός"] for idx,row in edited_df.iterrows()}

        # Γενική δημιουργία βαρδιών για τον μήνα
        assign_map = assign_rotation_for_month(year, month, st.session_state.doctors, st.session_state.ref_date, st.session_state.ref_doc, manual_assign=manual_assign)
        st.session_state.prev_assignments.update(assign_map)

        if ym not in st.session_state.generated_months:
            st.session_state.generated_months.append(ym)
        if start_balance:
            st.session_state.prev_assignments = assign_map.copy()
            st.session_state.generated_months = [ym]

        st.success(f"Δημιουργήθηκε πρόγραμμα για τον μήνα {calendar.month_name[month]} {year}")

    if st.button("Επαναφορά Όλων"):
        st.session_state.prev_assignments = {}
        st.session_state.holidays = defaultdict(set)
        st.session_state.generated_months = []
        st.success("Όλα τα προγράμματα και οι αργίες επαναφέρθηκαν")

    if st.button("Αποθήκευση Κατάστασης"):
        data = {
            "prev_assignments": {d.isoformat(): doc for d,doc in st.session_state.prev_assignments.items()},
            "holidays": {f"{y}-{m}": [d.isoformat() for d in s] for (y,m),s in st.session_state.holidays.items()},
            "generated_months": st.session_state.generated_months,
            "ref_date": st.session_state.ref_date.isoformat(),
            "ref_doc": st.session_state.ref_doc
        }
        with open("schedule_state.pkl","wb") as f:
            pickle.dump(data, f)
        st.success("Κατάσταση αποθηκεύτηκε")

    if st.button("Φόρτωση Κατάστασης"):
        try:
            with open("schedule_state.pkl","rb") as f:
                data = pickle.load(f)
            st.session_state.prev_assignments = {datetime.fromisoformat(k).date(): v for k,v in data["prev_assignments"].items()}
            st.session_state.holidays = defaultdict(set)
            for key,lst in data.get("holidays",{}).items():
                y,m = map(int,key.split("-"))
                st.session_state.holidays[(y,m)] = set(datetime.fromisoformat(d).date() for d in lst)
            st.session_state.generated_months = data.get("generated_months",[])
            st.session_state.ref_date = datetime.fromisoformat(data.get("ref_date")).date()
            st.session_state.ref_doc = data.get("ref_doc", st.session_state.doctors[0])
            st.success("Κατάσταση φορτώθηκε")
        except Exception as e:
            st.error(f"Σφάλμα κατά τη φόρτωση: {e}")

with right:
    st.subheader("Εκτύπωση")
    if st.button("Εκτύπωση τελευταίου μήνα (σε HTML)"):
        if not st.session_state.generated_months:
            st.warning("Δεν έχει δημιουργηθεί μήνας")
        else:
            ym = st.session_state.generated_months[-1]
            y,m = ym
            dates = month_dates(y,m)
            html = "<html><body><h3>Πρόγραμμα</h3><table border=1><tr><th>Ημερομηνία</th><th>Ημέρα</th><th>Ιατρός</th><th>Αργία</th></tr>"
            for d in dates:
                doc = st.session_state.prev_assignments.get(d,"")
                hol = "Ναι" if d in st.session_state.holidays.get(ym,set()) else ""
                html += f"<tr><td>{d}</td><td>{calendar.day_name[d.weekday()]}</td><td>{doc}</td><td>{hol}</td></tr>"
            html += "</table></body></html>"
            st.download_button("Κατέβασμα HTML για εκτύπωση", html, file_name=f"schedule_{y}_{m}.html", mime="text/html")

# ---------------------------
# Προβολή μήνα & Ισοζύγια

st.markdown("---")

if st.session_state.generated_months:
    selected_ym = st.selectbox("Επιλογή μήνα προς προβολή", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)

    # Holiday toggling
    st.subheader(f"Πρόγραμμα {calendar.month_name[m]} {y}")
    default_hols = list(st.session_state.holidays.get(selected_ym, []))
    date_strs = [d.isoformat() + " - " + calendar.day_name[d.weekday()] for d in dates]
    date_map = {date_strs[i]: dates[i] for i in range(len(dates))}
    selected_defaults = [s.isoformat() + " - " + calendar.day_name[s.weekday()] for s in default_hols if s in dates]
    hol_selection = st.multiselect("Αργίες (δεν επηρεάζουν περιστροφή)", date_strs, default=selected_defaults)
    st.session_state.holidays[selected_ym] = set(date_map[s] for s in hol_selection)

    # Display schedule table
    rows = []
    for d in dates:
        doc = st.session_state.prev_assignments.get(d, "")
        wd = calendar.day_name[d.weekday()]
        is_hol = d in st.session_state.holidays.get(selected_ym, set())
        rows.append({"Ημερομηνία": d, "Ημέρα": wd, "Ιατρός": doc, "Αργία": "Ναι" if is_hol else ""})
    df = pd.DataFrame(rows)
    st.dataframe(df.style.applymap(lambda v: 'background-color: yellow' if v=="Ναι" else '', subset=['Αργία']), height=480)

    # Balance panel
    balance_rows = []
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_non_week = 0
        for (ym_k, holset) in st.session_state.holidays.items():
            for hd in holset:
                if st.session_state.prev_assignments.get(hd) == doc and hd.weekday() not in (5,6):
                    hol_non_week += 1
        balance_rows.append({"Ιατρός": doc, "Παρασκευή": fr, "Σάββατο": sa, "Κυριακή": su, "Αργίες εκτός Σ/Κ": hol_non_week})
    st.subheader("Πίνακας Ισοζυγίων (συσσωρευτικά)")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Ιατρός"))
else:
    st.info("Δεν έχει δημιουργηθεί ακόμη μήνας. Χρησιμοποιήστε τα controls για να δημιουργήσετε πρόγραμμα.")
