import streamlit as st
import datetime
import calendar
import pandas as pd
from collections import defaultdict
from fpdf import FPDF

# ----------------------------
# CONSTANTS & SETUP
# ----------------------------
DOCTORS = ["Χριστίνα", "Αθηνά", "Μαρία", "Έλια", "Αλέξανδρος", "Εύα", "Έλενα"]

DOCTOR_COLORS = {
    "Έλενα": (255, 182, 193),
    "Εύα": (152, 251, 152),
    "Μαρία": (176, 196, 222),
    "Αθηνά": (255, 250, 205),
    "Αλέξανδρος": (221, 160, 221),
    "Έλια": (175, 238, 238),
    "Χριστίνα": (245, 222, 179),
}

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
GREEK_WEEKDAY_LABELS = ["Δευ", "Τρι", "Τετ", "Πεμ", "Παρ", "Σαβ", "Κυρ"]

GREEK_MONTHS = [
    "", "Ιανουάριος", "Φεβρουάριος", "Μάρτιος", "Απρίλιος", "Μάιος", "Ιούνιος",
    "Ιούλιος", "Αύγουστος", "Σεπτέμβριος", "Οκτώβριος", "Νοέμβριος", "Δεκέμβριος",
]

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

DOCTOR_ROTATION_INDICES = {
    "Χριστίνα": [0, 1, 2, 0, 1, 2, 0],
    "Αθηνά":    [1, 2, 0, 1, 2, 0, 0],
    "Μαρία":    [2, 0, 1, 2, 0, 0, 1],
    "Έλια":     [0, 1, 2, 0, 0, 1, 2],
    "Αλέξανδρος":[1, 2, 0, 0, 1, 2, 0],
    "Εύα":      [2, 0, 0, 1, 2, 0, 1],
    "Έλενα":    [0, 0, 1, 2, 0, 1, 2]
}

GROUP_NAMES = {0: "Xmas", 1: "Easter", 2: "Common"}

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
def _week_monday(date):
    return date - datetime.timedelta(days=date.weekday())


def _has_nearby_shift(doctor, date, schedule, min_gap=3):
    for d, doc in schedule.items():
        if doc == doctor and d != date and abs((d - date).days) <= min_gap:
            return True
    return False


def _has_weekend_in_adjacent_week(doctor, date, schedule):
    if date.weekday() not in (5, 6):
        return False
    target_wk = _week_monday(date)
    for d, doc in schedule.items():
        if doc == doctor and d.weekday() in (5, 6):
            other_wk = _week_monday(d)
            if abs((target_wk - other_wk).days) == 7:
                return True
    return False


def _shifts_in_week(doctor, date, schedule, exclude_date=None):
    wk = _week_monday(date)
    return sum(
        1 for d, doc in schedule.items()
        if doc == doctor and d != exclude_date and _week_monday(d) == wk
    )


def _total_shifts_in_month(doctor, date, schedule, exclude_date=None):
    return sum(
        1 for d, doc in schedule.items()
        if d != exclude_date and doc == doctor
        and d.year == date.year and d.month == date.month
    )


def _special_bucket(date, holiday_dates):
    if date.weekday() == 5:
        return "sat"
    if date.weekday() == 6:
        return "sun"
    if date in holiday_dates:
        return "hol"
    return None


def _special_count_in_month(doctor, date, schedule, holiday_dates, exclude_date=None):
    bucket = _special_bucket(date, holiday_dates)
    if bucket is None:
        return 0
    return sum(
        1 for d, doc in schedule.items()
        if doc == doctor and d != exclude_date
        and d.year == date.year and d.month == date.month
        and _special_bucket(d, holiday_dates) == bucket
    )


def _month_stats(doctor, date, schedule, exclude_date=None):
    total, has_sat, has_sun = 0, False, False
    for d, doc in schedule.items():
        if d == exclude_date or doc != doctor:
            continue
        if d.year == date.year and d.month == date.month:
            total += 1
            if d.weekday() == 5:
                has_sat = True
            elif d.weekday() == 6:
                has_sun = True
    return total, has_sat, has_sun


