import streamlit as st
import datetime
import calendar
import pandas as pd
from fpdf import FPDF

# ----------------------------
# CONSTANTS & SETUP
# ----------------------------
DOCTORS = ["Χριστίνα", "Αθηνά", "Μαρία", "Έλια", "Αλέξανδρος", "Εύα", "Έλενα"]

DOCTOR_COLORS = {
    "Έλενα": (255, 182, 193),       # Anoixto Roz
    "Εύα": (152, 251, 152),         # Anoixto Prasino
    "Μαρία": (176, 196, 222),       # Anoixto Mple
    "Αθηνά": (255, 250, 205),       # Kitrino Lemoniou
    "Αλέξανδρος": (221, 160, 221),   # Mov / Plum
    "Έλια": (175, 238, 238),        # Tourkouaz
    "Χριστίνα": (245, 222, 179)     # Mpez / Wheat
}

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
ROTATION_BASE_YEAR = 2026

FIXED_HOLIDAYS = [
    (1, 1, "Πρωτοχρονιά"),
    (1, 6, "Θεοφάνεια"),
    (3, 25, "Ευαγγελισμός / Εθνική Εορτή"),
    (4, 1, "Εθνική Εορτή Κύπρου"),
    (5, 1, "Πρωτομαγιά"),
    (8, 15, "Κοίμηση της Θεοτόκου"),
    (10, 1, "Ημέρα Ανεξαρτησίας Κύπρου"),
    (10, 28, "Ημέρα του Όχι"),
    (12, 24, "Παραμονή Χριστουγέννων"),
    (12, 25, "Χριστούγεννα"),
    (12, 26, "Δεύτερη μέρα Χριστουγέννων"),
    (12, 31, "Παραμονή Πρωτοχρονιάς"),
]

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
def _week_monday(date):
    return date - datetime.timedelta(days=date.weekday())

def _has_nearby_shift(doctor, date, schedule, max_gap=2):
    for d, doc in schedule.items():
        if doc == doctor and d != date and abs((d - date).days) <= max_gap:
            return True
    return False

def _shifts_in_week(doctor, date, schedule, exclude_date=None):
    wk = _week_monday(date)
    return sum(
        1 for d, doc in schedule.items()
        if doc == doctor and d != exclude_date and _week_monday(d) == wk
    )

def _count_doctor_weekends_in_month(doctor, date, schedule, exclude_date=None):
    year, month = date.year, date.month
    weekends_count = 0
    for d, doc in schedule.items():
        if d == exclude_date:
            continue
        if doc == doctor and d.year == year and d.month == month:
            if d.weekday() in (5, 6):
                weekends_count += 1
    return weekends_count

def _total_shifts_in_month(doctor, date, schedule, exclude_date=None):
    year, month = date.year, date.month
    total = 0
    for d, doc in schedule.items():
        if d == exclude_date:
            continue
        if doc == doctor and d.year == year and d.month == month:
            total += 1
    return total

def is_valid_assignment(doctor, date, schedule, exclude_date=None):
    if _has_nearby_shift(doctor, date, schedule, max_gap=2):
        return False
    if _shifts_in_week(doctor, date, schedule, exclude_date=exclude_date) >= 2:
        return False
        
    total_m = _total_shifts_in_month(doctor, date, schedule, exclude_date=exclude_date)
    if total_m >= 5:
        return False
        
    return True

# ----------------------------
# HOLIDAY HELPERS
# ----------------------------
def orthodox_easter(year):
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    julian_easter = datetime.date(year, month, day)
    return julian_easter + datetime.timedelta(days=13)

def get_cyprus_holidays(year):
    holidays = {}
    for month, day, name in FIXED_HOLIDAYS:
        holidays[datetime.date(year, month, day)] = name

    easter = orthodox_easter(year)
    movable = {
        easter - datetime.timedelta(days=48): "Καθαρά Δευτέρα",
        easter - datetime.timedelta(days=2): "Μεγάλη Παρασκευή",
        easter - datetime.timedelta(days=1): "Μεγάλο Σάββατο",
        easter: "Κυριακή του Πάσχα",
        easter + datetime.timedelta(days=1): "Δευτέρα του Πάσχα",
        easter + datetime.timedelta(days=50): "Δευτέρα Αγίου Πνεύματος",
    }
    holidays.update(movable)
    return holidays

def get_holidays_in_range(start_date, end_date):
    holidays = {}
    for year in range(start_date.year, end_date.year + 1):
        holidays.update(get_cyprus_holidays(year))
    return {d: name for d, name in holidays.items() if start_date <= d <= end_date}

