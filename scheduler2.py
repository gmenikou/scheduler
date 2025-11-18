# doctor_shift_scheduler_streamlit.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
from collections import defaultdict
from io import BytesIO
import pickle

# ---------------------------
# Helper functions

def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def weekday_monday(d: date):
    return d - timedelta(days=d.weekday())

def weeks_in_month(year, month):
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    cur = weekday_monday(first)
    mondays = []
    while cur <= last:
        mondays.append(cur)
        cur += timedelta(days=7)
    return mondays

def assign_rotation_for_month(year, month, doctors, ref_date, ref_doc, manual_assign=None):
    """Assign rotation for the month starting from ref_date and ref_doc using backward 2-days/week rule."""
    mondays = weeks_in_month(year, month)
    N = len(doctors)
    try:
        ref_index = doctors.index(ref_doc)
    except ValueError:
        ref_index = 0
    ref_monday = weekday_monday(ref_date)
    assign_map = {}

    for week_idx, week_monday in enumerate(mondays):
        weeks_between = (week_monday - ref_monday).days // 7
        doc_idx = (ref_index + weeks_between) % N
        doc = doctors[doc_idx]
        shift_weekday = (ref_date.weekday() - 2 * weeks_between) % 7
        shift_date = week_monday + timedelta(days=shift_weekday)
        if shift_date.year == year and shift_date.month == month:
            if manual_assign and shift_date in manual_assign:
                assign_map[shift_date] = manual_assign[shift_date]
            else:
                assign_map[shift_date] = doc
    return assign_map

def print_schedule_to_html(dates, assignments, holidays, month, year):
    rows = []
    for d in dates:
        doc = assignments.get(d,"")
        is_hol = d in holidays
        rows.append(f"<tr><td>{d}</td><td>{calendar.day_name[d.weekday()]}</td><td>{doc}</td><td>{'Yes' if is_hol else ''}</td></tr>")
    html = f"""
    <html>
    <head>
    <title>Schedule {calendar.month_name[month]} {year}</title>
    <style>
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid black; padding: 5px; text-align: left; }}
    th {{ background-color: #f2f2f2; }}
    .holiday {{ background-color: yellow; }}
    </style>
    </head>
    <body>
    <h2>Schedule for {calendar.month_name[month]} {year}</h2>
    <table>
    <tr><th>Date</th><th>Weekday</th><th>Doctor</th><th>Holiday</th></tr>
    {''.join(rows)}
    </table>
    </body>
    </html>
    """
    return html

# ---------------------------
# Streamlit App Setup

st.set_page_config(page_title="Doctor Shift Scheduler", layout="wide")

# Session state
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []
if 'ref_date' not in st.session_state:
    st.session_state.ref_date = date.today()
if 'ref_doc' not in st.session_state:
    st.session_state.ref_doc = st.session_state.doctors[0]

st.title("Doctor Shift Scheduler — Backwards 2-day weekly rotation")

# ---------------------------
# Controls

left, mid, right = st.columns([2,1,1])

with left:
    st.subheader("Month / Reference settings")
    year = st.number_input("Year", min_value=2000, max_value=2100, value=date.today().year)
    month = st.selectbox("Month", list(range(1,13)), index=date.today().month-1)
    start_balance = st.checkbox("Start balance from this month (reset)", value=False)
    st.markdown("**Reference (rotation baseline)**")
    ref_date = st.date_input("Reference date (week & weekday baseline)", value=st.session_state.ref_date)
    ref_doc = st.selectbox("Reference doctor (works on reference date)", st.session_state.doctors, index=st.session_state.doctors.index(st.session_state.ref_doc))