def _within_month_cap(doctor, date, schedule, exclude_date=None):
    total, has_sat, has_sun = _month_stats(doctor, date, schedule, exclude_date)
    total += 1
    if date.weekday() == 5:
        has_sat = True
    elif date.weekday() == 6:
        has_sun = True
    limit = 4 if (has_sat and has_sun) else 5
    return total <= limit


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


def get_major_holiday_blocks_in_range(start_date, end_date):
    blocks = []
    for year in range(start_date.year - 2, end_date.year + 2):
        easter_next = orthodox_easter(year + 1)
        g_fri_next = easter_next - datetime.timedelta(days=2)
        s_sat_next = easter_next - datetime.timedelta(days=1)
        sun_e_next = easter_next
        mon_e_next = easter_next + datetime.timedelta(days=1)

        year_packages = [
            {"dates": [datetime.date(year + 1, 1, 1)], "name": "Πρωτοχρονιά (1/1)", "group": "Xmas", "year": year},
            {"dates": [datetime.date(year, 12, 25)], "name": "Χριστούγεννα (25/12)", "group": "Xmas", "year": year},
            {"dates": [datetime.date(year, 12, 31)], "name": "Παραμονή Πρωτοχρονιάς (31/12)", "group": "Xmas", "year": year},
            {"dates": [sun_e_next], "name": "Κυριακή του Πάσχα", "group": "Easter", "year": year},
            {"dates": [mon_e_next], "name": "Δευτέρα του Πάσχα", "group": "Easter", "year": year},
            {"dates": [s_sat_next, datetime.date(year, 12, 24)], "name": "Μεγάλο Σάββατο + 24/12", "group": "Common", "year": year},
            {"dates": [g_fri_next, datetime.date(year, 12, 26)], "name": "Μεγάλη Παρασκευή + 26/12", "group": "Common", "year": year},
        ]

        for pkg in year_packages:
            valid_dates = [d for d in pkg["dates"] if start_date <= d <= end_date]
            if valid_dates:
                blocks.append({
                    "name": f"{pkg['name']} (Κύκλος {year}-{year+1})",
                    "base_name": pkg["name"],
                    "group": pkg["group"],
                    "dates": valid_dates,
                    "year": year,
                    "cycle_id": year,
                })
    return blocks


def is_valid_assignment(doctor, date, schedule, holiday_dates, exclude_date=None,
                        strict_monthly=True, min_gap=3, max_special=1, avoid_consecutive_weekends=True):
    if _has_nearby_shift(doctor, date, schedule, min_gap=min_gap):
        return False
    if _shifts_in_week(doctor, date, schedule, exclude_date=exclude_date) >= 2:
        return False
    if _special_count_in_month(doctor, date, schedule, holiday_dates,
                               exclude_date=exclude_date) >= max_special:
        return False
    if avoid_consecutive_weekends and _has_weekend_in_adjacent_week(doctor, date, schedule):
        return False
    if strict_monthly:
        if not _within_month_cap(doctor, date, schedule, exclude_date=exclude_date):
            return False
    return True


def find_all_violations(schedule):
    return []


