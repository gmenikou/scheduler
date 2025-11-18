# doctor_shift_scheduler_streamlit.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
from collections import defaultdict
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

# ---------------------------
# Rotation logic using manual initial week

def assign_rotation_for_month(year, month, doctors, initial_week_assignments, continue_across_months=True):
    """
    Populate month using backward-2-days rotation from manual initial week.
    initial_week_assignments: dict {date: doctor} for 7-day reference week
    """
    N = len(doctors)
    dates_in_month = month_dates(year, month)
    assign_map = {}

    # Sort the initial week dates
    initial_week = sorted(initial_week_assignments.keys())
    for d in initial_week:
        if d.month == month:
            assign_map[d] = initial_week_assignments[d]

    # Now fill rest of the month
    # Step through days in month
    for d in dates_in_month:
        if d in assign_map:
            continue  # already assigned
        # find previous assigned date before d
        prev_dates = [pd for pd in sorted(assign_map.keys()) if pd < d]
        if prev_dates:
            last_assigned_date = prev_dates[-1]
            last_doc = assign_map[last_assigned_date]
            last_idx = doctors.index(last_doc)
            # rotate backwards: find previous doctor
            doc_idx = (last_idx - 1) % N
            assign_map[d] = doctors[doc_idx]
        else:
            # pick first doctor
            assign_map[d] = doctors[0]
    return assign_map

# ---------------------------
# Streamlit App

st.set_page_config(page_title="Doctor Shift Scheduler", layout="wide")

# Initialize session state
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}   # {date: doctor}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)  # {(y,m): set(date objects)}
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []
if 'initial_week' not in st.session_state:
    st.session_state.initial_week = {}

st.title("Doctor Shift Scheduler — Manual initial week & backward-2-day rotation")

# ---------------------------
# Controls

col1, col2, col3 = st.columns([2,1,1])

with col1:
    st.subheader("Month / Initial Week Settings")
    year = st.number_input("Year", min_value=2000, max_value=2100, value=date.today().year)
    month = st.selectbox("Month", list(range(1,13)), index=date.today().month-1)
    start_balance = st.checkbox("Start balance from this month (reset balances)", value=False)

    st.markdown("**Initial Week Assignment**")
    # reference week: Monday of the week containing 1st of month
    ref_date = date(year, month, 1)
    ref_week_start = weekday_monday(ref_date)
    week_dates = [ref_week_start + timedelta(days=i) for i in range(7)]
    week_labels = [calendar.day_name[d.weekday()] + f" ({d.isoformat()})" for d in week_dates]

    # default doctors
    default_docs = [st.session_state.initial_week.get(d, st.session_state.doctors[i % len(st.session_state.doctors)]) for i,d in enumerate(week_dates)]
    initial_week_assignments = {}
    for i, d in enumerate(week_dates):
        doc = st.selectbox(f"{week_labels[i]}", st.session_state.doctors, index=st.session_state.doctors.index(default_docs[i]))
        initial_week_assignments[d] = doc
    st.session_state.initial_week = initial_week_assignments

with col2:
    st.subheader("Actions")
    if st.button("Generate Schedule for selected month"):
        if start_balance:
            st.session_state.prev_assignments = {}
            st.session_state.generated_months = []
        ym = (year, month)
        assign_map = assign_rotation_for_month(year, month, st.session_state.doctors, st.session_state.initial_week)
        st.session_state.prev_assignments.update(assign_map)
        if ym not in st.session_state.generated_months:
            st.session_state.generated_months.append(ym)
        st.success(f"Generated schedule for {calendar.month_name[month]} {year}")

    if st.button("Reset All"):
        st.session_state.prev_assignments = {}
        st.session_state.holidays = defaultdict(set)
        st.session_state.generated_months = []
        st.session_state.initial_week = {}
        st.success("Reset all schedules and holidays")

    if st.button("Save State"):
        data = {
            "prev_assignments": {d.isoformat(): doc for d,doc in st.session_state.prev_assignments.items()},
            "holidays": {f"{y}-{m}": [d.isoformat() for d in s] for (y,m),s in st.session_state.holidays.items()},
            "generated_months": st.session_state.generated_months,
            "initial_week": {d.isoformat(): doc for d,doc in st.session_state.initial_week.items()}
        }
        with open("schedule_state.pkl","wb") as f:
            pickle.dump(data,f)
        st.success("State saved to schedule_state.pkl")

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
            st.session_state.initial_week = {datetime.fromisoformat(k).date():v for k,v in data.get("initial_week",{}).items()}
            st.success("State loaded")
        except Exception as e:
            st.error(f"Failed to load: {e}")

with col3:
    st.subheader("Print")
    if st.button("Print current month to console"):
        if not st.session_state.generated_months:
            st.warning("No month generated yet.")
        else:
            ym = st.session_state.generated_months[-1]
            y,m = ym
            print(f"\nSchedule for {calendar.month_name[m]} {y}:")
            dates = month_dates(y,m)
            for d in dates:
                doc = st.session_state.prev_assignments.get(d,"")
                holiday_flag = "HOLIDAY" if d in st.session_state.holidays.get(ym,set()) else ""
                print(f"{d.isoformat()}\t{calendar.day_name[d.weekday()]}\t{doc}\t{holiday_flag}")
            st.success(f"Printed schedule for {calendar.month_name[m]} {y} to server console")

# ---------------------------
# Month viewer

st.markdown("---")

if st.session_state.generated_months:
    selected_ym = st.selectbox("View generated month", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)

    st.subheader(f"Schedule for {calendar.month_name[m]} {y}")
    # multi-select holidays
    default_hols = list(st.session_state.holidays.get(selected_ym,set()))
    date_strs = [d.isoformat() + " - " + calendar.day_name[d.weekday()] for d in dates]
    date_map = {date_strs[i]: dates[i] for i in range(len(dates))}
    selected_defaults = [s.isoformat() + " - " + calendar.day_name[s.weekday()] for s in default_hols if s in dates]
    hol_selection = st.multiselect("Mark Holidays (do not affect rotation)", date_strs, default=selected_defaults)
    new_hols = set(date_map[s] for s in hol_selection)
    st.session_state.holidays[selected_ym] = new_hols

    # Display schedule table
    rows = []
    for d in dates:
        doc = st.session_state.prev_assignments.get(d,"")
        wd = calendar.day_name[d.weekday()]
        is_hol = d in st.session_state.holidays.get(selected_ym,set())
        rows.append({"Date":d,"Weekday":wd,"Doctor":doc,"Holiday":"Yes" if is_hol else ""})
    df = pd.DataFrame(rows)
    st.dataframe(df.style.applymap(lambda v:'background-color:yellow' if v=="Yes" else '', subset=['Holiday']), height=480)

    # ---------------------------
    # Balance panel
    balance_rows = []
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        hol_nonweek = 0
        for (ymk,holset) in st.session_state.holidays.items():
            for hd in holset:
                if st.session_state.prev_assignments.get(hd)==doc and hd.weekday() not in (5,6):
                    hol_nonweek +=1
        balance_rows.append({"Doctor":doc,"Fridays":fr,"Saturdays":sa,"Sundays":su,"Holidays (non-weekend)":hol_nonweek})
    st.subheader("Balance Panel (cumulative)")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Doctor"))
else:
    st.info("No months generated yet. Use controls above to generate a month.")
