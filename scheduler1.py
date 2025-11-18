# doctor_shift_scheduler_streamlit.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from collections import defaultdict, deque
import pickle

# ---------------------------
# Helper functions

def month_dates(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    return [first + timedelta(days=i) for i in range(last_day)]

def categorize_dates(dates):
    weekdays, fridays, saturdays, sundays = [], [], [], []
    for d in dates:
        wd = d.weekday()
        if wd == 4:
            fridays.append(d)
        elif wd == 5:
            saturdays.append(d)
        elif wd == 6:
            sundays.append(d)
        else:
            weekdays.append(d)
    return weekdays, fridays, saturdays, sundays

# ---------------------------
# Scheduler logic

def assign_shifts(dates, doctors, prev_assignments=None, weekend_history=None, friday_history=None, holidays=set()):
    if prev_assignments is None:
        prev_assignments = {}
    if weekend_history is None:
        weekend_history = defaultdict(int)
    if friday_history is None:
        friday_history = defaultdict(int)

    weekdays, fridays, saturdays, sundays = categorize_dates(dates)
    assign_map = {}

    last_weekend_doc = {}

    def can_assign(doc, d, is_weekend=False):
        if d in holidays:
            # holidays are still working shifts, so apply rules
            pass
        # strict 2-day gap
        for delta in range(1,3):
            if assign_map.get(d - timedelta(days=delta)) == doc:
                return False
            if assign_map.get(d + timedelta(days=delta)) == doc:
                return False
        if is_weekend:
            prev_weekend = d - timedelta(days=7)
            if last_weekend_doc.get(doc) and last_weekend_doc[doc] >= prev_weekend:
                return False
        return True

    # --- Step1: Weekends
    weekend_days = sorted(saturdays + sundays)
    total_weekends = len(weekend_days)
    base_count = total_weekends // len(doctors)
    extras = total_weekends - base_count*len(doctors)
    weekend_assign_counts = defaultdict(int)

    for d in weekend_days:
        sorted_docs = sorted(doctors, key=lambda doc: (weekend_history[doc], weekend_assign_counts[doc]))
        assigned = False
        for doc in sorted_docs:
            max_shifts = base_count + (1 if extras>0 else 0)
            if weekend_assign_counts[doc] >= max_shifts:
                continue
            if not can_assign(doc,d,is_weekend=True):
                continue
            assign_map[d] = doc
            weekend_assign_counts[doc] +=1
            weekend_history[doc] +=1
            last_weekend_doc[doc] = d
            if extras>0 and weekend_assign_counts[doc] > base_count:
                extras -=1
            assigned = True
            break
        if not assigned:
            doc = sorted_docs[0]
            assign_map[d] = doc
            weekend_assign_counts[doc] +=1
            weekend_history[doc] +=1
            last_weekend_doc[doc] = d

    # --- Step2: Fridays
    total_fridays = len(fridays)
    base_count = total_fridays // len(doctors)
    extras = total_fridays - base_count*len(doctors)
    friday_assign_counts = defaultdict(int)

    for d in fridays:
        sorted_docs = sorted(doctors, key=lambda doc: (weekend_assign_counts[doc], friday_history[doc]))
        assigned = False
        for doc in sorted_docs:
            max_shifts = base_count + (1 if extras>0 else 0)
            if friday_assign_counts[doc] >= max_shifts:
                continue
            if not can_assign(doc,d):
                continue
            assign_map[d] = doc
            friday_assign_counts[doc] +=1
            friday_history[doc] +=1
            if extras>0 and friday_assign_counts[doc] > base_count:
                extras -=1
            assigned = True
            break
        if not assigned:
            doc = sorted_docs[0]
            assign_map[d] = doc
            friday_assign_counts[doc] +=1
            friday_history[doc] +=1

    # --- Step3: Weekdays
    weekday_cycle = deque(doctors)
    for d in weekdays:
        for _ in range(len(weekday_cycle)):
            doc = weekday_cycle[0]
            if can_assign(doc,d):
                assign_map[d] = doc
                weekday_cycle.rotate(-1)
                break
            weekday_cycle.rotate(-1)
        else:
            assign_map[d] = weekday_cycle[0]
            weekday_cycle.rotate(-1)

    return assign_map

# ---------------------------
# Streamlit App

st.set_page_config(page_title="Doctor Shift Scheduler", layout="wide")

if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}
if 'weekend_history' not in st.session_state:
    st.session_state.weekend_history = defaultdict(int)
if 'friday_history' not in st.session_state:
    st.session_state.friday_history = defaultdict(int)
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []

st.title("Doctor Shift Scheduler")

