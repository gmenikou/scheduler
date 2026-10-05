import calendar
from collections import defaultdict
import datetime
import json
import os
import base64
import requests
from fpdf import FPDF
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

# --- ΡΥΘΜΙΣΕΙΣ GITHUB SYNC (Για το Make.com & Telegram Reminders) ---
REPO_OWNER = "TO_GITHUB_USERNAME_ΣΟΥ"  # <-- Βάλε το username σου στο GitHub
REPO_NAME = "TO_REPO_NAME_ΣΟΥ"  # <-- Βάλε το όνομα του repository σου
FILE_PATH = "schedule_data.json"


def save_json_to_github(data_dict):
  """Ανεβάζει αυτόματα το ενημερωμένο αρχείο JSON στο GitHub για να το διαβάζει το Make.com
