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
    "Έλενα": (255, 182, 193),
    "Εύα": (152, 251, 152),
    "Μαρία": (176, 196, 222),
    "Αθηνά": (255, 250, 205),
    "Αλέξανδρος": (221, 160, 221),
    "Έλια": (175, 238, 238),
    "Χριστίνα": (245, 222, 179)
}

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

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

def _has_nearby_shift(doctor, date, schedule, max_gap=3):
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

def _total_shifts_in_month(doctor, date, schedule, exclude_date=None):
    year, month = date.year, date.month
    total = 0
    for d, doc in schedule.items():
        if d == exclude_date:
            continue
        if doc == doctor and d.year == year and d.month == month:
            total += 1
    return total

def _specific_weekday_in_month(doctor, date, schedule, exclude_date=None):
    year, month = date.year, date.month
    weekday = date.weekday()
    count = 0
    for d, doc in schedule.items():
        if d == exclude_date:
            continue
        if doc == doctor and d.year == year and d.month == month and d.weekday() == weekday:
            count += 1
    return count

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
    for year in range(start_date.year, end_date.year + 1):
        try:
            easter = orthodox_easter(year)
            s_sat = easter - datetime.timedelta(days=1)
            g_fri = easter - datetime.timedelta(days=2)
            sun_e = easter
            mon_e = easter + datetime.timedelta(days=1)
        except Exception:
            s_sat, g_fri, sun_e, mon_e = None, None, None, None

        year_blocks = [
            ([datetime.date(year, 12, 25)], f"Χριστούγεννα {year}"),
            ([datetime.date(year, 1, 1)], f"Πρωτοχρονιά {year}"),
            ([sun_e] if sun_e else [], f"Κυριακή του Πάσχα {year}"),
            ([mon_e] if mon_e else [], f"Δευτέρα του Πάσχα {year}"),
            ([datetime.date(year, 12, 24), s_sat] if s_sat else [datetime.date(year, 12, 24)], f"Παραμονή Χριστουγέννων & Μεγάλο Σάββατο {year}"),
            ([datetime.date(year, 12, 26), g_fri] if g_fri else [datetime.date(year, 12, 26)], f"2η Χριστουγέννων & Μεγάλη Παρασκευή {year}"),
            ([datetime.date(year, 12, 31)], f"Παραμονή Πρωτοχρονιάς {year}"),
        ]

        for dates, name in year_blocks:
            valid_dates = [d for d in dates if d and start_date <= d <= end_date]
            if valid_dates:
                blocks.append({"name": name, "dates": valid_dates, "year": year})
                
    return blocks

def is_valid_assignment(doctor, date, schedule, exclude_date=None, strict_monthly=True, max_gap=3):
    if _has_nearby_shift(doctor, date, schedule, max_gap=max_gap):
        return False
    if _shifts_in_week(doctor, date, schedule, exclude_date=exclude_date) > 2:
        return False
        
    if date.weekday() in (4, 5, 6):
        doc_count = _specific_weekday_in_month(doctor, date, schedule, exclude_date=exclude_date)
        year, month = date.year, date.month
        weekday = date.weekday()
        
        other_counts = [
            sum(1 for d, doc_name in schedule.items() if d != exclude_date and doc_name == doc and d.year == year and d.month == month and d.weekday() == weekday)
            for doc in DOCTORS if doc != doctor
        ]
        min_others = min(other_counts) if other_counts else 0
        if doc_count > min_others:
            return False

    if strict_monthly:
        if _total_shifts_in_month(doctor, date, schedule, exclude_date=exclude_date) > 5:
            return False
    return True

