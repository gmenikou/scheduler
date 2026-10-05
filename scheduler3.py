import base64
import calendar
from collections import defaultdict
import datetime
import json
import os
from fpdf import FPDF
import pandas as pd
import requests
import streamlit as str_lit

# ----------------------------
# CONSTANTS & SETUP
# ----------------------------
DEFAULT_DOCTORS = [
    "Χριστίνα",
    "Αθηνά",
    "Μαρία",
    "Έλια",
    "Αλέξανδρος",
    "Εύα",
    "Έλενα",
]

DEFAULT_DOCTOR_COLORS = {
    "Έλενα": (255, 182, 193),
    "Εύα": (152, 251, 152),
    "Μαρία": (176, 196, 222),
    "Αθηνά": (255, 250, 205),
    "Αλέξανδρος": (221, 160, 221),
    "Έλια": (175, 238, 238),
    "Χριστίνα": (245, 222, 179),
}

EXTRA_COLORS = [
    (255, 218, 185),
    (230, 230, 250),
    (255, 228, 225),
    (240, 255, 240),
    (240, 248, 255),
    (255, 248, 220),
]

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
GREEK_WEEKDAY_LABELS = ["Δευ", "Τρι", "Τετ", "Πεμ", "Παρ", "Σαβ", "Κυρ"]

