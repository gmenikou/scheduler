import streamlit as st
import datetime
import calendar
from fpdf import FPDF

# ---------------------------------------------
# 1. CONSTANTS
# ---------------------------------------------
DOCTORS = ["Elena", "Eva", "Maria", "Athina", "Alexandros", "Elia", "Christina"]

# ---------------------------------------------
# 2. HELPERS
# ---------------------------------------------
def get_week_dates(any_date):
    """Return list of Mon–Sun dates for the week of any_date."""
    monday = any_date - datetime.timedelta(days=any_date.weekday())
    return [monday + datetime.timedelta(days=i) for i in range(7)]


def backwards_rotation(start_assignments, dates):
    """
    start_assignments: dict {date: doctor} for the first week.
    dates: all dates of the month.
    Rotation: every next week shifts backwards by 2 positions.
    """
    week_doctors = [start_assignments[d] for d in sorted(start_assignments.keys())]
    assignments = {}
    dates_sorted = sorted(dates)

    # Group per 7 days (week blocks)
    weeks = [dates_sorted[i:i+7] for i in range(0, len(dates_sorted), 7)]

    for w_idx, block in enumerate(weeks):
        offset = (w_idx * 2) % 7
        rotated = week_doctors[-offset:] + week_doctors[:-offset]

        for i, d in enumerate(block):
            assignments[d] = rotated[i % 7]

    return assignments


def create_pdf(assignments, filename="schedule.pdf"):
    """Create simple PDF with Greek title (latin-1 friendly)."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    title = "PROGRAMMA GIATRWN"
    pdf.cell(190, 10, txt=title, ln=1, align='C')
    pdf.ln(4)

    for d in sorted(assignments.keys()):
        date_str = d.strftime("%d/%m/%Y")
        doctor = assignments[d]

        pdf.cell(60, 8, txt=date_str, border=1)
        pdf.cell(80, 8, txt=doctor, border=1, ln=1)

    pdf.output(filename)
    return filename


# ---------------------------------------------
# 3. STREAMLIT APP
# ---------------------------------------------
st.title("📅 Πρόγραμμα Γιατρών – Backwards Rotation")

# Initialize session_state
if "initial_week" not in st.session_state:
    st.session_state.initial_week = None
if "start_date" not in st.session_state:
    st.session_state.start_date = None

# ---- RESET ----
if st.button("🔄 Reset Όλων"):
    st.session_state.clear()
    st.success("Το session επαναφέρθηκε. Παρακαλώ ξεκινήστε ξανά.")
    st.stop()  # σταματά το script μετά το reset

# ---- Step 1: Select initial date ----
st.subheader("1️⃣ Επιλογή ημερομηνίας μέσα στην αρχική εβδομάδα")
selected_date = st.date_input("Επίλεξε ημερομηνία:", datetime.date.today())

week_dates = get_week_dates(selected_date)

st.write("Η εβδομάδα είναι:")
for d in week_dates:
    st.write("-", d.strftime("%d/%m/%Y"))

# ---- Step 2: Manual assignment (uniqueness check) ----
st.subheader("2️⃣ Ανάθεση γιατρών για την πρώτη εβδομάδα")

initial_week = {}
selected_doctors = []

cols = st.columns(7)

for i, d in enumerate(week_dates):
    with cols[i]:
        doc = st.selectbox(
            d.strftime("%a\n%d/%m"),
            DOCTORS,
            key=f"manual_{d}"
        )
        initial_week[d] = doc
        selected_doctors.append(doc)

# Check duplicates
if len(set(selected_doctors)) < len(selected_doctors):
    st.error("❗ Δεν επιτρέπονται διπλοί γιατροί στην ίδια εβδομάδα.")
else:
    if st.button("💾 Αποθήκευση αρχικής εβδομάδας"):
        st.session_state.initial_week = initial_week
        st.session_state.start_date = selected_date
        st.success("Η αρχική εβδομάδα αποθηκεύτηκε!")

if st.session_state.initial_week is None:
    st.stop()

# ---- Step 3: Full month schedule ----
st.subheader("3️⃣ Παραγωγή προγράμματος μηνός")

year = st.session_state.start_date.year
month = st.session_state.start_date.month

num_days = calendar.monthrange(year, month)[1]
all_dates = [datetime.date(year, month, d) for d in range(1, num_days + 1)]

assignments = backwards_rotation(st.session_state.initial_week, all_dates)

st.write("### 📋 Πρόγραμμα Μηνός")
for d in sorted(assignments.keys()):
    st.write(d.strftime("%d/%m/%Y"), "→", assignments[d])

# ---- Step 4: Export PDF ----
st.subheader("📄 Εκτύπωση")

if st.button("🖨️ Δημιουργία PDF"):
    filename = create_pdf(assignments)
    with open(filename, "rb") as f:
        st.download_button("⬇️ Κατέβασε PDF", data=f, file_name="schedule.pdf")
