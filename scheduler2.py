# doctor_shift_scheduler_streamlit.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
from collections import defaultdict
from fpdf import FPDF
import pickle
import os

# ---------------------------
# Βοηθητικές Συναρτήσεις
# ---------------------------

def monday_of(date_obj: date) -> date:
    return date_obj - timedelta(days=date_obj.weekday())

def month_dates(year: int, month: int):
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    return [first + timedelta(days=i) for i in range(last_day)]

def week_dates_from_monday(monday: date):
    return [monday + timedelta(days=i) for i in range(7)]

def assign_rotation_from_initial(ref_monday: date, initial_map: dict, doctors: list, target_dates: list):
    """
    Κανονικός, σαφής αλγόριθμος:
    - ref_monday: η Δευτέρα της αρχικής εβδομάδας (reference week start)
    - initial_map: dict {date: doctor} για τις 7 ημέρες της αρχικής εβδομάδας
    - doctors: λίστα γιατρών (χρησιμοποιείται μόνο για ordering/έλεγχο)
    - target_dates: λίστα ημερομηνιών που θέλουμε να γεμίσουμε (π.χ. όλος ο μήνας)
    Λογική: για κάθε ημερομηνία d:
      weeks_between = floor((d - ref_monday) / 7)
      weekday d.weekday() = wd
      source_weekday = (wd + 2*weeks_between) mod 7
      doctor = initial_map_by_weekday[source_weekday]
    """
    if not initial_map:
        return {}
    # mapping weekday (0=Mon..6=Sun) -> doctor from initial week
    initial_by_wd = {}
    for d, doc in initial_map.items():
        initial_by_wd[d.weekday()] = doc

    assign = {}
    for d in sorted(target_dates):
        weeks_between = (d - ref_monday).days // 7
        wd = d.weekday()
        source_wd = (wd + 2 * weeks_between) % 7
        doc = initial_by_wd.get(source_wd)
        if doc is None:
            # safety fallback: rotate through doctors list if mapping missing
            doc = doctors[(source_wd) % len(doctors)]
        assign[d] = doc
    return assign

def save_state(filepath="schedule_state.pkl"):
    data = {
        "initial_week": {d.isoformat(): doc for d,doc in st.session_state.initial_week.items()},
        "assignments": {d.isoformat(): doc for d,doc in st.session_state.assignments.items()},
        "holidays": {f"{y}-{m}": [d.isoformat() for d in s] for (y,m),s in st.session_state.holidays.items()},
        "generated_months": st.session_state.generated_months
    }
    with open(filepath, "wb") as f:
        pickle.dump(data, f)

def load_state(filepath="schedule_state.pkl"):
    if not os.path.exists(filepath):
        raise FileNotFoundError("Αρχείο κατάστασης δεν βρέθηκε.")
    with open(filepath, "rb") as f:
        data = pickle.load(f)
    st.session_state.initial_week = {datetime.fromisoformat(k).date():v for k,v in data.get("initial_week",{}).items()}
    st.session_state.assignments = {datetime.fromisoformat(k).date():v for k,v in data.get("assignments",{}).items()}
    st.session_state.holidays = defaultdict(set)
    for ym_key, lst in data.get("holidays", {}).items():
        y_str,m_str = ym_key.split("-")
        y,m = int(y_str), int(m_str)
        st.session_state.holidays[(y,m)] = set(datetime.fromisoformat(x).date() for x in lst)
    st.session_state.generated_months = data.get("generated_months", [])

def create_pdf_for_month(year, month, assignments, holidays_set, out_path):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0,10,f"Πρόγραμμα - {calendar.month_name[month]} {year}", ln=True, align="C")
    pdf.ln(4)
    pdf.set_font("Arial","B",11)
    pdf.cell(35,8,"Ημερομηνία",1)
    pdf.cell(35,8,"Ημέρα",1)
    pdf.cell(70,8,"Γιατρός",1)
    pdf.cell(30,8,"Αργία",1)
    pdf.ln()
    pdf.set_font("Arial","",11)
    for d in month_dates(year, month):
        doc = assignments.get(d,"")
        hol = "Ναι" if d in holidays_set else ""
        pdf.cell(35,8,d.strftime("%Y-%m-%d"),1)
        pdf.cell(35,8,calendar.day_name[d.weekday()],1)
        pdf.cell(70,8,doc,1)
        pdf.cell(30,8,hol,1)
        pdf.ln()
    pdf.output(out_path)