def get_major_holidays_in_range(start_date, end_date):
    target_dates = {}
    for year in range(start_date.year, end_date.year + 1):
        c_dates = [
            (datetime.date(year, 1, 1), "Πρωτοχρονιά"),
            (datetime.date(year, 12, 24), "Παραμονή Χριστουγέννων"),
            (datetime.date(year, 12, 25), "Χριστούγεννα"),
            (datetime.date(year, 12, 26), "Δεύτερη μέρα Χριστουγέννων"),
            (datetime.date(year, 12, 31), "Παραμονή Πρωτοχρονιάς"),
        ]
        for d, name in c_dates:
            if start_date <= d <= end_date:
                target_dates[d] = name
        
        try:
            easter = orthodox_easter(year)
            e_dates = [
                (easter - datetime.timedelta(days=2), "Μεγάλη Παρασκευή"),
                (easter - datetime.timedelta(days=1), "Μεγάλο Σάββατο"),
                (easter, "Κυριακή του Πάσχα"),
                (easter + datetime.timedelta(days=1), "Δευτέρα του Πάσχα"),
            ]
            for d, name in e_dates:
                if start_date <= d <= end_date:
                    target_dates[d] = name
        except Exception:
            pass
            
    return dict(sorted(target_dates.items()))

# ----------------------------
# HYBRID SCHEDULING LOGIC
# ----------------------------
def generate_hybrid_schedule(start_date, end_date, initial_week, manual_assignments=None):
    manual_assignments = manual_assignments or {}
    
    # 1. Dimioyrgia vasikis rotas gia oles tis imeres (ase tis kathimerines na akoloythoyn ti rota)
    schedule = {}
    total_days = (end_date - start_date).days + 1
    for day_offset in range(total_days):
        current_date = start_date + datetime.timedelta(days=day_offset)
        week_num = day_offset // 7
        day_of_week = day_offset % 7
        doc_index = (day_of_week + (week_num * 2)) % len(initial_week)
        schedule[current_date] = initial_week[doc_index]

    # Efarmogi xeirokinitwn allagwn prwta
    for d, doc in manual_assignments.items():
        if d in schedule:
            schedule[d] = doc

    holiday_names = get_holidays_in_range(start_date, end_date)
    
    # 2. Entopismos Savvatokyriakwn & Argion pou prepei na rythmistoyn dikaia
    # Mazeyoyme oles tis imeres S/K i argies
    special_dates = sorted(list(set(list(holiday_names.keys()) + [d for d, dt in schedule.items() if d.weekday() in (5, 6)])))
    special_dates = [d for d in special_dates if start_date <= d <= end_date]

    # Proterotita sta S/K: Oloi na paroun 1 S/K/argia prin pane gia 2o, kai synolikes efimeries 4-5
    # Trexoyme ena diorthotiko pass gia tis eidikes imeres (S/K & argies)
    for d in special_dates:
        if d in manual_assignments:
            continue
            
        current_doc = schedule[d]
        # Elegxoyme an o trexon giatros exei idi poly fortio (>=5) i parei polla S/K enw alloi exoyn 0
        sks = _count_doctor_weekends_in_month(current_doc, d, schedule, exclude_date=d)
        total_s = _total_shifts_in_month(current_doc, d, schedule, exclude_date=d)
        
        # An o giatros den einai egkyros (exei hdi polles efimeries i paraviazei apostasi $\pm 2$), ton allazoyme
        if not is_valid_assignment(current_doc, d, schedule, exclude_date=d):
            # Vriskoyme ton kalytero diatithemeno giatro
            valid_docs = [doc for doc in DOCTORS if is_valid_assignment(doc, d, schedule, exclude_date=d)]
            if valid_docs:
                # Protimisame ayton me ta ligotera S/K kai synolikes efimeries
                best_doc = min(valid_docs, key=lambda doc: (_count_doctor_weekends_in_month(doc, d, schedule, exclude_date=d), _total_shifts_in_month(doc, d, schedule, exclude_date=d)))
                schedule[d] = best_doc

    # 3. Telikos elegxos isis katanomis (4-5 efimeries ana giatro) stis kathimerines an xreiazetai
    # (Diashmalizoume oti kanenas den menei me <4 i >5 an einai efikto)
    for _ in range(2): # 2 perasmata diorthosis
        shift_counts = {doc: _total_shifts_in_month(doc, start_date, schedule) for doc in DOCTORS}
        overloaded = [doc for doc, cnt in shift_counts.items() if cnt > 5]
        underloaded = [doc for doc, cnt in shift_counts.items() if cnt < 4]
        
        if not overloaded and not underloaded:
            break
            
        # An yparxoyn anisorropies, metakynoyme mias meras efimeria (oxi S/K) an yparxei dynatotita
        for ov in overloaded:
            for under in underloaded:
                # Vriskoyme mia efimeria toy overloaded pou den einai S/K oyte argia
                ov_dates = [d for d, doc in schedule.items() if doc == ov and d.weekday() not in (5, 6) and d not in holiday_names and d not in manual_assignments]
                for od in ov_dates:
                    if is_valid_assignment(under, od, schedule, exclude_date=od):
                        schedule[od] = under
                        break
                break

    return schedule, holiday_names