# ----------------------------
# SCHEDULING LOGIC
# ----------------------------
def generate_full_schedule(start_date, end_date, initial_week, manual_assignments=None):
    manual_assignments = manual_assignments or {}
    schedule = {}
    warnings = []

    total_days = (end_date - start_date).days + 1
    holiday_names = get_holidays_in_range(start_date, end_date)
    holiday_dates = set(holiday_names.keys())
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)

    if initial_week and isinstance(initial_week, (list, tuple)) and len(initial_week) >= 7:
        week_start_monday = start_date - datetime.timedelta(days=start_date.weekday())
        for i in range(7):
            d = week_start_monday + datetime.timedelta(days=i)
            if start_date <= d <= end_date:
                schedule[d] = initial_week[i]

    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            schedule[d] = doc

    all_major_blocks = sorted(major_blocks, key=lambda b: (b["year"], b["dates"][0]))

    for block in all_major_blocks:
        block_dates = block["dates"]
        if any(bd in schedule for bd in block_dates):
            continue
        
        primary_date = block_dates[0]
        cycle_year = block["year"]
        target_group_name = block["group"]
        
        group_name_to_code = {"Xmas": 0, "Easter": 1, "Common": 2}
        target_group_code = group_name_to_code[target_group_name]

        year_index = (cycle_year - 2026) % 7

        assigned_doc = None
        rotation_candidates = [
            doc for doc in DOCTORS 
            if DOCTOR_ROTATION_INDICES[doc][year_index] == target_group_code
        ]

        for avoid_cons in (True, False):
            for min_gap in (3, 2, 1, 0):
                valid_candidates = [
                    doc for doc in rotation_candidates
                    if is_valid_assignment(doc, primary_date, schedule, holiday_dates, exclude_date=None, 
                                           strict_monthly=True, min_gap=min_gap, max_special=2, avoid_consecutive_weekends=avoid_cons)
                ]
                if valid_candidates:
                    assigned_doc = valid_candidates[0]
                    break
            if assigned_doc:
                break

        if assigned_doc is None:
            for avoid_cons in (True, False):
                for min_gap in (3, 2, 1, 0):
                    valid_candidates = [
                        doc for doc in DOCTORS
                        if is_valid_assignment(doc, primary_date, schedule, holiday_dates, exclude_date=None, 
                                               strict_monthly=True, min_gap=min_gap, max_special=2, avoid_consecutive_weekends=avoid_cons)
                    ]
                    if valid_candidates:
                        assigned_doc = valid_candidates[0]
                        break
                if assigned_doc:
                    break

        if assigned_doc is None:
            assigned_doc = DOCTORS[0]

        for bd in block_dates:
            schedule[bd] = assigned_doc

    all_days = [start_date + datetime.timedelta(days=i) for i in range(total_days)]
    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    minor_dates = {d for d in holiday_dates if d not in all_major_dates}

    special_dates = [
        d for d in all_days
        if d not in schedule and (d.weekday() in (4, 5, 6) or d in holiday_dates)
    ]
    special_dates.sort(key=lambda d: (0 if d in minor_dates else 1 if d.weekday() in (5, 6) else 2, d))

    for d in special_dates:
        chosen = None
        for avoid_cons in (True, False):
            for min_gap in (3, 2, 1, 0):
                for max_special in (1, 2):
                    valid = [doc for doc in DOCTORS if is_valid_assignment(
                        doc, d, schedule, holiday_dates, exclude_date=d,
                        strict_monthly=True, min_gap=min_gap, max_special=max_special, 
                        avoid_consecutive_weekends=avoid_cons)]
                    if valid:
                        chosen = min(valid, key=lambda doc: (
                            _total_shifts_in_month(doc, d, schedule, exclude_date=d)
                        ))
                        break
                if chosen:
                    break
            if chosen:
                break

        if chosen is None:
            chosen = DOCTORS[0]
            warnings.append(f"{d.strftime('%d/%m/%Y')}: καμία έγκυρη επιλογή, ανατέθηκε {chosen}")
        schedule[d] = chosen

    for current_date in all_days:
        if current_date in schedule:
            continue

        chosen = None
        for min_gap in (3, 2, 1, 0):
            valid = [doc for doc in DOCTORS if is_valid_assignment(
                doc, current_date, schedule, holiday_dates, exclude_date=current_date,
                strict_monthly=True, min_gap=min_gap, avoid_consecutive_weekends=False)]
            if valid:
                chosen = min(valid, key=lambda doc: _total_shifts_in_month(doc, current_date, schedule, exclude_date=current_date))
                break

        if chosen is None:
            chosen = DOCTORS[0]
            warnings.append(f"{current_date.strftime('%d/%m/%Y')}: καμία έγκυρη επιλογή, ανατέθηκε {chosen}")
        schedule[current_date] = chosen

    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            schedule[d] = doc

    return schedule, holiday_names, warnings