# ---------------------------
# App: αρχικοποίηση session_state
# ---------------------------

if 'doctors' not in st.session_state:
    # βάζουμε την ονομαστική σειρά — μπορείς να την αλλάξεις
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]

if 'initial_week' not in st.session_state:
    st.session_state.initial_week = {}   # {date: doctor} για Αρχική Εβδομάδα (7 ημέρες)

if 'assignments' not in st.session_state:
    st.session_state.assignments = {}    # {date: doctor} για όλα τα δημιουργημένα

if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)  # {(y,m): set(dates)}

if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []  # list of (y,m) σε σειρά δημιουργίας

# ---------------------------
# UI (Ελληνικά)
# ---------------------------

st.set_page_config(page_title="Scheduler Εφημεριών", layout="wide")
st.title("Scheduler Εφημεριών — Περιστροφή: 2 ημέρες πίσω / εβδομάδα")

# στήλες: αριστερά έλεγχοι, δεξιά προβολή
left, right = st.columns([2,3])

with left:
    st.header("Βήμα 1 — Αρχική εβδομάδα (χειροκίνητη)")
    chosen_date = st.date_input("Επίλεξε οποιαδήποτε ημέρα της αρχικής εβδομάδας (θα χρησιμοποιηθεί η Δευτέρα της εβδομάδας αυτής)", value=date(2026,1,12))
    ref_monday = monday_of(chosen_date)
    st.markdown(f"**Αρχική εβδομάδα (Δευτέρα έως Κυριακή):** {ref_monday.isoformat()} — { (ref_monday+timedelta(days=6)).isoformat() }")
    week_dates = week_dates_from_monday(ref_monday)

    st.write("Επίλεξε γιατρό για κάθε ημέρα (υποχρεωτικά):")
    # ξεχωριστά selectboxes με μοναδικά keys (based on date) — έτσι ΔΕΝ "χάνονται"
    temp_initial = {}
    for d in week_dates:
        key = f"init_{d.isoformat()}"
        default = st.session_state.initial_week.get(d, st.session_state.doctors[0])
        sel = st.selectbox(f"{calendar.day_name[d.weekday()]} {d.isoformat()}", st.session_state.doctors, index=st.session_state.doctors.index(default), key=key)
        temp_initial[d] = sel

    if st.button("Αποθήκευση Αρχικής Εβδομάδας"):
        # validate: πρέπει να έχουμε 7 διαφορετικές/έγκυρες τιμές (επιτρέπουμε επαναλήψεις αν θέλεις)
        missing = [d for d,doc in temp_initial.items() if doc not in st.session_state.doctors]
        if missing:
            st.error("Επιλέξτε γιατρό για κάθε ημέρα από τη λίστα.")
        else:
            st.session_state.initial_week = temp_initial.copy()
            st.success("Αρχική εβδομάδα αποθηκεύτηκε.")

    st.markdown("---")
    st.header("Βήμα 2 — Επιλογή μήνα & δημιουργία")
    y = st.number_input("Έτος", min_value=2000, max_value=2100, value=date.today().year)
    m = st.selectbox("Μήνας", list(range(1,13)), index=date.today().month-1)
    if st.button("Δημιούργησε πρόγραμμα για τον μήνα"):
        if not st.session_state.initial_week or len(st.session_state.initial_week) < 7:
            st.error("Δεν έχετε αποθηκεύσει την αρχική εβδομάδα με 7 γιατρούς.")
        else:
            # υπολογισμός assignments για τον μήνα
            dates = month_dates(y,m)
            new_assign = assign_rotation_from_initial(ref_monday, st.session_state.initial_week, st.session_state.doctors, dates)
            st.session_state.assignments.update(new_assign)
            if (y,m) not in st.session_state.generated_months:
                st.session_state.generated_months.append((y,m))
            st.success(f"Πρόγραμμα δημιουργήθηκε για {calendar.month_name[m]} {y}.")

    st.markdown("---")
    st.header("Βήμα 3 — Αργίες (δεν επηρεάζουν περιστροφή)")
    if st.session_state.generated_months:
        sel_month_for_hols = st.selectbox("Επίλεξε μήνα για αργίες", st.session_state.generated_months, key="hol_month_select")
        y_h, m_h = sel_month_for_hols
        dates_for_h = month_dates(y_h, m_h)
        date_labels = [f"{d.isoformat()} - {calendar.day_name[d.weekday()]}" for d in dates_for_h]
        current_defaults = [f"{d.isoformat()} - {calendar.day_name[d.weekday()]}" for d in st.session_state.holidays.get((y_h,m_h), set()) if d in dates_for_h]
        sel = st.multiselect("Επίλεξε αργίες για αυτόν τον μήνα", date_labels, default=current_defaults)
        # Apply only when button pressed
        if st.button("Εφαρμογή αργιών για τον μήνα"):
            chosen = set()
            for s in sel:
                iso = s.split(" - ")[0]
                chosen.add(datetime.fromisoformat(iso).date())
            st.session_state.holidays[(y_h,m_h)] = chosen
            st.success("Αργίες αποθηκεύτηκαν για τον μήνα.")

    st.markdown("---")
    st.header("Αποθήκευση / Φόρτωση / Επαναφορά")
    col_save, col_load, col_reset = st.columns(3)
    if col_save.button("Αποθήκευση κατάστασης"):
        try:
            save_state()
            st.success("Κατάσταση αποθηκεύτηκε σε schedule_state.pkl")
        except Exception as e:
            st.error(f"Αποτυχία αποθήκευσης: {e}")

    if col_load.button("Φόρτωση κατάστασης"):
        try:
            load_state()
            st.success("Κατάσταση φορτώθηκε.")
        except Exception as e:
            st.error(f"Αποτυχία φόρτωσης: {e}")

    if col_reset.button("Επαναφορά / Διαγραφή"):
        st.session_state.initial_week = {}
        st.session_state.assignments = {}
        st.session_state.holidays = defaultdict(set)
        st.session_state.generated_months = []
        st.success("Όλα διαγράφηκαν.")

