import datetime
import calendar
from collections import defaultdict
import pandas as pd
import streamlit as str_lit
from fpdf import FPDF

# ----------------------------
# CONSTANTS & DEFAULTS
# ----------------------------
DEFAULT_DOCTORS = ["Γιατρός 1", "Γιατρός 2", "Γιατρός 3", "Γιατρός 4", "Γιατρός 5", "Γιατρός 6", "Γιατρός 7"]

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
GREEK_WEEKDAY_LABELS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]

GREEK_MONTHS = {
    1: "Ιανουάριος", 2: "Φεβρουάριος", 3: "Μάρτιος", 4: "Απρίλιος",
    5: "Μάιος", 6: "Ιούνιος", 7: "Ιούλιος", 8: "Αύγουστος",
    9: "Σεπτέμβριος", 10: "Ὀκτώβριος", 11: "Νοέμβριος", 12: "Δεκέμβριος"
}

# ----------------------------
# PLACEHOLDER HELPER FUNCTIONS (Απαιτούνται για τη λειτουργία)
# ----------------------------
def load_state_from_file():
    return None

def save_state_to_file(*args, **kwargs):
    pass

def get_holidays_in_range(start_date, end_date):
    return {}

def get_major_holiday_blocks_in_range(start_date, end_date, num_doctors=7):
    return []

def get_doctor_color(doc, doctors_list):
    return (220, 230, 242)

def generate_full_schedule(start_date, end_date, doctors_list, initial_week, manual_assignments):
    return {}, {}, []

def generate_full_schedule_with_balance(start_date, end_date, doctors_list, initial_week, manual_assignments, balance_dict):
    return {}, {}, []


# ----------------------------
# CHRONOLOGICAL SUMMARY FUNCTIONS
# ----------------------------
def compute_major_holidays_by_doctor(schedule, start_date, end_date, doctors_list):
    doctor_rows = {doc: [] for doc in doctors_list}
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date, len(doctors_list))
    
    for block in major_blocks:
        package_name = block["base_name"]
        for d in block["dates"]:
            if start_date <= d <= end_date:
                doc = schedule.get(d)
                doc_str = doc if doc else "-"
                if doc in doctor_rows:
                    weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
                    doctor_rows[doc].append({
                        "date_obj": d,
                        "Ακτινολόγος": doc_str,
                        "Ημερομηνία & Ημέρα": f"{d.strftime('%d/%m/%Y')} ({weekday_str})",
                        "Μεγάλη Εορτή / Πακέτο": package_name
                    })
                
    all_data = []
    for doc in doctors_list:
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
        doc = schedule.get(d)
        doc_str = doc if doc else "-"
        weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
        data.append({
            "date_obj": d,
            "Ημερομηνία": d.strftime('%d/%m/%Y'),
            "Ημέρα": weekday_str,
            "Μικρή Αργία": regular_holidays[d],
            "Ακτινολόγος": doc_str,
        })
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("date_obj").drop(columns=["date_obj"]).reset_index(drop=True)
    return df


def compute_balance(schedule, start_date, end_date, holiday_names, doctors_list):
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in doctors_list}
    for date, doc in schedule.items():
        if doc in counts and doc is not None:
            counts[doc][WEEKDAY_LABELS[date.weekday()]] += 1

    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]

    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date, len(doctors_list))
    
    major_counts = defaultdict(int)
    for block in major_blocks:
        for d in block["dates"]:
            doc = schedule.get(d)
            if doc in doctors_list and doc is not None:
                major_counts[doc] += 1

    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    regular_counts = defaultdict(int)
    for d in regular_hols:
        doc = schedule.get(d)
        if doc in doctors_list and doc is not None:
            regular_counts[doc] += 1

    df["Αργίες"] = df["Doctor"].apply(lambda doc: major_counts.get(doc, 0) + regular_counts.get(doc, 0))
    df["Total"] = df["Weekdays"] + df["Fri"] + df["Sat"] + df["Sun"] + df["Αργίες"]
    return df[["Doctor", "Weekdays", "Fri", "Sat", "Sun", "Αργίες", "Total"]]


# ----------------------------
# PDF EXPORT HELPERS
# ----------------------------
def create_balance_pdf(df, start_date, end_date):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Ισοζύγιο Εφημεριών", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
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
    return bytes(pdf.output())


