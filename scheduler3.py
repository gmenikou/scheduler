import streamlit as st
import datetime
import calendar
import pandas as pd
from fpdf import FPDF

# ----------------------------
# CONSTANTS & SETUP
# ----------------------------
DOCTORS = ["Χριστίνα", "Εύα", "Έλια", "Αθηνά", "Έλενα", "Αλέξανδρος", "Μαρία"]

DOCTOR_COLORS = {
    "Έλενα": (255, 200, 200),
    "Εύα": (200, 255, 200),
    "Μαρία": (200, 200, 255),
    "Αθηνά": (255, 255, 200),
    "Αλέξανδρος": (255, 200, 255),
    "Έλια": (200, 200, 255),
    "Χριστίνα": (220, 220, 220)
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

# ----------------------------
# WEEKLY -2 DAYS SHIFT SCHEDULE
# ----------------------------
def generate_weekly_shifting_schedule(initial_doctors, start_date, end_date, manual_assignments=None):
    """
    Δημιουργεί πρόγραμμα όπου κάθε εβδομάδα η μέρα μετατοπίζεται κατά -2 ημέρες
    (δηλαδή -2 μέρες σε σχέση με την προηγούμενη εβδομάδα).
    """
    schedule = {}
    manual_assignments = manual_assignments or {}
    num_docs = len(initial_doctors)
    
    current_date = start_date
    while current_date <= end_date:
        if current_date in manual_assignments:
            schedule[current_date] = manual_assignments[current_date]
        else:
            days_from_start = (current_date - start_date).days
            week_num = days_from_start // 7
            weekday = current_date.weekday() # 0: Δευτέρα έως 6: Κυριακή
            
            # Μετατόπιση κατά -2 ημέρες κάθε εβδομάδα (ισοδύναμο με +2 στο modulo 7)
            doc_idx = (weekday + 2 * week_num) % num_docs
            schedule[current_date] = initial_doctors[doc_idx]
            
        current_date += datetime.timedelta(days=1)
        
    return schedule

# ----------------------------
# BALANCE & HOLIDAYS REPORTING
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

def compute_doctor_holidays_breakdown(schedule, holiday_names):
    doc_holidays = {doc: [] for doc in DOCTORS}
    for d in sorted(holiday_names.keys()):
        doc = schedule.get(d)
        if doc in doc_holidays:
            doc_holidays[doc].append(f"{d.strftime('%d/%m/%Y')} ({holiday_names[d]})")
            
    data = []
    for doc in DOCTORS:
        h_list = doc_holidays[doc]
        data.append({
            "Ακτινολόγος": doc,
            "Πλήθος Αργιών": len(h_list),
            "Αργίες που του/της Αναλογούν": ", ".join(h_list) if h_list else "Καμία"
        })
    return pd.DataFrame(data)

# ----------------------------
# DISPLAY & PDF HELPERS
# ----------------------------
def display_calendar(schedule):
    manual_assignments = st.session_state.get("manual_assignments", {})
    holiday_names = st.session_state.get("holiday_names", {})
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

def create_calendar_pdf(schedule, filename="calendar.pdf"):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'DejaVuSans.ttf', uni=True)
    pdf.set_font("DejaVu", "", 12)

    manual_assignments = st.session_state.get("manual_assignments", {})
    holiday_names = st.session_state.get("holiday_names", {})
    last_month = None
    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            pdf.add_page()
            pdf.set_font("DejaVu", "B", 16)
            pdf.cell(0, 10, month_name, ln=True, align="C")
            pdf.ln(4)
            pdf.set_font("DejaVu", "B", 12)
            col_width = 40
            for wd in WEEKDAY_LABELS:
                pdf.cell(col_width, 8, wd, border=1, align="C")
            pdf.ln()
            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(date.year, date.month)
            pdf.set_font("DejaVu", "", 12)
            cell_height = 20
            for week in weeks:
                x_start = pdf.get_x()
                y_start = pdf.get_y()
                for i, day in enumerate(week):
                    pdf.set_xy(x_start + i * col_width, y_start)
                    if day.month == date.month:
                        doc = schedule.get(day, "")
                        is_holiday = day in holiday_names
                        marker = "*" if day in manual_assignments else ""
                        text = f"{day.day}{marker}\n{doc}"
                        if is_holiday:
                            text += "\n(Αργία)"
                            pdf.set_fill_color(255, 225, 225)
                        else:
                            pdf.set_fill_color(*DOCTOR_COLORS.get(doc, (220, 220, 220)))
                        pdf.multi_cell(col_width, 5, text, border=1, align="C", fill=True)
                    else:
                        pdf.set_fill_color(240, 240, 240)
                        pdf.cell(col_width, cell_height, "", border=1, fill=True)
                pdf.ln(cell_height)
            last_month = month_name
    pdf.output(filename)
    return filename