with right:
    st.header("Προβολή / Έλεγχος")
    if not st.session_state.generated_months:
        st.info("Δεν υπάρχει δημιουργημένος μήνας — δημιούργησε έναν από τη στήλη στα αριστερά.")
    else:
        # επιλογή ποιον δημιουργημένο μήνα να δείξουμε
        view_month = st.selectbox("Προβολή μήνα", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
        vy, vm = view_month
        st.subheader(f"{calendar.month_name[vm]} {vy}")
        dates = month_dates(vy, vm)
        rows = []
        for d in dates:
            rows.append({
                "Ημερομηνία": d,
                "Ημέρα": calendar.day_name[d.weekday()],
                "Γιατρός": st.session_state.assignments.get(d, ""),
                "Αργία": "Ναι" if d in st.session_state.holidays.get((vy,vm), set()) else ""
            })
        df_view = pd.DataFrame(rows)
        st.dataframe(df_view, height=520)

        # balance cumulative
        st.subheader("Πίνακας Ισορροπίας (συσσωρευτικά)")
        balance = []
        for doc in st.session_state.doctors:
            fr = sum(1 for d,dd in st.session_state.assignments.items() if dd==doc and d.weekday()==4)
            sa = sum(1 for d,dd in st.session_state.assignments.items() if dd==doc and d.weekday()==5)
            su = sum(1 for d,dd in st.session_state.assignments.items() if dd==doc and d.weekday()==6)
            hol_non = 0
            for (ymk, hols) in st.session_state.holidays.items():
                for hd in hols:
                    if st.session_state.assignments.get(hd)==doc and hd.weekday() not in (5,6):
                        hol_non += 1
            balance.append({"Γιατρός": doc, "Παρασκευές": fr, "Σάββατα": sa, "Κυριακές": su, "Αργίες (μη Σ/Κ)": hol_non})
        st.dataframe(pd.DataFrame(balance).set_index("Γιατρός"))

        # PDF export & download
        st.subheader("Εξαγωγή / Εκτύπωση")
        if st.button("Δημιουργία PDF και Λήψη"):
            try:
                outname = f"schedule_{vy}_{vm}.pdf"
                create_pdf_for_month(vy, vm, st.session_state.assignments, st.session_state.holidays.get((vy,vm), set()), outname)
                with open(outname, "rb") as f:
                    st.download_button("Κατέβασε PDF", f, file_name=outname, mime="application/pdf")
                st.success(f"PDF δημιουργήθηκε: {outname}")
            except Exception as e:
                st.error(f"Σφάλμα PDF: {e}")

# ---------------------------
# Τέλος
# ---------------------------
