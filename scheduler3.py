from collections import deque
import calendar
import datetime
from fpdf import FPDF
import pandas as pd
import streamlit as st

# ----------------------------
# CONSTANTS
# ----------------------------
DOCTORS = ["Χριστίνα", "Αθηνά", "Μαρία", "Έλια", "Αλέξανδρος", "Εύα", "Έλενα"]

DOCTOR_COLORS = {
    "Έλενα": (255, 200, 200),
    "Εύα": (200, 255, 200),
    "Μαρία": (200, 200, 255),
    "Αθηνά": (255, 255, 200),
    "Αλέξανδρος": (255, 200, 255),
    "Έλια": (200, 255, 255),
    "Χριστίνα": (220, 220, 220),
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
    (12, 25, "Χριστούγεννα"),
    (12, 26, "Δεύτερη μέρα Χριστουγέννων"),
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
  for year in range(start_date.year - 1, end_date.year + 2):
    c_dates = [
        (datetime.date(year, 12, 24), "Παραμονή Χριστουγέννων"),
        (datetime.date(year, 12, 25), "Χριστούγεννα"),
        (datetime.date(year, 12, 26), "Δεύτερη μέρα Χριστουγέννων"),
        (datetime.date(year, 12, 31), "Παραμονή Πρωτοχρονιάς"),
        (datetime.date(year + 1, 1, 1), "Πρωτοχρονιά"),
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


def compute_major_holidays_summary(schedule, major_holidays):
  summary = {doc: {"Count": 0, "Details": []} for doc in DOCTORS}
  for d in sorted(major_holidays.keys()):
    doc = schedule.get(d, "-")
    if doc in summary:
      summary[doc]["Count"] += 1
      summary[doc]["Details"].append(
          f"{d.strftime('%d/%m/%Y')} ({major_holidays[d]})"
      )

  data = []
  for doc in DOCTORS:
    data.append({
        "Ακτινολόγος": doc,
        "Σύνολο": summary[doc]["Count"],
        "Ημερομηνίες & Εορτές": (
            ", ".join(summary[doc]["Details"])
            if summary[doc]["Details"]
            else "Καμία"
        ),
    })
  return pd.DataFrame(data)


def compute_regular_holidays_summary(schedule, regular_holidays):
  summary = {doc: {"Count": 0, "Details": []} for doc in DOCTORS}
  for d in sorted(regular_holidays.keys()):
    doc = schedule.get(d, "-")
    if doc in summary:
      summary[doc]["Count"] += 1
      summary[doc]["Details"].append(
          f"{d.strftime('%d/%m/%Y')} ({regular_holidays[d]})"
      )

  data = []
  for doc in DOCTORS:
    data.append({
        "Ακτινολόγος": doc,
        "Σύνολο": summary[doc]["Count"],
        "Ημερομηνίες & Εορτές": (
            ", ".join(summary[doc]["Details"])
            if summary[doc]["Details"]
            else "Καμία"
        ),
    })
  return pd.DataFrame(data)


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
      1
      for d, doc in schedule.items()
      if doc == doctor and d != exclude_date and _week_monday(d) == wk
  )


def assign_holiday_duties(
    holiday_dates_sorted,
    base_schedule,
    manual_assignments=None,
    max_per_week=2,
    min_gap_days=3,
    custom_queue=None,
):
  manual_assignments = manual_assignments or {}
  working = dict(base_schedule)
  working.update(manual_assignments)

  queue = custom_queue if custom_queue is not None else deque(DOCTORS)
  assignments = {}
  conflicts = set()
  max_gap = min_gap_days - 1

  for d in holiday_dates_sorted:
    if d in manual_assignments:
      continue

    skipped = []
    chosen = None
    for _ in range(len(queue)):
      candidate = queue.popleft()
      nearby_conflict = _has_nearby_shift(
          candidate, d, working, max_gap=max_gap
      )
      week_count = _shifts_in_week(candidate, d, working, exclude_date=d)
      weekly_conflict = (week_count + 1) > max_per_week
      if not nearby_conflict and not weekly_conflict:
        chosen = candidate
        queue.append(candidate)
        break
      skipped.append(candidate)

    if chosen is None:
      chosen = skipped.pop(0)
      queue.append(chosen)
      conflicts.add(d)

    for s in reversed(skipped):
      queue.appendleft(s)

    assignments[d] = chosen
    working[d] = chosen

  return assignments, conflicts


# ----------------------------
# HELPERS
# ----------------------------
def get_week_dates(any_date):
  monday = any_date - datetime.timedelta(days=any_date.weekday())
  return [monday + datetime.timedelta(days=i) for i in range(7)]


def generate_base_rota(initial_week, start_date, end_date):
  schedule = {}
  doctor_to_weekday = {doc: i for i, doc in enumerate(initial_week)}
  for i, doc in enumerate(initial_week):
    schedule[start_date + datetime.timedelta(days=i)] = doc
  current_week_start = start_date + datetime.timedelta(days=7)
  while current_week_start <= end_date:
    new_map = {doc: (wd - 2) % 7 for doc, wd in doctor_to_weekday.items()}
    for doc, wd in new_map.items():
      day = current_week_start + datetime.timedelta(days=wd)
      if day <= end_date:
        schedule[day] = doc
    doctor_to_weekday = new_map
    current_week_start += datetime.timedelta(days=7)
  return schedule


def generate_schedule(
    initial_week,
    start_date,
    end_date,
    holiday_assignments=None,
    manual_assignments=None,
):
  schedule = generate_base_rota(initial_week, start_date, end_date)
  if holiday_assignments:
    for d, doc in holiday_assignments.items():
      if start_date <= d <= end_date:
        schedule[d] = doc
  if manual_assignments:
    for d, doc in manual_assignments.items():
      if start_date <= d <= end_date:
        schedule[d] = doc
  return schedule


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


# ----------------------------
# CALENDAR DISPLAY
# ----------------------------
def display_calendar(schedule):
  manual_assignments = st.session_state.get("manual_assignments", {})
  holiday_names = st.session_state.get("holiday_names", {})
  holiday_conflicts = st.session_state.get("holiday_conflicts", set())
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
            conflict_icon = " ⚠️" if day in holiday_conflicts else ""
            holiday_tag = (
                f"<br><span style='font-size:10px'>🎉"
                f" {holiday_names[day]}{conflict_icon}</span>"
                if is_holiday
                else ""
            )
            color = "#%02x%02x%02x" % DOCTOR_COLORS.get(doc, (220, 220, 220))
            border = "border:2px solid #d9534f;" if is_holiday else ""
            cols[i].markdown(
                f"<div style='background-color:{color}; {border} padding:6px;"
                " border-radius:4px; text-align:center'>"
                f"<b>{day.day}</b><br>{doc}{icon}{holiday_tag}</div>",
                unsafe_allow_html=True,
            )
          else:
            cols[i].markdown("")


# ----------------------------
# PDF EXPORT (FIXED FOR MULTI-CELL ALIGNMENT)
# ----------------------------
def create_balance_pdf(
    df, start_date, end_date, filename="balance_summary.pdf"
):
  pdf = FPDF(orientation="L", unit="mm", format="A4")
  pdf.add_page()
  pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
  pdf.add_font("DejaVu", "B", "DejaVuSans.ttf", uni=True)

  pdf.set_font("DejaVu", "B", 16)
  pdf.cell(0, 10, "Doctor Balance Summary", ln=True, align="C")
  pdf.set_font("DejaVu", "", 12)
  pdf.cell(
      0,
      8,
      f"Period: {start_date.strftime('%d/%m/%Y')} –"
      f" {end_date.strftime('%d/%m/%Y')}",
      ln=True,
      align="C",
  )
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


def render_pdf_summary_table(pdf, df, title, start_date, end_date, filename):
  pdf.add_page()
  pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
  pdf.add_font("DejaVu", "B", "DejaVuSans.ttf", uni=True)

  pdf.set_font("DejaVu", "B", 16)
  pdf.cell(0, 10, title, ln=True, align="C")
  pdf.set_font("DejaVu", "", 12)
  pdf.cell(
      0,
      8,