# ----------------------------
# SCHEDULING LOGIC
# ----------------------------
def generate_full_schedule(start_date, end_date, initial_week, manual_assignments=None):
    manual_assignments = manual_assignments or {}
    schedule = {}
    
    total_days = (end_date - start_date).days + 1
    for day_offset in range(total_days):
        current_date = start_date + datetime.timedelta(days=day_offset)
        week_num = day_offset // 7
        day_of_week = day_offset % 7
        doc_index = (day_of_week + (week_num * 2)) % len(initial_week)
        schedule[current_date] = initial_week[doc_index]

    holiday_names = get_holidays_in_range(start_date, end_date)

    for d, doc in manual_assignments.items():
        if d in schedule:
            schedule[d] = doc

    # ΒΗΜΑ 1: Κατανομή Παρασκευών, Σαββάτων και Κυριακών (κανονικές μέρες)
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    all_major_dates = {d for block in major_blocks for d in block["dates"]}

    weekend_dates = sorted([d for d in schedule.keys() if d.weekday() in (4, 5, 6) and d not in manual_assignments and d not in all_major_dates])
    for d in weekend_dates:
        valid_docs = [doc for doc in DOCTORS if is_valid_assignment(doc, d, schedule, exclude_date=d, strict_monthly=True, max_gap=3)]
        if not valid_docs:
            valid_docs = [doc for doc in DOCTORS if is_valid_assignment(doc, d, schedule, exclude_date=d, strict_monthly=False, max_gap=3)]
        
        if valid_docs:
            best_doc = min(valid_docs, key=lambda doc: (
                _specific_weekday_in_month(doc, d, schedule, exclude_date=d),
                _total_shifts_in_month(doc, d, schedule, exclude_date=d)
            ))
            schedule[d] = best_doc

    # Παρακολούθηση ποιος γιατρός έκανε Χριστούγεννα (24, 25, 26, 31 Δεκεμβρίου) ώστε να αποκλείεται από την 1/1 του επόμενου έτους
    xmas_doctors_by_year = {y: set() for y in range(start_date.year - 1, end_date.year + 2)}

    # Πρώτα προσδιορίζουμε ποιος παίρνει τα Χριστουγεννιάτικα πακέτα (24, 25, 26, 31)
    doctor_yearly_major_count = {doc: {y: 0 for y in range(start_date.year, end_date.year + 2)} for doc in DOCTORS}

    # Διαχωρισμός πακέτων Πρωτοχρονιάς (1/1) από τα υπόλοιπα μεγάλα πακέτα για να εφαρμοστεί σωστά ο αποκλεισμός
    for block in major_blocks:
        block_dates = block["dates"]
        block_year = block["year"]
        is_jan_1 = (len(block_dates) == 1 and block_dates[0].month == 1 and block_dates[0].day == 1)

        assigned_doc = None
        for d in block_dates:
            if d in manual_assignments:
                assigned_doc = manual_assignments[d]
                break

        if not assigned_doc:
            eligible_docs = [doc for doc in DOCTORS if doctor_yearly_major_count[doc][block_year if not is_jan_1 else block_year - 1] == 0]
            
            # Ειδικός κανόνας: Αν είναι 1/1, αποκλείονται όσοι έκαναν Χριστούγεννα/31/12 τον Δεκέμβριο του προηγούμενου έτους
            if is_jan_1:
                prev_year = block_year - 1
                eligible_docs = [doc for doc in eligible_docs if doc not in xmas_doctors_by_year.get(prev_year, set())]

            if not eligible_docs:
                eligible_docs = DOCTORS

            valid_docs = []
            for doc in eligible_docs:
                if all(is_valid_assignment(doc, d, schedule, exclude_date=d, strict_monthly=False, max_gap=2) for d in block_dates):
                    valid_docs.append(doc)
            
            if not valid_docs:
                valid_docs = eligible_docs

            best_doc = min(valid_docs, key=lambda doc: sum(doctor_yearly_major_count[doc].values()))
        else:
            best_doc = assigned_doc

        for d in block_dates:
            if d not in manual_assignments and d in schedule:
                schedule[d] = best_doc
        
        # Αν το πακέτο είναι εντός Δεκεμβρίου (24, 25, 26, 31), καταγράφουμε τον γιατρό για τον αποκλεισμό της 1/1 του επόμενου έτους
        for d in block_dates:
            if d.month == 12:
                xmas_doctors_by_year[block_year].add(best_doc)

        if not is_jan_1:
            doctor_yearly_major_count[best_doc][block_year] += 1
        else:
            doctor_yearly_major_count[best_doc][block_year - 1] += 1

    # Κατανομή υπόλοιπων (μικρών) αργιών
    regular_dates_in_range = [d for d in holiday_names.keys() if d not in all_major_dates]
    for d in regular_dates_in_range:
        if d in manual_assignments:
            continue
        valid_docs = [doc for doc in DOCTORS if is_valid_assignment(doc, d, schedule, exclude_date=d, strict_monthly=True, max_gap=3)]
        if not valid_docs:
            valid_docs = [doc for doc in DOCTORS if is_valid_assignment(doc, d, schedule, exclude_date=d, strict_monthly=False, max_gap=3)]
        
        if valid_docs:
            best_doc = min(valid_docs, key=lambda doc: (
                sum(1 for date, doc_name in schedule.items() if doc_name == doc and date in holiday_names),
                _total_shifts_in_month(doc, d, schedule, exclude_date=d)
            ))
        else:
            best_doc = DOCTORS[0]
        schedule[d] = best_doc

    for d, doc in manual_assignments.items():
        if d in schedule:
            schedule[d] = doc

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

def compute_major_holidays_summary(schedule, start_date, end_date):
    blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    summary = {doc: {"Count": 0, "Details": []} for doc in DOCTORS}
    
    for block in blocks:
        primary_date = block["dates"][0]
        doc = schedule.get(primary_date, "-")
        if doc in summary:
            summary[doc]["Count"] += 1
            dates_str = ", ".join([d.strftime('%d/%m/%Y') for d in block["dates"]])
            summary[doc]["Details"].append(f"• {block['name']} ({dates_str})")

    data = []
    for doc in DOCTORS:
        data.append({
            "Ακτινολόγος": doc,
            "Σύνολο Πακέτων": summary[doc]["Count"],
            "Ανατεθειμένα Πακέτα": "\n".join(summary[doc]["Details"]) if summary[doc]["Details"] else "Κανένα"
        })
    return pd.DataFrame(data)