# ----------------------------
# BALANCE & REPORTING
# ----------------------------
def compute_balance(schedule, holiday_dates=None):
    holiday_dates = holiday_dates or set()
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in DOCTORS}
    holiday_counts = {doc: 0 for doc in DOCTORS}
    for date, doc in schedule.items():
        if doc not in counts:
            continue
        wd = date.weekday()
        counts[doc][WEEKDAY_LABELS[wd]] += 1
        if date in holiday_dates:
            holiday_counts[doc] += 1
    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]
    df["Αργίες"] = df["Doctor"].map(holiday_counts)
    df["Total"] = df["Weekdays"] + df["Fri"] + df["Sat"] + df["Sun"]
    return df[["Doctor", "Weekdays", "Fri", "Sat", "Sun", "Αργίες", "Total"]]

def display_calendar(schedule, holiday_names):
    manual_assignments = st.session_state.get("manual_assignments", {})
    last_month = None
    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            st.markdown(f"## {month_name}")
            last_month = month_name
            headers = st.columns(7)
            for i, d in enumerate(WEEKDAY_LABELS):
                headers[i].markdown(f"**{d}**")
            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(date.year, date.month)
            for week in weeks:
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day.month == date.month:
                        doc = schedule.get(day, "")
                        is_holiday = day in holiday_names
                        icon = " ✏️" if day in manual_assignments else ""
                        holiday_tag = f"<br><span style='font-size:10px'>🎉 {holiday_names[day]}</span>" if is_holiday else ""
                        color = '#%02x%02x%02x' % DOCTOR_COLORS.get(doc, (220, 220, 220))
                        border = "border:2px solid #d9534f;" if is_holiday else ""
                        cols[i].markdown(
                            f"<div style='background-color:{color}; {border} padding:6px; border-radius:4px; text-align:center'>"
                            f"<b>{day.day}</b><br>{doc}{icon}{holiday_tag}</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        cols[i].markdown("")

# ----------------------------
# STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="📅 Πρόγραμμα Εφημεριών", layout="wide")
st.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων (Yvridiko Systima)")
st.markdown("<span style='font-size:14px; color:gray;'>© Γιώργος Μενοίκου, PhD</span>", unsafe_allow_html=True)

if "manual_assignments" not in st.session_state:
    st.session_state.manual_assignments = {}
if "schedule" not in st.session_state:
    st.session_state.schedule = None
if "holiday_names" not in st.session_state:
    st.session_state.holiday_names = {}
if "balance" not in st.session_state:
    st.session_state.balance = None
if "initial_week" not in st.session_state:
    st.session_state.initial_week = None
if "start_date" not in st.session_state:
    st.session_state.start_date = datetime.date.today()

left_col, right_col = st.columns([0.35, 0.65])

with left_col:
    st.subheader("📊 Κατάσταση Εφημεριών")
    if st.session_state.start_date and st.session_state.schedule:
        manual_date = st.date_input("Epilexte imerominia gia allagi", min_value=min(st.session_state.schedule.keys()), max_value=max(st.session_state.schedule.keys()))
        manual_doctor = st.selectbox("Epilogi Aktinologoy", DOCTORS)
        if st.button("✅ Epikyrwsi Allagis"):
            st.session_state.manual_assignments[manual_date] = manual_doctor
            st.session_state.schedule[manual_date] = manual_doctor
            st.session_state.balance = compute_balance(st.session_state.schedule, holiday_dates=set(st.session_state.holiday_names.keys()))
            st.success(f"Anatethike ston/stin {manual_doctor} stis {manual_date.strftime('%d/%m/%Y')}")
            st.rerun()

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        st.dataframe(st.session_state.balance, use_container_width=True, height=260)

with right_col:
    selected_date = st.date_input("Imerominia enarxis:", datetime.date.today())
    week_dates = [selected_date - datetime.timedelta(days=selected_date.weekday()) + datetime.timedelta(days=i) for i in range(7)]

    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            initial_week[d] = st.selectbox(d.strftime("%a %d/%m"), DOCTORS, index=i % 7, key=f"doc_{d}")

    if st.button("💾 Apothikefsi Arxikis Rotas"):
        st.session_state.initial_week = [initial_week[d] for d in sorted(initial_week)]
        st.session_state.start_date = week_dates[0]
        st.rerun()

    if st.session_state.initial_week:
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start date", st.session_state.start_date)
        with c2:
            end_date = st.date_input("End date", st.session_state.start_date + datetime.timedelta(days=30))

        if st.button("🗓️ Dimiourgia Programmatos"):
            sch, hols = generate_hybrid_schedule(
                start_date, end_date, st.session_state.initial_week,
                manual_assignments=st.session_state.manual_assignments
            )
            st.session_state.schedule = sch
            st.session_state.holiday_names = hols
            st.session_state.balance = compute_balance(sch, holiday_dates=set(hols.keys()))
            st.rerun()

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule, st.session_state.holiday_names)