# ----------------------------
# CHRONOLOGICAL SUMMARY FUNCTIONS
# ----------------------------
def compute_major_holidays_by_doctor(schedule, start_date, end_date):
    blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    sorted_blocks = sorted(blocks, key=lambda b: b["dates"][0])
    
    doctor_rows = {doc: [] for doc in DOCTORS}
    
    for block in sorted_blocks:
        for d in block["dates"]:
            doc = schedule.get(d, "-")
            if doc in doctor_rows:
                weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
                doctor_rows[doc].append({
                    "date_obj": d,
                    "Ακτινολόγος": doc,
                    "Ημερομηνία & Ημέρα": f"{d.strftime('%d/%m/%Y')} ({weekday_str})",
                    "Μεγάλη Εορτή / Πακέτο": block["base_name"]
                })
                
    all_data = []
    for doc in DOCTORS:
        sorted_items = sorted(doctor_rows[doc], key=lambda x: x["date_obj"])
        for item in sorted_items:
            all_data.append({
                "Ακτινολόγος": item["Ακτινολόγος"],
                "Ημερομηνία & Ημέρα": item["Ημερομηνία & Ημέρα"],
                "Μεγάλη Εορτή / Πακέτο": item["Μεγάλη Εορτή / Πακέτο"]
            })
            
    return pd.DataFrame(all_data)


def compute_regular_holidays_chronological(schedule, regular_holidays):
    sorted_hols = sorted(regular_holidays.keys())
    data = []
    for d in sorted_hols:
        doc = schedule.get(d, "-")
        weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
        data.append({
            "date_obj": d,
            "Ημερομηνία": d.strftime('%d/%m/%Y'),
            "Ημέρα": weekday_str,
            "Μικρή Αργία": regular_holidays[d],
            "Ακτινολόγος": doc,
        })
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("date_obj").drop(columns=["date_obj"]).reset_index(drop=True)
    return df


def compute_balance(schedule, start_date, end_date, holiday_names):
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in DOCTORS}
    for date, doc in schedule.items():
        if doc in counts:
            counts[doc][WEEKDAY_LABELS[date.weekday()]] += 1

    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]

    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    
    major_counts = defaultdict(int)
    for block in major_blocks:
        for d in block["dates"]:
            doc = schedule.get(d)
            if doc in DOCTORS:
                major_counts[doc] += 1

    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    regular_counts = defaultdict(int)
    for d in regular_hols:
        doc = schedule.get(d)
        if doc in DOCTORS:
            regular_counts[doc] += 1

    df["Αργίες"] = df["Doctor"].apply(lambda doc: major_counts.get(doc, 0) + regular_counts.get(doc, 0))
    df["Total"] = df["Weekdays"] + df["Fri"] + df["Sat"] + df["Sun"] + df["Αργίες"]
    return df[["Doctor", "Weekdays", "Fri", "Sat", "Sun", "Αργίες", "Total"]]