# ----------------------------
# STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="📅 Πρόγραμμα εφημεριών © Γιώργος Μενοίκου,PhD ", layout="wide")
st.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων")
st.markdown(
    "<span style='font-size:14px; color:gray;'>© Γιώργος Μενοίκου, PhD</span>",
    unsafe_allow_html=True
)

if "manual_assignments" not in st.session_state:
    st.session_state.manual_assignments = {}
if "holiday_names" not in st.session_state:
    st.session_state.holiday_names = {}

for key in ["initial_doctors", "start_date", "end_date", "schedule", "balance"]:
    if key not in st.session_state:
        st.session_state[key] = None

left_col, right_col = st.columns([0.40, 0.60])

# ----------------------------
# LEFT: Balance & Holiday Breakdown
# ----------------------------
with left_col:
    st.subheader("📊 Κατάσταση Εφημεριών Εύρους")

    if st.session_state.start_date and st.session_state.end_date:
        manual_date = st.date_input(
            "Επιλέξετε ημερομηνία για αλλαγή",
            min_value=st.session_state.start_date,
            max_value=st.session_state.end_date
        )
        manual_doctor = st.selectbox("Επιλογή Ακτινολόγου", DOCTORS)
        if st.button("✅ Επικύρωση"):
            st.session_state.manual_assignments[manual_date] = manual_doctor
            st.session_state.schedule[manual_date] = manual_doctor

            st.session_state.balance = compute_balance(
                st.session_state.schedule,
                holiday_dates=set(st.session_state.holiday_names.keys())
            )

            holiday_note = ""
            if manual_date in st.session_state.holiday_names:
                holiday_note = f" (Αργία: {st.session_state.holiday_names[manual_date]})"
            st.success(f"Ο/Η {manual_doctor} ανατέθηκε στις {manual_date.strftime('%d/%m/%Y')}{holiday_note}")
            
            st.rerun()

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        st.dataframe(st.session_state.balance, use_container_width=True, height=260)

        # ----------------------------
        # ΑΝΑΛΥΣΗ ΑΡΓΙΩΝ ΑΝΑ ΓΙΑΤΡΟ
        # ----------------------------
        if st.session_state.holiday_names:
            st.subheader("🎉 Αναλογία Αργιών ανά Γιατρό")
            hols_df = compute_doctor_holidays_breakdown(
                st.session_state.schedule, 
                st.session_state.holiday_names
            )
            st.dataframe(hols_df, use_container_width=True)

        if st.button("📄 Εξαγωγή κατάστασης σε PDF"):
            pdf_file = create_balance_pdf(
                st.session_state.balance,
                st.session_state.start_date,
                st.session_state.end_date
            )
            with open(pdf_file, "rb") as f:
                st.download_button("⬇️ Κατέβασε κατάσταση σε PDF", f, file_name=pdf_file)
        if st.button("🖨️ Εξαγωγή ημερολογίου σε PDF"):
            pdf_file = create_calendar_pdf(st.session_state.schedule)
            with open(pdf_file, "rb") as f:
                st.download_button("⬇️ Κατέβασε ημερολόγιο σε PDF", f, file_name=pdf_file)

# ----------------------------
# RIGHT: Rota Generation
# ----------------------------
with right_col:
    st.subheader("Σειρά Εναλλαγής Γιατρών")
    st.write("Ορίστε τη σειρά των 7 γιατρών:")
    
    selected_doctors = []
    cols = st.columns(7)
    for i in range(7):
        with cols[i]:
            doc = st.selectbox(
                f"Γιατρός {i+1}",
                DOCTORS,
                index=i,
                key=f"doc_order_{i}"
            )
            selected_doctors.append(doc)

    start_date = st.date_input("Ημερομηνία Έναρξης", datetime.date(2026, 2, 2))
    end_date = st.date_input("Ημερομηνία Λήξης", datetime.date(2026, 3, 31))

    if st.button("🗓️ Δημιουργία Προγράμματος"):
        st.session_state.initial_doctors = selected_doctors
        holiday_names = get_holidays_in_range(start_date, end_date)
        st.session_state.holiday_names = holiday_names

        st.session_state.schedule = generate_weekly_shifting_schedule(
            selected_doctors,
            start_date,
            end_date,
            manual_assignments=st.session_state.manual_assignments
        )
        
        st.session_state.start_date = start_date
        st.session_state.end_date = end_date
        
        st.session_state.balance = compute_balance(
            st.session_state.schedule,
            holiday_dates=set(holiday_names.keys())
        )

        st.rerun()

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule)