# Controls
col1, col2 = st.columns(2)
with col1:
    year = st.number_input("Year", min_value=2000, max_value=2100, value=date.today().year)
    month = st.selectbox("Month", list(range(1,13)), index=date.today().month-1)
    start_balance = st.checkbox("Start balance from this month")

with col2:
    st.write("### Actions")
    if st.button("Generate Schedule"):
        if start_balance:
            st.session_state.weekend_history = defaultdict(int)
            st.session_state.friday_history = defaultdict(int)
            st.session_state.prev_assignments = {}
        ym = (year, month)
        dates = month_dates(year, month)
        assign_map = assign_shifts(dates, st.session_state.doctors,
                                   prev_assignments=st.session_state.prev_assignments,
                                   weekend_history=st.session_state.weekend_history,
                                   friday_history=st.session_state.friday_history,
                                   holidays=st.session_state.holidays.get(ym,set()))
        st.session_state.prev_assignments.update({d: assign_map[d] for d in dates})
        if ym not in st.session_state.generated_months:
            st.session_state.generated_months.append(ym)

    if st.button("Reset All"):
        st.session_state.prev_assignments.clear()
        st.session_state.weekend_history.clear()
        st.session_state.friday_history.clear()
        st.session_state.generated_months.clear()
        st.session_state.holidays.clear()

    if st.button("Save State"):
        with open("schedule_state.pkl","wb") as f:
            pickle.dump(dict(st.session_state), f)
        st.success("Schedule state saved.")

    if st.button("Load State"):
        try:
            with open("schedule_state.pkl","rb") as f:
                data = pickle.load(f)
            for k,v in data.items():
                st.session_state[k] = v
            st.success("State loaded.")
        except Exception as e:
            st.error(f"Failed to load: {e}")

# Select which month to view
if st.session_state.generated_months:
    selected_ym = st.selectbox("View Month", st.session_state.generated_months)
    year, month = selected_ym
    dates = month_dates(year, month)
    df = pd.DataFrame({
        "Date": [d for d in dates],
        "Weekday": [calendar.day_name[d.weekday()] for d in dates],
        "Doctor": [st.session_state.prev_assignments[d] for d in dates]
    })

    # Multi-select holidays
    holiday_options = [d for d in dates]
    holiday_selection = st.multiselect("Mark Holidays", holiday_options,
                                       default=list(st.session_state.holidays.get(selected_ym,set())))
    st.session_state.holidays[selected_ym] = set(holiday_selection)

    # Recalculate after holidays
    assign_map = assign_shifts(dates, st.session_state.doctors,
                               prev_assignments={k:v for k,v in st.session_state.prev_assignments.items() if k<dates[0]},
                               weekend_history=st.session_state.weekend_history,
                               friday_history=st.session_state.friday_history,
                               holidays=st.session_state.holidays[selected_ym])
    st.session_state.prev_assignments.update({d: assign_map[d] for d in dates})

    # Display schedule table
    df['DayType'] = df['Weekday'].apply(lambda x: "Friday" if x=="Friday" else ("Saturday" if x=="Saturday" else ("Sunday" if x=="Sunday" else "Weekday")))
    df['Holiday'] = df['Date'].apply(lambda d: "Yes" if d in st.session_state.holidays[selected_ym] else "")
    st.subheader(f"Schedule for {calendar.month_name[month]} {year}")
    st.dataframe(df.style.applymap(lambda x: 'background-color: yellow' if x=="Yes" else '', subset=['Holiday']),height=500)

    # Show balances
    balance_data = []
    for doc in st.session_state.doctors:
        fridays = sum(1 for d in st.session_state.prev_assignments if st.session_state.prev_assignments[d]==doc and d.weekday()==4)
        saturdays = sum(1 for d in st.session_state.prev_assignments if st.session_state.prev_assignments[d]==doc and d.weekday()==5)
        sundays = sum(1 for d in st.session_state.prev_assignments if st.session_state.prev_assignments[d]==doc and d.weekday()==6)
        balance_data.append({"Doctor":doc,"Fridays":fridays,"Saturdays":saturdays,"Sundays":sundays})
    st.subheader("Balance Panel")
    st.dataframe(pd.DataFrame(balance_data))

# Optional print to console
if st.button("Print Schedule"):
    if st.session_state.generated_months:
        selected_ym = st.session_state.generated_months[-1]
        year, month = selected_ym
        dates = month_dates(year, month)
        print(f"\nSchedule for {calendar.month_name[month]} {year}")
        for d in dates:
            doc = st.session_state.prev_assignments[d]
            holiday_flag = "Holiday" if d in st.session_state.holidays[selected_ym] else ""
            print(f"{d}: {doc} {holiday_flag}")
