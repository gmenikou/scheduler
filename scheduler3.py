import streamlit as st
import datetime
import calendar
import pandas as pd
from fpdf import FPDF
from ortools.sat.python import cp_model

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

# ----------------------------
# CP-SAT SCHEDULING LOGIC
# ----------------------------
def generate_full_schedule(start_date, end_date, rota_sequence, manual_assignments=None):
    manual_assignments = manual_assignments or {}
    
    total_days = (end_date - start_date).days + 1
    dates = [start_date + datetime.timedelta(days=i) for i in range(total_days)]
    
    holiday_names = get_holidays_in_range(start_date, end_date)
    holiday_dates = set(holiday_names.keys())
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)

    model = cp_model.CpModel()
    
    x = {}
    for d in dates:
        for doc in DOCTORS:
            x[(d, doc)] = model.NewBoolVar(f"x_{d}_{doc}")

    # 1. Κάθε μέρα ακριβώς 1 γιατρός
    for d in dates:
        model.Add(sum(x[(d, doc)] for doc in DOCTORS) == 1)

    # 2. Χειροκίνητες αναθέσεις
    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            model.Add(x[(d, doc)] == 1)

    # 3. Αποφυγή κοντινών εφημεριών (min gap >= 2 μέρες)
    for doc in DOCTORS:
        for i in range(len(dates)):
            for j in range(i + 1, min(i + 3, len(dates))):
                model.Add(x[(dates[i], doc)] + x[(dates[j], doc)] <= 1)

    # 4. ΕΛΑΣΤΙΚΟΣ ΚΑΝΟΝΑΣ: Επιθυμητό μέγιστο 1 Σαββατοκύριακο/αργία ανά μήνα ανά γιατρό
    months = sorted(list(set((d.year, d.month) for d in dates)))
    overtime_penalties = []
    for year, month in months:
        month_special_dates = [
            d for d in dates 
            if d.year == year and d.month == month and (d.weekday() in (5, 6) or d in holiday_dates)
        ]
        if month_special_dates:
            for doc in DOCTORS:
                excess = model.NewIntVar(0, len(month_special_dates), f"excess_{doc}_{year}_{month}")
                model.Add(sum(x[(d, doc)] for d in month_special_dates) - 1 <= excess)
                overtime_penalties.append(excess)

    # 5. Απόλυτη Ισότητα στα Μεγάλα Πακέτα Εορτών
    for block in major_blocks:
        block_dates = block["dates"]
        for doc in DOCTORS:
            for bd in block_dates[1:]:
                model.Add(x[(block_dates[0], doc)] == x[(bd, doc)])

    years_in_range = sorted(list(set(b["year"] for b in major_blocks)))
    for y in years_in_range:
        y_blocks = [b for b in major_blocks if b["year"] == y]
        if y_blocks:
            for doc in DOCTORS:
                doc_major_vars = [x[(b["dates"][0], doc)] for b in y_blocks]
                if len(y_blocks) >= len(DOCTORS):
                    model.Add(sum(doc_major_vars) == 1)
                else:
                    model.Add(sum(doc_major_vars) <= 1)

    # 6. ΣΥΝΕΧΗΣ ΚΥΚΛΙΚΗ ΡΟΤΑ (Προχωράει μέρα-μέρα κυκλικά σε όλο το εύρος)
    rota_penalties = []
    for i, d in enumerate(dates):
        expected_doc = rota_sequence[i % len(rota_sequence)]
        # Δίνουμε μεγάλη προτεραιότητα στη ρότα μέσω soft constraint ώστε να κυλάει ομαλά
        match_var = model.NewBoolVar(f"match_{i}")
        model.Add(x[(d, expected_doc)] == 1).OnlyEnforceIf(match_var)
        model.Add(x[(d, expected_doc)] == 0).OnlyEnforceIf(match_var.Not())
        
        # Αν είναι αργία, επιτρέπουμε να σπάει πιο εύκολα η ρότα για να μοιραστούν οι αργίες δίκαια
        weight = 5 if d in holiday_dates else 1
        pen = model.NewIntVar(0, weight, f"pen_{i}")
        model.Add(pen == 0).OnlyEnforceIf(match_var)
        model.Add(pen == weight).OnlyEnforceIf(match_var.Not())
        rota_penalties.append(pen)

    # Ελαχιστοποίηση αποκλίσεων από τη ρότα και τα Σαββατοκύριακα
    total_cost = sum(rota_penalties)
    if overtime_penalties:
        total_cost += sum(overtime_penalties) * 10  # μεγαλύτερη βαρύτητα στην ισότητα των ΣΚ/Αργιών
        
    model.Minimize(total_cost)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model)

    schedule = {}
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        for d in dates:
            for doc in DOCTORS:
                if solver.Value(x[(d, doc)]) == 1:
                    schedule[d] = doc
    else:
        st.warning("⚠️ Ο solver δεν βρήκε βέλτιστη λύση, εφαρμόζεται εναλλακτική κατανομή...")
        for i, d in enumerate(dates):
            doc = DOCTORS[i % len(DOCTORS)]
            schedule[d] = doc

    return schedule, holiday_names

