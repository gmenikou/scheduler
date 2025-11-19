# app.py
import streamlit as st
import datetime
import calendar
from fpdf import FPDF
import json
import os
import colorsys
import math
import io

# -------------------------------
# Constants (original + extras)
# -------------------------------
DOCTORS = ["Elena", "Eva", "Maria", "Athina", "Alexandros", "Elia", "Christina"]
INIT_FILE = "initial_week.json"

# -------------------------------
# Original scheduling helpers
# -------------------------------
def get_week_dates(any_date):
    monday = any_date - datetime.timedelta(days=any_date.weekday())
    return [monday + datetime.timedelta(days=i) for i in range(7)]

def save_initial_week(initial_week):
    serializable = {d.strftime("%Y-%m-%d"): doc for d, doc in initial_week.items()}
    with open(INIT_FILE, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, sort_keys=True)

def load_initial_week():
    if os.path.exists(INIT_FILE):
        with open(INIT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {datetime.datetime.strptime(k, "%Y-%m-%d").date(): v for k, v in data.items()}
    return None

def rotate_week_list(week_list, shift):
    shift = shift % 7
    return week_list[-shift:] + week_list[:-shift]

def generate_schedule(initial_week, all_dates):
    schedule = {}
    week_list = [initial_week[d] for d in sorted(initial_week.keys())]
    initial_monday = min(initial_week.keys())

    # Group dates into weeks starting from initial_monday
    current = initial_monday
    weeks = []
    while current <= max(all_dates):
        week_block = [current + datetime.timedelta(days=i) for i in range(7)]
        weeks.append(week_block)
        current += datetime.timedelta(days=7)

    week_counter = 1  # Start counting rotation from week immediately after initial week
    for week_block in weeks:
        # Preserve initial week exactly
        if any(d in initial_week for d in week_block):
            for d in week_block:
                if d in initial_week:
                    schedule[d] = initial_week[d]
        else:
            # Rotation starts immediately from next week
            # NOTE: keep original rotation logic untouched
            rotated_week = rotate_week_list(week_list, -2 * week_counter)
            for idx, d in enumerate(week_block):
                if d in all_dates:
                    schedule[d] = rotated_week[idx % 7]
            week_counter += 1

    # Only keep dates from initial week onwards
    schedule = {d: doc for d, doc in schedule.items() if d >= initial_monday}
    return schedule

def generate_schedule_for_months(initial_week, start_month, num_months=1):
    all_schedules = {}
    for m in range(num_months):
        month = (start_month.month + m - 1) % 12 + 1
        year = start_month.year + ((start_month.month + m - 1) // 12)
        num_days = calendar.monthrange(year, month)[1]
        month_dates = [datetime.date(year, month, d) for d in range(1, num_days + 1)]
        schedule = generate_schedule(initial_week, month_dates)
        all_schedules[(year, month)] = schedule
    return all_schedules

# -------------------------------
# Automatic pastel color generator
# -------------------------------
def generate_doctor_colors(doctor_list):
    """
    Generate visually distinct pastel colors for each doctor.
    Returns hex strings like '#aabbcc'.
    """
    colors = {}
    n = max(1, len(doctor_list))
    for i, doc in enumerate(doctor_list):
        # Spread hues evenly
        hue = (i / n)
        # pastel: low saturation, high value
        r, g, b = colorsys.hsv_to_rgb(hue, 0.35, 0.95)
        hexcol = '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))
        colors[doc] = hexcol
    return colors

DOCTOR_COLORS = generate_doctor_colors(DOCTORS)

# -------------------------------
# PDF calendar exporter
# -------------------------------
class CalendarPDF(FPDF):
    def header(self):
        # No header text by default (we add month title in page body)
        pass

    def add_calendar_page(self, year, month, schedule, edits=None):
        if edits is None:
            edits = {}
        self.add_page()
        # Title
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, f"{calendar.month_name[month]} {year}", 0, 1, "C")
        self.ln(4)

        # Grid settings
        col_width = 26
        row_height = 16
        left_margin = (self.w - (col_width * 7)) / 2
        self.set_x(left_margin)

        # Weekday header
        self.set_font("Arial", "B", 10)
        for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            self.cell(col_width, row_height, d, 1, 0, "C")
        self.ln(row_height)
        self.set_x(left_margin)

        self.set_font("Arial", "", 9)
        cal = calendar.Calendar(firstweekday=0)
        for week in cal.monthdatescalendar(year, month):
            for d in week:
                if d.month != month:
                    self.cell(col_width, row_height, "", 1, 0, "C")
                else:
                    # apply edits override if present
                    doc = edits.get(d, schedule.get(d, ""))
                    # keep text limited
                    text = f"{d.day} {doc}"
                    self.cell(col_width, row_height, text, 1, 0, "C")
            self.ln(row_height)
            self.set_x(left_margin)

def export_calendar_pdf(all_schedules, edits_map, filename="calendar.pdf"):
    pdf = CalendarPDF()
    for (year, month), schedule in all_schedules.items():
        pdf.add_calendar_page(year, month, schedule, edits=edits_map.get((year, month), {}))
    # Save to in-memory bytes and return bytes buffer
    buf = io.BytesIO()
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    buf = BytesIO(pdf_bytes)
    return buf

# -------------------------------
# Streamlit UI helpers: Calendar grid & interactions
# -------------------------------
def apply_edits_to_schedule(schedule, edits):
    """
    schedule: dict date->doctor
    edits: dict date->doctor (overrides)
    returns new dict with overrides applied
    """
    merged = dict(schedule)
    merged.update(edits)
    return merged

def display_month_calendar_enhanced(year, month, schedule, edits, selected_doctor, enable_assign=True, dark_mode=False):
    """
    Displays one month as a calendar grid.
    schedule: base schedule dict date->doctor
    edits: overrides dict date->doctor
    selected_doctor: currently selected doctor (string or None)
    enable_assign: if True clicking a cell assigns selected_doctor to that date
    """
    # Merge schedule + edits for display
    merged = apply_edits_to_schedule(schedule, edits)

    st.markdown(f"### 🗓️ {calendar.month_name[month]} {year}")
    cal = calendar.Calendar(firstweekday=0)
    month_weeks = cal.monthdatescalendar(year, month)

    # Weekday header
    cols = st.columns(7)
    weekday_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    for i, c in enumerate(cols):
        c.markdown(f"**{weekday_names[i]}**")

    # Build grid with interactive buttons
    for w_idx, week in enumerate(month_weeks):
        cols = st.columns(7)
        for c_idx, d in enumerate(week):
            cell_col = cols[c_idx]
            if d.month != month:
                # empty
                cell_col.markdown("<div style='height:70px;background:#f6f6f6;border-radius:6px'></div>", unsafe_allow_html=True)
                continue

            doc = merged.get(d, "")
            # color for doctor (uses generated colors; fallback to gray)
            bg = DOCTOR_COLORS.get(doc, "#e0e0e0") if doc else "#ffffff"
            text_color = "#000000"
            # For dark mode, invert text color if bg is dark
            if dark_mode:
                # approximate luminance
                try:
                    r = int(bg[1:3], 16); g = int(bg[3:5], 16); b = int(bg[5:7], 16)
                    luminance = 0.2126*r + 0.7152*g + 0.0722*b
                    if luminance < 140:
                        text_color = "#ffffff"
                except Exception:
                    text_color = "#ffffff"

            # Build displayed text
            display_text = f"{d.day}"
            if doc:
                display_text += f"\n{doc}"

            # Use unique key per cell
            key = f"cell_{year}_{month}_{d.isoformat()}"

            # Create a small form so we can have a "Assign" button and a "Clear" button per cell if desired.
            with cell_col:
                # Card-like container
                html = f"""
                <div style="
                    border-radius:8px;
                    padding:8px;
                    min-height:70px;
                    display:flex;
                    flex-direction:column;
                    justify-content:space-between;
                    align-items:center;
                    background:{bg};
                    color:{text_color};
                    border:1px solid #ccc;
                ">
                    <div style="font-weight:700">{d.day}</div>
                    <div style="font-size:12px;white-space:pre-wrap;">{doc if doc else ''}</div>
                </div>
                """
                st.write(html, unsafe_allow_html=True)

                # Buttons for interactions
                c1, c2 = st.columns([1,1])
                if enable_assign:
                    if c1.button("Assign", key=key+"_assign"):
                        if selected_doctor:
                            # set edit in session_state
                            st.session_state.edits[d] = selected_doctor
                            st.rerun()
                        else:
                            st.warning("Select a doctor from the 'Assign doctor' selector above before assigning.")
                if c2.button("Clear", key=key+"_clear"):
                    if d in st.session_state.edits:
                        del st.session_state.edits[d]
                    else:
                        # allow clearing base schedule by setting to empty edit
                        st.session_state.edits[d] = ""
                    st.rerun()

                # Small details / modal
                if st.button("Details", key=key + "_details"):
                    # show modal with info
                    try:
                        with st.modal(f"{d.strftime('%A, %d %B %Y')}"):
                            st.subheader(d.strftime("%A, %d %B %Y"))
                            base_doc = schedule.get(d, "(no assignment)")
                            edited = st.session_state.edits.get(d, None)
                            st.write(f"Base assignment: **{base_doc}**")
                            if edited is not None:
                                st.write(f"Edited assignment: **{edited if edited else '(cleared)'}**")
                            else:
                                st.write("No edits for this date.")
                            st.write("---")
                            st.write("Use the Assign selector above and click **Assign** to set/override this day.")
                    except Exception:
                        # fallback if modal not supported
                        st.write("Details:")
                        st.write(d.strftime("%A, %d %B %Y"))
                        st.write(f"Base assignment: **{schedule.get(d,'(no assignment)')}**")
                        if st.session_state.edits.get(d) is not None:
                            st.write(f"Edited assignment: **{st.session_state.edits[d]}**")

# -------------------------------
# Streamlit app UI (main)
# -------------------------------
st.set_page_config(layout="wide", page_title="Programma Giatron - Calendar Grid")

st.title("📅 Programma Giatron – Backwards Rotation (Calendar Grid)")

# Session state initializers
if "initial_week" not in st.session_state:
    st.session_state.initial_week = load_initial_week()
# Auto-restore start_date if initial_week was loaded from file
if "start_date" not in st.session_state:
    if st.session_state.initial_week:
        st.session_state.start_date = min(st.session_state.initial_week.keys())
    else:
        st.session_state.start_date = None

if "start_date" not in st.session_state:
    st.session_state.start_date = None
if "edits" not in st.session_state:
    # edits: dict date->doctor overrides (keys are datetime.date)
    st.session_state.edits = {}
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# Top controls: Reset
col1, col2, col3 = st.columns([1,2,1])
with col1:
    if st.button("🔄 Reset All"):
        # clear session and file
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        if os.path.exists(INIT_FILE):
            os.remove(INIT_FILE)
        st.success("Session and initial week deleted.")
        st.rerun()

with col3:
    # Dark mode toggle
    if st.checkbox("🌙 Dark Mode", value=st.session_state.dark_mode):
        st.session_state.dark_mode = True
    else:
        st.session_state.dark_mode = False

# If dark mode, inject CSS
if st.session_state.dark_mode:
    DARK_MODE_CSS = """
    <style>
    .stApp {
        background-color: #0f1115;
        color: #e6eef8;
    }
    .css-1d391kg { color: #e6eef8; } /* title fallback */
    .stMarkdown p { color: #e6eef8; }
    .stButton>button { background-color: #2b2f36; color: #e6eef8; }
    </style>
    """
    st.markdown(DARK_MODE_CSS, unsafe_allow_html=True)

# Step 1: Select initial week date (same UX as original)
st.subheader("1️⃣ Select a date in the initial week")
if st.session_state.start_date is None:
    selected_date = st.date_input("Choose a date:", datetime.date.today())
else:
    selected_date = st.session_state.start_date

week_dates = get_week_dates(selected_date)
st.write("The week is:")
colw = st.columns(7)
for i, d in enumerate(week_dates):
    colw[i].write(f"**{d.strftime('%a %d/%m/%Y')}**")

# Step 2: Assign doctors for initial week (unchanged logic)
st.subheader("2️⃣ Assign doctors for the first week")
if st.session_state.initial_week is None:
    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            doc = st.selectbox(d.strftime("%a\n%d/%m"), DOCTORS, key=f"manual_{d}")
            initial_week[d] = doc

    if st.button("💾 Save initial week"):
        st.session_state.initial_week = initial_week
        st.session_state.start_date = selected_date
        save_initial_week(initial_week)
        st.success("Initial week saved!")
else:
    st.info("Initial week already saved. Use Reset to change it.")
    if st.session_state.initial_week:
        st.write("Your assigned initial week:")
        for d in sorted(st.session_state.initial_week.keys()):
            st.write(f"{d.strftime('%d/%m/%Y')} ({d.strftime('%a')}) → {st.session_state.initial_week[d]}")

# Step 3: Generate schedule for forthcoming months (unchanged)
if st.session_state.initial_week and st.session_state.start_date:
    st.subheader("3️⃣ Generate schedule for forthcoming months")
    today = datetime.date.today()
    months_options = [(today + datetime.timedelta(days=30*i)).replace(day=1) for i in range(12)]
    months_display = [d.strftime("%B %Y") for d in months_options]
    selected_month_index = st.selectbox("Choose start month:", list(range(12)),
                                        format_func=lambda x: months_display[x])
    selected_month_date = months_options[selected_month_index]

    num_months = st.number_input("Number of months to generate:", min_value=1, max_value=12, value=1, step=1)

    if st.button("Generate Schedule"):
        multi_schedule = generate_schedule_for_months(st.session_state.initial_week,
                                                      selected_month_date, num_months)
        # Save the generated schedule to session state so edits can be applied
        st.session_state.generated_schedule = multi_schedule
        # Clear previous edits unless user wants to keep them
        if "edits" not in st.session_state:
            st.session_state.edits = {}

        st.success("Schedule generated. Scroll down to view and edit in calendar grid.")

# Calendar visualization and editing
if "generated_schedule" in st.session_state:
    st.subheader("📋 Calendar Grid (click cells to Assign / Clear)")

    # Left side: controls for assignment
    ctrl_col, preview_col = st.columns([1, 3])
    with ctrl_col:
        st.write("### Assign doctor")
        selected_doctor = st.selectbox("Select doctor to assign:", [""] + DOCTORS, index=0)
        st.write("Click a date's **Assign** button to apply the selected doctor.")
        st.write("Press **Clear** on a cell to remove an edit (revert to base schedule) or to blank it.")
        st.markdown("---")
        # Quick actions
        if st.button("Clear all edits"):
            st.session_state.edits = {}
            st.rerun()
        if st.button("Export calendar PDF (with edits)"):
            # Build edits map grouped per (year, month)
            edits_map = {}
            for d, doc in st.session_state.edits.items():
                if isinstance(d, str):
                    d_obj = datetime.datetime.strptime(d, "%Y-%m-%d").date()
                else:
                    d_obj = d
                key = (d_obj.year, d_obj.month)
                edits_map.setdefault(key, {})[d_obj] = doc
            buf = export_calendar_pdf(st.session_state.generated_schedule, edits_map)
            st.download_button("⬇️ Download Calendar PDF", data=buf, file_name="calendar.pdf")

    with preview_col:
        # Multi-month layout: two columns of months
        months = list(st.session_state.generated_schedule.items())
        cols_count = 2
        col_blocks = [st.container() for _ in range(cols_count)]
        for idx, ((year, month), schedule) in enumerate(months):
            target_col = col_blocks[idx % cols_count]
            with target_col:
                # Collect edits relevant to this month
                month_edits = {}
                for d, doc in st.session_state.edits.items():
                    # keys in session_state.edits are datetime.date objects
                    if isinstance(d, str):
                        try:
                            d_obj = datetime.datetime.strptime(d, "%Y-%m-%d").date()
                        except Exception:
                            continue
                    else:
                        d_obj = d
                    if d_obj.year == year and d_obj.month == month:
                        month_edits[d_obj] = doc
                # display month calendar
                display_month_calendar_enhanced(year, month, schedule, month_edits,
                                                selected_doctor if selected_doctor else None,
                                                enable_assign=True,
                                                dark_mode=st.session_state.dark_mode)

    st.markdown("---")
    # Show a compact list of edits (for convenience)
    if st.session_state.edits:
        st.subheader("📝 Current edits (overrides)")
        for d in sorted(st.session_state.edits.keys()):
            val = st.session_state.edits[d]
            st.write(f"{d.strftime('%d/%m/%Y')} → {val if val else '(cleared)'}")

    # Offer ability to persist edits to a file (optional)
    if st.button("💾 Save edits to file (edits.json)"):
        serializable = {d.strftime("%Y-%m-%d"): doc for d, doc in st.session_state.edits.items()}
        with open("edits.json", "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        st.success("Edits saved to edits.json")

else:
    st.info("Create and save an initial week, then press 'Generate Schedule' to view the calendar.")