def create_major_holidays_pdf_by_doctor(schedule, start_date, end_date, doctors_list):
    doctor_rows = {doc: [] for doc in doctors_list}
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date, len(doctors_list))
    
    for block in major_blocks:
        package_name = block["base_name"]
        for d in block["dates"]:
            if start_date <= d <= end_date:
                doc = schedule.get(d)
                doc_str = doc if doc else "-"
                if doc in doctor_rows:
                    weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
                    doctor_rows[doc].append({
                        "date_obj": d,
                        "Ημερομηνία & Ημέρα": f"{d.strftime('%d/%m/%Y')} ({weekday_str})",
                        "Μεγάλη Εορτή / Πακέτο": package_name
                    })

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    col_widths = [45, 125]
    headers = ["Ημερομηνία & Ημέρα", "Μεγάλη Εορτή / Πακέτο"]

    for doc in doctors_list:
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 14)
        pdf.cell(0, 10, f"Κατάσταση Μεγάλων Εορτών - {doc}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVu", "", 10)
        pdf.cell(0, 6, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
                 align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

        pdf.set_font("DejaVu", "B", 10)
        for h, w in zip(headers, col_widths):
            pdf.cell(w, 8, h, border=1, align="C")
        pdf.ln()

        pdf.set_font("DejaVu", "", 9)
        items = sorted(doctor_rows[doc], key=lambda x: x["date_obj"])
        if items:
            for item in items:
                pdf.cell(col_widths[0], 8, item["Ημερομηνία & Ημέρα"], border=1, align="C")
                pdf.cell(col_widths[1], 8, item["Μεγάλη Εορτή / Πακέτο"], border=1, align="L")
                pdf.ln()
        else:
            pdf.cell(col_widths[0] + col_widths[1], 8, "Καμία μεγάλη εορτή", border=1, align="C")
            pdf.ln()

    return bytes(pdf.output())


def create_yearly_major_holidays_pdf(schedule, year, start_date, end_date):
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    valid_hols = []
    for block in major_blocks:
        for d in block["dates"]:
            if d.year == year and start_date <= d <= end_date:
                valid_hols.append((d, block["base_name"]))
    
    sorted_hols = sorted(valid_hols, key=lambda x: x[0])

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, f"Πρόγραμμα Μεγάλων Εορτών – Έτος {year}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, f"Συγκεντρωτική Κατάσταση Έτους", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    col_widths = [30, 20, 75, 45]
    headers = ["Ημερομηνία", "Ημέρα", "Μεγάλη Εορτή", "Ακτινολόγος"]

    pdf.set_font("DejaVu", "B", 10)
    for h, w in zip(headers, col_widths):
        pdf.cell(w, 8, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("DejaVu", "", 9)
    found_any = False
    for d, name in sorted_hols:
        doc = schedule.get(d)
        doc_str = doc if doc else "-"
        weekday_str = GREEK_WEEKDAY_LABELS[d.weekday()]
        pdf.cell(col_widths[0], 8, d.strftime('%d/%m/%Y'), border=1, align="C")
        pdf.cell(col_widths[1], 8, weekday_str, border=1, align="C")
        pdf.cell(col_widths[2], 8, name, border=1, align="L")
        pdf.cell(col_widths[3], 8, doc_str, border=1, align="C")
        pdf.ln()
        found_any = True

    if not found_any:
        pdf.cell(sum(col_widths), 8, "Καμία μεγάλη εορτή", border=1, align="C")
        pdf.ln()

    return bytes(pdf.output())


def create_regular_holidays_pdf(schedule, holiday_names, start_date, end_date):
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date, 7)
    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    
    df = compute_regular_holidays_chronological(schedule, regular_hols)
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, "Κατάσταση Μικρών Αργιών", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, f"Περίοδος: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    col_widths = [30, 20, 105, 45]
    headers = ["Ημερομηνία", "Ημέρα", "Μικρή Αργία", "Ακτινολόγος"]
    
    pdf.set_font("DejaVu", "B", 10)
    for h, w in zip(headers, col_widths):
        pdf.cell(w, 8, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("DejaVu", "", 9)
    for _, row in df.iterrows():
        pdf.cell(col_widths[0], 8, str(row["Ημερομηνία"]), border=1, align="C")
        pdf.cell(col_widths[1], 8, str(row["Ημέρα"]), border=1, align="C")
        pdf.cell(col_widths[2], 8, str(row["Μικρή Αργία"]), border=1, align="L")
        pdf.cell(col_widths[3], 8, str(row["Ακτινολόγος"]), border=1, align="C")
        pdf.ln()
        
    return bytes(pdf.output())


def create_calendar_pdf(schedule, start_date, end_date, holiday_names, doctors_list):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")
    
    months_to_print = []
    curr = datetime.date(start_date.year, start_date.month, 1)
    while curr <= end_date:
        months_to_print.append((curr.year, curr.month))
        if curr.month == 12:
            curr = datetime.date(curr.year + 1, 1, 1)
        else:
            curr = datetime.date(curr.year, curr.month + 1, 1)
            
    for year, month in months_to_print:
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 16)
        month_name = GREEK_MONTHS[month]
        pdf.cell(0, 10, f"{month_name} {year}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        
        col_width = 38
        row_height = 24
        
        pdf.set_font("DejaVu", "B", 11)
        for d_label in GREEK_WEEKDAY_LABELS:
            pdf.cell(col_width, 8, d_label, border=1, align="C")
        pdf.ln()
        
        cal = calendar.Calendar(firstweekday=0)
        month_weeks = cal.monthdatescalendar(year, month)
        
        for week in month_weeks:
            for day in week:
                x_pos = pdf.get_x()
                y_pos = pdf.get_y()
                
                is_hol = day in holiday_names
                doc = schedule.get(day) if day in schedule else None
                
                if day.month == month and doc:
                    rgb = get_doctor_color(doc, doctors_list)
                    pdf.set_fill_color(rgb[0], rgb[1], rgb[2])
                else:
                    pdf.set_fill_color(255, 255, 255)
                    
                pdf.rect(x_pos, y_pos, col_width, row_height, style="FD")
                
                if day.month == month:
                    pdf.set_xy(x_pos, y_pos + 1.5)
                    pdf.set_font("DejaVu", "B", 10)
                    pdf.cell(col_width, 5, str(day.day), align="C", new_x="LMARGIN", new_y="NEXT")
                    
                    pdf.set_x(x_pos)
                    pdf.set_font("DejaVu", "", 9)
                    doc_str = doc if doc else ""
                    pdf.cell(col_width, 5, doc_str, align="C", new_x="LMARGIN", new_y="NEXT")
                    
                    if is_hol:
                        pdf.set_x(x_pos)
                        pdf.set_font("DejaVu", "", 7)
                        hol_name = holiday_names[day]
                        h_short = hol_name[:18] + "..." if len(hol_name) > 18 else hol_name
                        pdf.cell(col_width, 4, h_short, align="C", new_x="LMARGIN", new_y="NEXT")
                
                pdf.set_xy(x_pos + col_width, y_pos)
            pdf.ln(row_height)
            
    return bytes(pdf.output())


def display_calendar(schedule, holiday_names, doctors_list):
    last_month = None
    empty_tooltips = getattr(str_lit.session_state, "empty_tooltips", {})
    
    for date in sorted(schedule.keys()):
        month_key = (date.year, date.month)
        if month_key != last_month:
            str_lit.markdown(f"## {GREEK_MONTHS[date.month]} {date.year}")
            last_month = month_key
            headers = str_lit.columns(7)
            for i, d in enumerate(WEEKDAY_LABELS):
                headers[i].markdown(f"**{d}**")
            cal = calendar.Calendar(firstweekday=0)
            for week in cal.monthdatescalendar(date.year, date.month):
                cols = str_lit.columns(7)
                for i, day in enumerate(week):
                    if day.month == date.month:
                        doc = schedule.get(day) if day in schedule else None
                        is_holiday = day in holiday_names
                        holiday_tag = (f"<br><span style='font-size:10px'>🎉 {holiday_names[day]}</span>"
                                       if is_holiday else "")
                        
                        if doc:
                            rgb = get_doctor_color(doc, doctors_list)
                            color = '#%02x%02x%02x' % rgb
                            doc_display = doc
                            tooltip_attr = ""
                        else:
                            color = '#f8f9fa'
                            doc_display = "<span style='color:gray; font-style:italic;'>Κενό</span>"
                            t_text = empty_tooltips.get(day, "Ελεύθερη μέρα ή μη υπολογισμένοι περιορισμοί")
                            t_text_safe = t_text.replace('"', '&quot;')
                            tooltip_attr = f"title='{t_text_safe}' style='cursor: help;'"

                        border = "border:2px solid #d9534f;" if is_holiday else "border:1px dashed #ccc;"
                        
                        cols[i].markdown(
                            f"<div {tooltip_attr} style='background-color:{color}; {border} padding:6px; "
                            f"border-radius:4px; text-align:center'>"
                            f"<b>{day.day}</b><br>{doc_display}{holiday_tag}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        cols[i].markdown("")


# ----------------------------
# PARTIAL RECALCULATION & FAIR TRANSITION LOGIC
# ----------------------------
def recalculate_on_doctor_change_fair(cutoff_date, schedule, old_doctors_list, new_doctors_list, initial_week, manual_entries, current_balance):
    new_schedule = {d: doc for d, doc in schedule.items() if d < cutoff_date}
    
    if isinstance(current_balance, pd.DataFrame):
        balance_dict = dict(zip(current_balance["Doctor"], current_balance["Total"])) if not current_balance.empty else {}
    else:
        balance_dict = current_balance.copy() if current_balance else {}
    
    newly_added_docs = [doc for doc in new_doctors_list if doc not in old_doctors_list]
    recently_removed_docs = [doc for doc in old_doctors_list if doc not in new_doctors_list]
    
    if newly_added_docs:
        past_counts = {doc: 0 for doc in old_doctors_list}
        for d, doc in schedule.items():
            if d < cutoff_date and doc in past_counts and doc is not None:
                past_counts[doc] += 1
                
        if old_doctors_list:
            avg_past_shifts = sum(past_counts.values()) / len(old_doctors_list)
        else:
            avg_past_shifts = 0
            
        for new_doc in newly_added_docs:
            if len(newly_added_docs) == 1 and len(recently_removed_docs) == 1:
                removed_doc = recently_removed_docs[0]
                balance_dict[new_doc] = balance_dict.get(removed_doc, avg_past_shifts)
            else:
                balance_dict[new_doc] = round(avg_past_shifts, 2)
            
    balance_dict = {doc: score for doc, score in balance_dict.items() if doc in new_doctors_list}
    
    future_manual = {
        d: doc for d, doc in manual_entries.items() 
        if d >= cutoff_date and doc in new_doctors_list
    }
    
    max_date = max(schedule.keys()) if schedule else cutoff_date + datetime.timedelta(days=365)
    
    sub_schedule, _, warnings = generate_full_schedule_with_balance(
        cutoff_date, max_date, new_doctors_list, initial_week, future_manual, balance_dict
    )
    
    new_schedule.update(sub_schedule)
    return new_schedule, warnings, balance_dict


# ----------------------------
# STREAMLIT UI
# ----------------------------
str_lit.set_page_config(page_title="📅 Πρόγραμμα Εφημεριών", layout="wide")
str_lit.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων")
str_lit.markdown("<span style='font-size:14px; color:gray;'>© Γιώργος Μενοίκου, PhD</span>",
            unsafe_allow_html=True)

saved_state = load_state_from_file()

defaults = {
    "manual_assignments": saved_state["manual_assignments"] if saved_state else {},
    "schedule": saved_state["schedule"] if saved_state else None,
    "holiday_names": saved_state["holiday_names"] if saved_state else {},
    "empty_tooltips": saved_state["empty_tooltips"] if saved_state else {},
    "doctors": saved_state["doctors"] if saved_state else DEFAULT_DOCTORS,
    "initial_week": saved_state["initial_week"] if saved_state else DEFAULT_DOCTORS[:7],
    "warnings": [],
    "start_date": datetime.date.today(),
    "balance": None,
}

for key, default_val in defaults.items():
    if key not in str_lit.session_state:
        str_lit.session_state[key] = default_val

if str_lit.session_state.schedule and (str_lit.session_state.balance is None or (isinstance(str_lit.session_state.balance, pd.DataFrame) and str_lit.session_state.balance.empty)):
    start_d = min(str_lit.session_state.schedule.keys())
    end_d = max(str_lit.session_state.schedule.keys())
    str_lit.session_state.balance = compute_balance(
        str_lit.session_state.schedule, start_d, end_d, 
        str_lit.session_state.holiday_names, str_lit.session_state.doctors
    )

str_lit.sidebar.markdown("### 🔐 Έλεγχος Πρόσβασης")
user_role = str_lit.sidebar.selectbox("Επιλέξτε Ρόλο Χρήστη", ["Γιατρός / Αναγνώστης (View-Only)", "Διαχειριστής (Moderator)"])

is_moderator = False

if user_role == "Διαχειριστής (Moderator)":
    admin_password = str_lit.sidebar.text_input("Κωδικός Διαχειριστή", type="password")
    
    if admin_password == "borland1!":
        is_moderator = True
        str_lit.sidebar.success("Επιτυχής σύνδεση ως Διαχειριστής!")
    elif admin_password != "":
        str_lit.sidebar.error("Λανθασμένος κωδικός!")
        is_moderator = False
else:
    is_moderator = False

left_col, right_col = str_lit.columns([0.35, 0.65])

if str_lit.session_state.schedule:
    default_start = min(str_lit.session_state.schedule.keys())
    default_end = max(str_lit.session_state.schedule.keys())
else:
    default_start = datetime.date.today()
    default_end = datetime.date.today() + datetime.timedelta(days=365)

with left_col:
    if is_moderator:
        str_lit.subheader("📊 Παραμετροποίηση Εύρους & Ιατρών")
        start_date = str_lit.date_input("Ημερομηνία Έναρξης", value=default_start)
        end_date = str_lit.date_input("Ημερομηνία Λήξης", value=default_end)

        str_lit.markdown("### 👥 Διαχείριση Ομάδας Ιατρών")
        
        new_doc_input = str_lit.text_input("Προσθήκη νέου γιατρού (πληκτρολόγησε όνομα):")
        if str_lit.button("➕ Προσθήκη στη λίστα"):
            if new_doc_input and new_doc_input not in str_lit.session_state.doctors:
                str_lit.session_state.doctors.append(new_doc_input)
                str_lit.success(f"Προστέθηκε ο/η {new_doc_input}")
                str_lit.rerun()

        current_doctors = str_lit.multiselect(
            "Ενεργοί Ιατροί (Ξε-τσεκάρισε για αφαίρεση)",
            options=str_lit.session_state.doctors,
            default=str_lit.session_state.doctors
        )
        if current_doctors:
            old_doctors_snapshot = str_lit.session_state.doctors.copy()
            str_lit.session_state.doctors = current_doctors
        else:
            str_lit.warning("Πρέπει να επιλέξετε τουλάχιστον έναν ιατρό.")
            str_lit.stop()

        active_doctors = str_lit.session_state.doctors

        str_lit.markdown("### 📋 Αρχική Σειρά Εβδομάδας (Δευτέρα - Κυριακή)")
        initial_week_list = []
        cols_init = str_lit.columns(7)
        for i, day_label in enumerate(GREEK_WEEKDAY_LABELS):
            with cols_init[i]:
                default_doc = str_lit.session_state.initial_week[i] if i < len(str_lit.session_state.initial_week) else active_doctors[0]
                if default_doc not in active_doctors:
                    default_doc = active_doctors[0]
                doc_sel = str_lit.selectbox(day_label, active_doctors, index=active_doctors.index(default_doc), key=f"init_day_{i}")
                initial_week_list.append(doc_sel)
        str_lit.session_state.initial_week = initial_week_list

        str_lit.markdown("### ✏️ Χειροκίνητες Αναθέσεις")
        with str_lit.form(key="manual_form"):
            str_lit.markdown("Επιλέξτε ημερομηνία και γιατρό για προσθήκη στη λίστα αλλαγών:")
            f_date = str_lit.date_input("Ημερομηνία Ανάθεσης", value=default_start)
            f_doc = str_lit.selectbox("Ιατρός", active_doctors)
            
            f_col1, f_col2 = str_lit.columns(2)
            submit_add = f_col1.form_submit_button("➕ Προσθήκη / Κλείδωμα")
            submit_del = f_col2.form_submit_button("🗑 Αφαίρεση Ημερομηνίας")

            if submit_add:
                str_lit.session_state.manual_assignments[f_date] = f_doc
                str_lit.success(f"Προστέθηκε: {f_date.strftime('%d/%m/%Y')} -> {f_doc}")
            elif submit_del:
                if f_date in str_lit.session_state.manual_assignments:
                    del str_lit.session_state.manual_assignments[f_date]
                    str_lit.info(f"Αφαιρέθηκε η ημερομηνία {f_date.strftime('%d/%m/%Y')}")

        if str_lit.session_state.manual_assignments:
            str_lit.markdown("**📋 Εκκρεμείς Χειροκίνητες Αλλαγές:**")
            for d, doc in sorted(str_lit.session_state.manual_assignments.items()):
                str_lit.write(f"- {d.strftime('%d/%m/%Y')}: **{doc}**")
            
            if str_lit.button("🗑️ Εκκαθάριση Όλων των Αλλαγών"):
                str_lit.session_state.manual_assignments = {}
                str_lit.rerun()

        str_lit.markdown("---")
        
        calc_col1, calc_col2 = str_lit.columns(2)
        
        with calc_col1:
            if str_lit.button("🔄 Νέος Υπολογισμός (Full)", type="primary"):
                str_lit.session_state.start_date = start_date
                holiday_names = get_holidays_in_range(start_date, end_date)
                str_lit.session_state.holiday_names = holiday_names
                
                schedule, holiday_names, warnings = generate_full_schedule(
                    start_date, end_date, active_doctors, str_lit.session_state.initial_week, str_lit.session_state.manual_assignments
                )
                str_lit.session_state.schedule = schedule
                str_lit.session_state.warnings = warnings
                str_lit.session_state.balance = compute_balance(schedule, start_date, end_date, holiday_names, active_doctors)
                
                save_state_to_file(
                    schedule, holiday_names, str_lit.session_state.balance, 
                    str_lit.session_state.manual_assignments, active_doctors, 
                    str_lit.session_state.initial_week, str_lit.session_state.empty_tooltips
                )
                str_lit.success("Το πρόγραμμα υπολογίστηκε εξ αρχής επιτυχώς!")

        with calc_col2:
            change_date = str_lit.date_input("Ημερομηνία Αλλαγής Προσωπικού:", value=datetime.date.today())
            if str_lit.button("⚡ Εφαρμογή Αλλαγής (Partial)"):
                if str_lit.session_state.schedule is not None:
                    updated_schedule, warnings, new_balance_dict = recalculate_on_doctor_change_fair(
                        cutoff_date=change_date,
                        schedule=str_lit.session_state.schedule,
                        old_doctors_list=old_doctors_snapshot,
                        new_doctors_list=active_doctors,
                        initial_week=str_lit.session_state.initial_week,
                        manual_entries=str_lit.session_state.manual_assignments,
                        current_balance=str_lit.session_state.balance
                    )
                    str_lit.session_state.schedule = updated_schedule
                    str_lit.session_state.warnings = warnings
                    
                    balance_df = pd.DataFrame(list(new_balance_dict.items()), columns=["Doctor", "Total"])
                    str_lit.session_state.balance = balance_df
                    
                    save_state_to_file(
                        updated_schedule, str_lit.session_state.holiday_names, 
                        balance_df, str_lit.session_state.manual_assignments, 
                        active_doctors, str_lit.session_state.initial_week, 
                        str_lit.session_state.empty_tooltips
                    )
                    str_lit.success("Η αλλαγή προσωπικού εφαρμόστηκε επιτυχώς!")
                else:
                    str_lit.warning("Δεν υπάρχει ενεργό πρόγραμμα.")

        active_doctors = str_lit.session_state.doctors
    else:
        str_lit.subheader("👁️ Λειτουργία Προβολής (Γιατρός)")
        active_doctors = str_lit.session_state.doctors
        start_date = default_start
        end_date = default_end
        
        if str_lit.session_state.schedule is None:
            str_lit.warning("Δεν έχει αποθηκευτεί ακόμα πρόγραμμα.")

    if str_lit.session_state.warnings:
        with str_lit.expander("⚠ Προειδοποιήσεις (Κενές Ημέρες)", expanded=False):
            for w in str_lit.session_state.warnings:
                str_lit.write(f"- {w}")

    if str_lit.session_state.balance is not None and not (isinstance(str_lit.session_state.balance, pd.DataFrame) and str_lit.session_state.balance.empty):
        end_d = max(str_lit.session_state.schedule.keys()) if str_lit.session_state.schedule else end_date
        
        str_lit.markdown("---")
        str_lit.markdown("### 📥 Επιλογές Εξαγωγής PDF")
        
        balance_to_pass = str_lit.session_state.balance
        if isinstance(balance_to_pass, dict):
            balance_to_pass = pd.DataFrame(list(balance_to_pass.items()), columns=["Doctor", "Total"])

        pdf_balance_bytes = create_balance_pdf(balance_to_pass, str_lit.session_state.start_date, end_d)
        str_lit.download_button("📄 Λήψη Ισοζυγίου σε PDF", pdf_balance_bytes, file_name="doctor_balance.pdf", mime="application/pdf")

        if str_lit.session_state.schedule:
            pdf_major_bytes = create_major_holidays_pdf_by_doctor(
                str_lit.session_state.schedule, 
                str_lit.session_state.start_date, 
                end_d, 
                active_doctors
            )
            str_lit.download_button("📄 Λήψη Μεγάλων Εορτών ανά Ιατρό σε PDF", pdf_major_bytes, file_name="major_holidays_by_doctor.pdf", mime="application/pdf")

            selected_year = str_lit.selectbox("Επιλογή Έτους για Μεγάλες Εορτές", range(start_date.year, end_date.year + 1))
            if str_lit.button("📥 Λήψη Μεγάλων Εορτών Έτους σε PDF"):
                pdf_yearly_bytes = create_yearly_major_holidays_pdf(str_lit.session_state.schedule, selected_year, str_lit.session_state.start_date, end_d)
                str_lit.download_button(
                    label=f"💾 Αποθήκευση PDF Έτους {selected_year}",
                    data=pdf_yearly_bytes,
                    file_name=f"major_holidays_{selected_year}.pdf",
                    mime="application/pdf"
                )

            major_blocks = get_major_holiday_blocks_in_range(str_lit.session_state.start_date, end_d, len(active_doctors))
            all_major_dates = {d for block in major_blocks for d in block["dates"]}
            regular_hols = {d: n for d, n in str_lit.session_state.holiday_names.items() if d not in all_major_dates}
            
            pdf_reg_bytes = create_regular_holidays_pdf(str_lit.session_state.schedule, str_lit.session_state.holiday_names, str_lit.session_state.start_date, end_d)
            str_lit.download_button("📄 Λήψη Μικρών Αργιών σε PDF", pdf_reg_bytes, file_name="regular_holidays.pdf", mime="application/pdf")

            pdf_calendar_bytes = create_calendar_pdf(
                str_lit.session_state.schedule,
                str_lit.session_state.start_date,
                end_d,
                str_lit.session_state.holiday_names,
                active_doctors
            )
            str_lit.download_button(
                "📥 Λήψη Πλήρους Ημερολογίου σε Landscape PDF (Ανά Μήνα)",
                pdf_calendar_bytes,
                file_name="calendar_landscape.pdf",
                mime="application/pdf"
            )

        str_lit.markdown("---")
        str_lit.markdown("### 📊 Πίνακας Ισοζυγίου")
        str_lit.dataframe(balance_to_pass, use_container_width=True, height=260)

        str_lit.markdown("---")
        str_lit.markdown("### 🎄🐣 Μεγάλες Εορτές ανά Ιατρό")
        major_doctor_df = compute_major_holidays_by_doctor(
            str_lit.session_state.schedule, str_lit.session_state.start_date, end_d, active_doctors)
        str_lit.dataframe(major_doctor_df, use_container_width=True, height=220)

        str_lit.markdown("---")
        str_lit.markdown("### 🏛 Μικρές Αργίες Χρονολογικά")
        reg_df = compute_regular_holidays_chronological(str_lit.session_state.schedule, regular_hols)
        str_lit.dataframe(reg_df, use_container_width=True, height=200)

with right_col:
    str_lit.subheader("🗓 Ημερολόγιο Εφημεριών")
    if str_lit.session_state.schedule:
        display_calendar(str_lit.session_state.schedule, str_lit.session_state.holiday_names, active_doctors)
    else:
        str_lit.info("Δεν υπάρχει διαθέσιμο πρόγραμμα.")