# ----------------------------
# BALANCE & REPORTING
# ----------------------------
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

def compute_balance(schedule, start_date, end_date, holiday_names):
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in DOCTORS}
    
    for date, doc in schedule.items():
        if doc not in counts:
            continue
        wd = date.weekday()
        counts[doc][WEEKDAY_LABELS[wd]] += 1
            
    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]
    
    major_df = compute_major_holidays_summary(schedule, start_date, end_date)
    major_dict = dict(zip(major_df["Ακτινολόγος"], major_df["Σύνολο Πακέτων"]))
    
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols_dict = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    regular_df = compute_regular_holidays_summary(schedule, regular_hols_dict)
    regular_dict = dict(zip(regular_df["Ακτινολόγος"], regular_df["Σύνολο"]))
    
    df["Αργίες"] = df["Doctor"].apply(lambda doc: major_dict.get(doc, 0) + regular_dict.get(doc, 0))
    df["Total"] = df["Weekdays"] + df["Fri"] + df["Sat"] + df["Sun"]
    return df[["Doctor", "Weekdays", "Fri", "Sat", "Sun", "Αργίες", "Total"]]

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
st.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων (Κυλιόμενη Ρότα & Κανόνες)")
st.markdown("<span style='font-size:14px; color:gray;'>© Γιώργος Μενοίκου, PhD</span>", unsafe_allow_html=True)

if "manual_assignments" not in st.session_state:
    st.session_state.manual_assignments = {}
if "schedule" not in st.session_state:
    st.session_state.schedule = None
if "holiday_names" not in st.session_state:
    st.session_state.holiday_names = {}
if "balance" not in st.session_state:
    st.session_state.balance = None
if "rota_sequence" not in st.session_state:
    st.session_state.rota_sequence = ["Χριστίνα", "Αθηνά", "Μαρία", "Έλια", "Αλέξανδρος", "Εύα", "Έλενα"]
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
            st.session_state.balance = compute_balance(st.session_state.schedule, st.session_state.start_date, max(st.session_state.schedule.keys()), st.session_state.holiday_names)
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
    st.subheader("🔄 Ορισμός Σειράς Ρότας")
    rota_inputs = []
    cols = st.columns(7)
    for i in range(7):
        with cols[i]:
            doc_choice = st.selectbox(f"Θέση {i+1}", DOCTORS, index=i, key=f"rota_pos_{i}")
            rota_inputs.append(doc_choice)

    if st.button("💾 Αποθήκευση Σειράς Ρότας"):
        st.session_state.rota_sequence = rota_inputs
        st.success("Η σειρά της ρότας αποθηκεύτηκε επιτυχώς!")

    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start date", datetime.date.today())
    with c2:
        default_end = start_date + datetime.timedelta(days=365)
        end_date = st.date_input("End date", default_end)

    if st.button("🗓️ Δημιουργία Προγράμματος"):
        with st.spinner("Υπολογισμός προγράμματος..."):
            sch, hols = generate_full_schedule(
                start_date, end_date, st.session_state.rota_sequence,
                manual_assignments=st.session_state.manual_assignments
            )
            st.session_state.schedule = sch
            st.session_state.holiday_names = hols
            st.session_state.start_date = start_date
            st.session_state.balance = compute_balance(sch, start_date, end_date, hols)
            st.rerun()

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule, st.session_state.holiday_names)
