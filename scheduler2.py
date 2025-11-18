# doctor_shift_scheduler_streamlit.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
from collections import defaultdict, deque
import pickle

# ---------------------------
# Helper functions

def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def get_current_week_dates():
    """Return Monday-Sunday dates for current week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]

def weeks_in_month(year, month):
    """Return Monday dates of all weeks intersecting the month."""
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    cur = first - timedelta(days=first.weekday())
    mondays = []
    while cur <= last:
        mondays.append(cur)
        cur += timedelta(days=7)
    return mondays

# ---------------------------
# Rotation logic

def assign_rotation(dates, doctors, initial_week_assignments):
    """Assign doctors to dates based on backward-2-days-per-week rotation, starting from initial week."""
    assign_map = {}
    if not initial_week_assignments:
        return assign_map

    # Determine reference: first date in initial week
    ref_date = min(initial_week_assignments.keys())
    ref_doc_map = {d: initial_week_assignments[d] for d in initial_week_assignments}

    # Build rotation for the rest of the month
    N = len(doctors)
    for d in dates:
        if d in ref_doc_map:
            assign_map[d] = ref_doc_map[d]
            continue
        # compute number of weeks between current date and ref_date
        weeks_between = ((d - ref_date).days) // 7
        # backward 2 days per week from reference weekday
        weekday_shift = (ref_date.weekday() - 2 * weeks_between) % 7
        # get the Monday of current date's week
        monday = d - timedelta(days=d.weekday())
        candidate_date = monday + timedelta(days=weekday_shift)
        if candidate_date != d:
            continue  # rotation skips if the weekday doesn't match
        # rotate doctor index
        ref_doc_index = doctors.index(initial_week_assignments[ref_date])
        doc_index = (ref_doc_index + weeks_between) % N
        assign_map[d] = doctors[doc_index]

    return assign_map

# ---------------------------
# Streamlit App

st.set_page_config(page_title="Doctor Shift Scheduler", layout="wide")

# Session state initialization
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []
if 'initial_week_assigned' not in st.session_state:
    st.session_state.initial_week_assigned = False
if 'initial_week_assignments' not in st.session_state:
    st.session_state.initial_week_assignments = {}

st.title("Doctor Shift Scheduler — Backward 2-day rotation")

# ---------------------------
# Controls
left, mid, right = st.columns([2,1,1])

with left:
    st.subheader("Month / Reference")
    year = st.number_input("Year", min_value=2000, max_value=2100, value=date.today().year)
    month = st.selectbox("Month", list(range(1,13)), index=date.today().month-1)
    start_balance = st.checkbox("Start balance from this month", value=False)

with mid:
    st.subheader("Actions")
    if st.button("Generate Schedule"):
        ym = (year, month)
        month_dates_list = month_dates(year, month)
        # If initial week not assigned, prompt manual input
        if not st.session_state.initial_week_assigned:
            st.info("Please assign the initial week first (current week).")
        else:
            # assign rest of month automatically
            assign_map = assign_rotation(month_dates_list, st.session_state.doctors, st.session_state.initial_week_assignments)
            st.session_state.prev_assignments.update(assign_map)
            if ym not in st.session_state.generated_months:
                st.session_state.generated_months.append(ym)
            st.success(f"Schedule generated for {calendar.month_name[month]} {year}")

    if st.button("Reset All"):
        st.session_state.prev_assignments.clear()
        st.session_state.generated_months.clear()
        st.session_state.initial_week_assignments.clear()
        st.session_state.initial_week_assigned = False
        st.session_state.holidays.clear()
        st.success("All data reset")

    if st.button("Save State"):
        data = {
            "prev_assignments": {d.isoformat(): doc for d, doc in st.session_state.prev_assignments.items()},
            "initial_week_assignments": {d.isoformat(): doc for d, doc in st.session_state.initial_week_assignments.items()},
            "holidays": {f"{y}-{m}":[d.isoformat() for d in s] for (y,m),s in st.session_state.holidays.items()},
            "generated_months": st.session_state.generated_months
        }
        with open("schedule_state.pkl","wb") as f:
            pickle.dump(data, f)
        st.success("State saved.")

    if st.button("Load State"):
        try:
            with open("schedule_state.pkl","rb") as f:
                data = pickle.load(f)
            st.session_state.prev_assignments = {datetime.fromisoformat(k).date():v for k,v in data["prev_assignments"].items()}
            st.session_state.initial_week_assignments = {datetime.fromisoformat(k).date():v for k,v in data["initial_week_assignments"].items()}
            st.session_state.generated_months = data.get("generated_months",[])
            st.session_state.holidays = defaultdict(set)
            for key,lst in data.get("holidays", {}).items():
                y,m = map(int,key.split("-"))
                st.session_state.holidays[(y,m)] = set(datetime.fromisoformat(d).date() for d in lst)
            if st.session_state.initial_week_assignments:
                st.session_state.initial_week_assigned = True
            st.success("State loaded")
        except Exception as e:
            st.error(f"Failed to load state: {e}")

with right:
    st.subheader("Print")
    if st.button("Print Schedule"):
        st.write("Printing the last generated month to printer (browser print dialog)")
        if st.session_state.generated_months:
            selected_ym = st.session_state.generated_months[-1]
            y,m = selected_ym
            month_dates_list = month_dates(y,m)
            df_print = pd.DataFrame({
                "Date": [d.isoformat() for d in month_dates_list],
                "Weekday": [calendar.day_name[d.weekday()] for d in month_dates_list],
                "Doctor": [st.session_state.prev_assignments.get(d,"") for d in month_dates_list]
            })
            st.dataframe(df_print)
            st.info("Use browser print dialog to print this table.")

# ---------------------------
# Initial week manual assignment
if not st.session_state.initial_week_assigned:
    st.subheader("Manual assignment — Initial week (current week)")
    week_dates = get_current_week_dates()
    manual_assignments = {}
    for d in week_dates:
        doc = st.selectbox(f"{d} ({calendar.day_name[d.weekday()]})", st.session_state.doctors, key=str(d))
        manual_assignments[d] = doc
    if st.button("Save Initial Week Assignments"):
        st.session_state.initial_week_assignments = manual_assignments
        st.session_state.prev_assignments.update(manual_assignments)
        st.session_state.initial_week_assigned = True
        st.success("Initial week assignments saved. Future dates will populate automatically.")

# ---------------------------
# Month viewer & holiday toggling / balances
st.markdown("---")

if st.session_state.generated_months:
    selected_ym = st.selectbox("View generated month", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)
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
    st.dataframe(df, height=480)

    # Balance panel
    balance_rows = []
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_non_weekday = sum(1 for (ym_k,holset) in st.session_state.holidays.items() for hd in holset
                              if st.session_state.prev_assignments.get(hd)==doc and hd.weekday() not in (5,6))
        balance_rows.append({"Doctor":doc,"Fridays":fr,"Saturdays":sa,"Sundays":su,"Holidays (non-weekend)":hol_non_weekday})
    st.subheader("Balance Panel (cumulative)")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Doctor"))