# ----------------------------
# PDF EXPORT HELPERS (Safe Font Handling)
# ----------------------------
def create_balance_pdf(df, start_date, end_date):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Doctor Balance Summary", align="C", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def display_calendar(schedule, holiday_names):
    manual_assignments = st.session_state.get("manual_assignments", {})
    last_month = None
    for date in sorted(schedule.keys()):
        month_key = (date.year, date.month)
        if month_key != last_month:
            st.markdown(f"## {GREEK_MONTHS[date.month]} {date.year}")
            last_month = month_key
            headers = st.columns(7)
            for i, d in enumerate(WEEKDAY_LABELS):
                headers[i].markdown(f"**{d}**")
            cal = calendar.Calendar(firstweekday=0)
            for week in cal.monthdatescalendar(date.year, date.month):
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day.month == date.month:
                        doc = schedule.get(day, "")
                        is_holiday = day in holiday_names
                        icon = " ✏️" if day in manual_assignments else ""
                        holiday_tag = (f"<br><span style='font-size:10px'>🎉 {holiday_names[day]}</span>"
                                       if is_holiday else "")
                        color = '#%02x%02x%02x' % DOCTOR_COLORS.get(doc, (220, 220, 220))
                        border = "border:2px solid #d9534f;" if is_holiday else ""
                        cols[i].markdown(
                            f"<div style='background-color:{color}; {border} padding:6px; "
                            f"border-radius:4px; text-align:center'>"
                            f"<b>{day.day}</b><br>{doc}{icon}{holiday_tag}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        cols[i].markdown("")


# ----------------------------
# STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="📅 Πρόγραμμα Εφημεριών", layout="wide")
st.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων")
st.markdown("<span style='font-size:14px; color:gray;'>© Γιώργος Μενοίκου, PhD</span>",
            unsafe_allow_html=True)

for key, default in [
    ("manual_assignments", {}), ("schedule", None), ("holiday_names", {}),
    ("balance", None), ("initial_week", None), ("warnings", []),
    ("start_date", datetime.date.today()),
]:
    if key not in st.session_state:
        st.session_state[key] = default

left_col, right_col = st.columns([0.35, 0.65])

with left_col:
    st.subheader("📊 Παραμετροποίηση Εύρους")
    start_date = st.date_input("Ημερομηνία Έναρξης", value=datetime.date(2026, 1, 1))
    end_date = st.date_input("Ημερομηνία Λήξης", value=datetime.date(2026, 12, 31))
    
    if st.button("🚀 Δημιουργία Προγράμματος"):
        st.session_state.start_date = start_date
        holiday_names = get_holidays_in_range(start_date, end_date)
        st.session_state.holiday_names = holiday_names
        
        schedule, holiday_names, warnings = generate_full_schedule(
            start_date, end_date, st.session_state.initial_week, st.session_state.manual_assignments
        )
        st.session_state.schedule = schedule
        st.session_state.warnings = warnings
        st.session_state.balance = compute_balance(schedule, start_date, end_date, holiday_names)
        st.success("Το πρόγραμμα δημιουργήθηκε επιτυχώς!")

    # Κουμπιά & Διαχείριση Χειροκίνητων Αναθέσεων που έλειπαν
    st.markdown("---")
    st.subheader("⚙️ Χειροκίνητες Παρεμβάσεις")
    with st.expander("Προσθήκη / Τροποποίηση Εφημερίας"):
        m_date = st.date_input("Ημερομηνία", value=datetime.date(2026, 1, 1))
        m_doc = st.selectbox("Γιατρός", DOCTORS)
        if st.button("💾 Αποθήκευση Ανάθεσης"):
            st.session_state.manual_assignments[m_date] = m_doc
            st.success(f"Ανατέθηκε η {m_date.strftime('%d/%m/%Y')} στον/ην {m_doc}")
            if st.session_state.schedule:
                st.session_state.schedule[m_date] = m_doc
                st.session_state.balance = compute_balance(st.session_state.schedule, st.session_state.start_date, end_date, st.session_state.holiday_names)
        
        if st.button("🗑️ Εκκαθάριση Χειροκίνητων"):
            st.session_state.manual_assignments = {}
            st.success("Καθαρίστηκαν οι χειροκίνητες αναθέσεις!")

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        st.markdown("---")
        st.subheader("📈 Ισοζύγιο Εφημεριών")
        st.dataframe(st.session_state.balance, use_container_width=True, height=260)
        
        # Κουμπί εξαγωγής PDF
        pdf_bytes = create_balance_pdf(st.session_state.balance, start_date, end_date)
        st.download_button(
            label="📥 Λήψη Ισοζυγίου σε PDF",
            data=pdf_bytes,
            file_name="doctor_balance.pdf",
            mime="application/pdf"
        )

with right_col:
    st.subheader("🗓️ Ημερολόγιο Εφημεριών")
    if st.session_state.warnings:
        with st.expander("⚠️ Προειδοποιήσεις Αυτόματης Δημιουργίας"):
            for w in st.session_state.warnings:
                st.warning(w)

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule, st.session_state.holiday_names)
    else:
        st.info("Πατήστε «Δημιουργία Προγράμματος» για να εμφανιστεί το ημερολόγιο.")