def compute_regular_holidays_summary(schedule, regular_holidays):
    summary = {doc: {"Count": 0, "Details": []} for doc in DOCTORS}
    for d in sorted(regular_holidays.keys()):
        doc = schedule.get(d, "-")
        if doc in summary:
            summary[doc]["Count"] += 1
            summary[doc]["Details"].append(f"{d.strftime('%d/%m/%Y')} ({regular_holidays[d]})")
    data = []
    for doc in DOCTORS:
        data.append({
            "Ακτινολόγος": doc,
            "Σύνολο": summary[doc]["Count"],
            "Ημερομηνίες & Εορτές": ", ".join(summary[doc]["Details"]) if summary[doc]["Details"] else "Καμία"
        })
    return pd.DataFrame(data)

# ----------------------------
# PDF HELPERS
# ----------------------------
def create_balance_pdf(df, start_date, end_date, filename="balance_summary.pdf"):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'DejaVuSans.ttf', uni=True)
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Doctor Balance Summary", ln=True, align="C")
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"Period: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}", ln=True, align="C")
    pdf.ln(6)
    col_widths = [45, 25, 18, 18, 18, 22, 22]
    pdf.set_font("DejaVu", "B", 12)
    for h, w in zip(df.columns, col_widths):
        pdf.cell(w, 8, str(h), border=1, align="C")
    pdf.ln()
    pdf.set_font("DejaVu", "", 12)
    for _, row in df.iterrows():
        for val, w in zip(row, col_widths):
            pdf.cell(w, 8, str(val), border=1, align="C")
        pdf.ln()
    pdf.output(filename)
    return filename

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
st.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων")
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
    st.subheader("📊 Κατάσταση Εφημεριών Εύρους")
    if st.session_state.start_date and st.session_state.schedule:
        manual_date = st.date_input("Επιλέξετε ημερομηνία για αλλαγή", min_value=min(st.session_state.schedule.keys()), max_value=max(st.session_state.schedule.keys()))
        manual_doctor = st.selectbox("Επιλογή Ακτινολόγου", DOCTORS)
        if st.button("✅ Επικύρωση"):
            st.session_state.manual_assignments[manual_date] = manual_doctor
            st.session_state.schedule[manual_date] = manual_doctor
            st.session_state.balance = compute_balance(st.session_state.schedule, holiday_dates=set(st.session_state.holiday_names.keys()))
            st.success(f"Ο/Η {manual_doctor} ανατέθηκε στις {manual_date.strftime('%d/%m/%Y')}")
            st.rerun()

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        st.dataframe(st.session_state.balance, use_container_width=True, height=260)

        if st.session_state.schedule:
            st.markdown("### 🎄🐣 Κατάσταση 7 Πακέτων Μεγάλων Εορτών")
            major_df = compute_major_holidays_summary(st.session_state.schedule, st.session_state.start_date, max(st.session_state.schedule.keys()))
            st.dataframe(major_df, use_container_width=True, height=240)

        if st.session_state.holiday_names:
            major_blocks = get_major_holiday_blocks_in_range(st.session_state.start_date, max(st.session_state.schedule.keys()))
            all_major_dates = {d for block in major_blocks for d in block["dates"]}
            regular_hols_dict = {d: n for d, n in st.session_state.holiday_names.items() if d not in all_major_dates}
            if regular_hols_dict:
                with st.expander("🎈 Ανάλυση Μικρών Αργιών"):
                    regular_df = compute_regular_holidays_summary(st.session_state.schedule, regular_hols_dict)
                    st.dataframe(regular_df, use_container_width=True)

        if st.button("📄 Εξαγωγή κατάστασης σε PDF"):
            pdf_file = create_balance_pdf(st.session_state.balance, st.session_state.start_date, max(st.session_state.schedule.keys()))
            with open(pdf_file, "rb") as f:
                st.download_button("⬇️ Κατέβασε κατάσταση σε PDF", f, file_name=pdf_file)

with right_col:
    selected_date = st.date_input("Ημερομηνία έναρξης:", datetime.date.today())
    week_dates = [selected_date - datetime.timedelta(days=selected_date.weekday()) + datetime.timedelta(days=i) for i in range(7)]

    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            initial_week[d] = st.selectbox(d.strftime("%a %d/%m"), DOCTORS, index=i % 7, key=f"doc_{d}")

    if st.button("💾 Αποθήκευση Αρχικής Ρότας"):
        st.session_state.initial_week = [initial_week[d] for d in sorted(initial_week)]
        st.session_state.start_date = week_dates[0]
        st.rerun()

    if st.session_state.initial_week:
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start date", st.session_state.start_date)
        with c2:
            default_end = start_date + datetime.timedelta(days=30)
            end_date = st.date_input("End date", default_end)

        if st.button("🗓️ Δημιουργία Προγράμματος"):
            sch, hols = generate_full_schedule(
                start_date, end_date, st.session_state.initial_week,
                manual_assignments=st.session_state.manual_assignments
            )
            st.session_state.schedule = sch
            st.session_state.holiday_names = hols
            st.session_state.balance = compute_balance(sch, holiday_dates=set(hols.keys()))
            st.rerun()

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule, st.session_state.holiday_names)