with mid:
    st.subheader("Actions")
    if st.button("Generate Schedule"):
        st.session_state.ref_date = ref_date
        st.session_state.ref_doc = ref_doc
        ym = (year, month)

        # Determine current week Monday–Sunday
        today = date.today()
        week_monday = weekday_monday(today)
        week_dates = [week_monday + timedelta(days=i) for i in range(7)]

        # Manual first-week assignment table
        st.write("### Assign First Week (Monday–Sunday)")
        manual_df = pd.DataFrame({
            "Date": [d for d in week_dates],
            "Weekday": [calendar.day_name[d.weekday()] for d in week_dates],
            "Doctor": [st.session_state.doctors[0] for _ in range(7)]
        })
        manual_assign = {}
        for idx, row in manual_df.iterrows():
            doc = st.selectbox(f"{row['Date']} ({row['Weekday']})", st.session_state.doctors, key=f"manual_{row['Date']}")
            manual_assign[row['Date']] = doc

        # Generate assignments for the month
        assign_map = assign_rotation_for_month(year, month, st.session_state.doctors, st.session_state.ref_date, st.session_state.ref_doc, manual_assign=manual_assign)
        st.session_state.prev_assignments.update(assign_map)

        if ym not in st.session_state.generated_months:
            st.session_state.generated_months.append(ym)
        if start_balance:
            st.session_state.prev_assignments = assign_map.copy()
            st.session_state.generated_months = [ym]

        st.success(f"Schedule generated for {calendar.month_name[month]} {year}")

    if st.button("Reset All"):
        st.session_state.prev_assignments.clear()
        st.session_state.holidays.clear()
        st.session_state.generated_months.clear()
        st.success("Reset all schedules and holidays")

    if st.button("Save State"):
        data = {
            "prev_assignments": {d.isoformat(): doc for d,doc in st.session_state.prev_assignments.items()},
            "holidays": {f"{y}-{m}":[d.isoformat() for d in s] for (y,m),s in st.session_state.holidays.items()},
            "generated_months": st.session_state.generated_months,
            "ref_date": st.session_state.ref_date.isoformat(),
            "ref_doc": st.session_state.ref_doc
        }
        with open("schedule_state.pkl","wb") as f:
            pickle.dump(data,f)
        st.success("State saved.")

    if st.button("Load State"):
        try:
            with open("schedule_state.pkl","rb") as f:
                data = pickle.load(f)
            st.session_state.prev_assignments = {datetime.fromisoformat(k).date():v for k,v in data["prev_assignments"].items()}
            st.session_state.holidays = defaultdict(set)
            for key,lst in data.get("holidays",{}).items():
                y,m = map(int,key.split("-"))
                st.session_state.holidays[(y,m)] = set(datetime.fromisoformat(d).date() for d in lst)
            st.session_state.generated_months = data.get("generated_months",[])
            st.session_state.ref_date = datetime.fromisoformat(data.get("ref_date")).date()
            st.session_state.ref_doc = data.get("ref_doc",st.session_state.doctors[0])
            st.success("State loaded.")
        except Exception as e:
            st.error(f"Failed to load state: {e}")

with right:
    st.subheader("Print")
    if st.button("Print current month"):
        if not st.session_state.generated_months:
            st.warning("No month generated yet.")
        else:
            ym = st.session_state.generated_months[-1]
            y,m = ym
            dates = month_dates(y,m)
            holidays = st.session_state.holidays.get(ym,set())
            html = print_schedule_to_html(dates, st.session_state.prev_assignments, holidays, m, y)
            b = BytesIO()
            b.write(html.encode('utf-8'))
            b.seek(0)
            st.download_button("Download Printable Schedule", b, file_name=f"schedule_{y}_{m}.html", mime="text/html")
            st.info("Open HTML file and print from browser")

# ---------------------------
# Month viewer & balances
st.markdown("---")

if st.session_state.generated_months:
    selected_ym = st.selectbox("View generated month", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)

    st.subheader(f"Schedule for {calendar.month_name[m]} {y}")

    default_hols = list(st.session_state.holidays.get(selected_ym,set()))
    date_strs = [d.isoformat()+" - "+calendar.day_name[d.weekday()] for d in dates]
    date_map = {date_strs[i]: dates[i] for i in range(len(dates))}
    selected_defaults = [s.isoformat()+" - "+calendar.day_name[s.weekday()] for s in default_hols if s in dates]
    hol_selection = st.multiselect("Toggle holidays (shifts unchanged)", date_strs, default=selected_defaults)
    new_hols = set(date_map[s] for s in hol_selection)
    st.session_state.holidays[selected_ym] = new_hols

    # Recompute assignments for display (rotation unchanged)
    assign_map = assign_rotation_for_month(y,m, st.session_state.doctors, st.session_state.ref_date, st.session_state.ref_doc)
    st.session_state.prev_assignments.update(assign_map)

    rows = []
    for d in dates:
        doc = st.session_state.prev_assignments.get(d,"")
        is_hol = d in st.session_state.holidays.get(selected_ym,set())
        rows.append({
            "Date": d,
            "Weekday": calendar.day_name[d.weekday()],
            "Doctor": doc,
            "Holiday": "Yes" if is_hol else ""
        })
    df = pd.DataFrame(rows)
    st.dataframe(df.style.applymap(lambda v:'background-color: yellow' if v=="Yes" else '', subset=['Holiday']), height=480)

    # Balance panel
    balance_rows=[]
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_non_weekday=0
        for (ym_k, holset) in st.session_state.holidays.items():
            for hd in holset:
                if st.session_state.prev_assignments.get(hd)==doc and hd.weekday() not in (5,6):
                    hol_non_weekday+=1
        balance_rows.append({
            "Doctor":doc,
            "Fridays":fr,
            "Saturdays":sa,
            "Sundays":su,
            "Holidays (non-weekend)":hol_non_weekday
        })
    st.subheader("Balance Panel (cumulative)")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Doctor"))

else:
    st.info("No months generated yet. Use controls above to generate a month.")