GREEK_MONTHS = [
    "",
    "Ιανουάριος",
    "Φεβρουάριος",
    "Μάρτιος",
    "Απρίλιος",
    "Μάιος",
    "Ιούνιος",
    "Ιούλιος",
    "Αύγουστος",
    "Σεπτέμβριος",
    "Οκτώβριος",
    "Νοέμβριος",
    "Δεκέμβριος",
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

STATE_FILE = "last_schedule_state.json"

# --- ΡΥΘΜΙΣΕΙΣ GITHUB SYNC ---
REPO_OWNER = "TO_GITHUB_USERNAME_ΣΟΥ"
REPO_NAME = "TO_REPO_NAME_ΣΟΥ"
FILE_PATH = "schedule_data.json"


def save_json_to_github(data_dict):
  # Ανεβάζει αυτόματα το ενημερωμένο αρχείο JSON στο GitHub
  token = str_lit.secrets.get("GITHUB_TOKEN")
  if not token:
    return

  url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
  headers = {
      "Authorization": f"Bearer {token}",
      "Accept": "application/vnd.github+json",
  }

  response = requests.get(url, headers=headers)
  sha = response.json().get("sha") if response.status_code == 200 else None

  json_content = json.dumps(data_dict, ensure_ascii=False, indent=4)
  content_encoded = base64.b64encode(json_content.encode("utf-8")).decode(
      "utf-8"
  )

  payload = {
      "message": "Auto-update schedule and telegram IDs from Streamlit",
      "content": content_encoded,
      "branch": "main",
  }
  if sha:
    payload["sha"] = sha

  requests.put(url, headers=headers, json=payload)


# ----------------------------
# STATE PERSISTENCE FUNCTIONS
# ----------------------------
def save_state_to_file(
    schedule,
    holiday_names,
    balance,
    manual_assignments,
    doctors,
    initial_week,
    empty_tooltips,
):
  data = {
      "schedule": (
          {
              d.strftime("%Y-%m-%d"): doc
              for d, doc in schedule.items()
              if doc is not None
          }
          if schedule
          else {}
      ),
      "holiday_names": (
          {d.strftime("%Y-%m-%d"): name for d, name in holiday_names.items()}
          if holiday_names
          else {}
      ),
      "manual_assignments": (
          {
              d.strftime("%Y-%m-%d"): doc
              for d, doc in manual_assignments.items()
          }
          if manual_assignments
          else {}
      ),
      "empty_tooltips": (
          {d.strftime("%Y-%m-%d"): t for d, t in empty_tooltips.items()}
          if empty_tooltips
          else {}
      ),
      "doctors": doctors,
      "initial_week": initial_week,
  }
  with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

  try:
    save_json_to_github(data)
  except Exception as e:
    print("GitHub sync error:", e)


def load_state_from_file():
  if not os.path.exists(STATE_FILE):
    return None
  try:
    with open(STATE_FILE, "r", encoding="utf-8") as f:
      data = json.load(f)

    schedule = {
        datetime.datetime.strptime(d, "%Y-%m-%d").date(): doc
        for d, doc in data.get("schedule", {}).items()
    }
    holiday_names = {
        datetime.datetime.strptime(d, "%Y-%m-%d").date(): name
        for d, name in data.get("holiday_names", {}).items()
    }
    manual_assignments = {
        datetime.datetime.strptime(d, "%Y-%m-%d").date(): doc
        for d, doc in data.get("manual_assignments", {}).items()
    }
    empty_tooltips = {
        datetime.datetime.strptime(d, "%Y-%m-%d").date(): t
        for d, t in data.get("empty_tooltips", {}).items()
    }

    return {
        "schedule": schedule,
        "holiday_names": holiday_names,
        "manual_assignments": manual_assignments,
        "empty_tooltips": empty_tooltips,
        "doctors": data.get("doctors", DEFAULT_DOCTORS),
        "initial_week": data.get("initial_week", DEFAULT_DOCTORS[:7]),
    }
  except Exception as e:
    print("Sfalma fortosis state:", e)
    return None


# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
def get_doctor_color(doc_name, doctors_list):
  if not doc_name:
    return (240, 240, 240)
  if doc_name in DEFAULT_DOCTOR_COLORS:
    return DEFAULT_DOCTOR_COLORS[doc_name]
  try:
    idx = doctors_list.index(doc_name) % len(EXTRA_COLORS)
    return EXTRA_COLORS[idx]
  except ValueError:
    return (220, 220, 220)


def _week_monday(date):
  return date - datetime.timedelta(days=date.weekday())


def _has_nearby_shift(doctor, date, schedule, min_gap=3):
  for d, doc in schedule.items():
    if doc == doctor and d != date and abs((d - date).days) <= min_gap:
      return True
  return False


def _has_fri_sun_same_weekend(doctor, date, schedule, exclude_date=None):
  if date.weekday() not in (4, 6):
    return False
  target_wk = _week_monday(date)

  all_shifts = [
      (d, doc)
      for d, doc in schedule.items()
      if d != exclude_date and doc is not None
  ]
  if exclude_date and exclude_date.weekday() in (4, 6):
    all_shifts.append((exclude_date, doctor))

  for d, doc in all_shifts:
    if doc == doctor and _week_monday(d) == target_wk:
      if (date.weekday() == 4 and d.weekday() == 6) or (
          date.weekday() == 6 and d.weekday() == 4
      ):
        return True
  return False


def _has_weekend_in_adjacent_week(doctor, date, schedule, exclude_date=None):
  if date.weekday() not in (4, 5, 6):
    return False
  target_wk = _week_monday(date)

  all_shifts = [
      (d, doc)
      for d, doc in schedule.items()
      if d != exclude_date and doc is not None
  ]
  if exclude_date and exclude_date.weekday() in (4, 5, 6):
    all_shifts.append((exclude_date, doctor))

  for d, doc in all_shifts:
    if doc == doctor and d.weekday() in (4, 5, 6) and d != date:
      other_wk = _week_monday(d)
      if abs((target_wk - other_wk).days) == 7:
        return True
  return False


def _shifts_in_week(doctor, date, schedule, exclude_date=None):
  wk = _week_monday(date)
  return sum(
      1
      for d, doc in schedule.items()
      if doc == doctor
      and d != exclude_date
      and _week_monday(d) == wk
      and doc is not None
  )


def _month_stats(doctor, date, schedule, exclude_date=None):
  total = 0
  weekend_fri_sat_sun_count = 0
  weekdays_in_month = []

  month_shifts = [
      d
      for d, doc in schedule.items()
      if doc == doctor
      and d.year == date.year
      and d.month == date.month
      and d != exclude_date
      and doc is not None
  ]
  if (
      exclude_date
      and exclude_date.year == date.year
      and exclude_date.month == date.month
  ):
    month_shifts.append(exclude_date)

  for d in month_shifts:
    total += 1
    weekdays_in_month.append(d.weekday())
    if d.weekday() in (4, 5, 6):
      weekend_fri_sat_sun_count += 1

  return total, weekend_fri_sat_sun_count, weekdays_in_month


def _within_dynamic_month_cap(
    doctor, date, schedule, num_docs, holiday_dates, exclude_date=None
):
  total, weekend_count, weekdays_in_month = _month_stats(
      doctor, date, schedule, exclude_date
  )

  if weekend_count > 2:
    return False

  if (
      weekdays_in_month.count(4) > 1
      or weekdays_in_month.count(5) > 1
      or weekdays_in_month.count(6) > 1
  ):
    return False

  has_sat = 5 in weekdays_in_month
  has_sun = 6 in weekdays_in_month
  if has_sat and has_sun:
    weekdays_count = sum(1 for w in weekdays_in_month if w in (0, 1, 2, 3))
    if total > 5:
      return False
    if total == 5 and weekdays_count < 3:
      return False

  return total <= 5


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
