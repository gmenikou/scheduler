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

def weekday_monday(d: date):
    """Return Monday of the week containing d."""
    return d - timedelta(days=d.weekday())

def weeks_in_month(year, month):
    """Return list of Monday dates (week starts) that intersect the month."""
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    # Start from the Monday of the week that contains the first day
    cur = weekday_monday(first)
    mondays = []
    while cur <= last:
        mondays.append(cur)
        cur += timedelta(days=7)
    return mondays

# ---------------------------
# New rotation assignment:
# - One shift per week
# - Each week i (relative to reference) gets doctor index (ref_doc_index + i) % N
# - Weekday for week i is (ref_weekday - 2*i) % 7
# - If the weekday date for that week falls inside the month, it's included; otherwise it's skipped

def assign_rotation_for_month(year, month, doctors, ref_date, ref_doc, continue_across_months=True):
    """
    Assign shifts in the month using the backwards-2-days-per-week weekday rotation.
    ref_date: date object that defines reference week and reference weekday where ref_doc works.
    ref_doc: doctor name who works on ref_date.
    continue_across_months: if True, we compute week offset from reference date (continuous rotation).
                           if False, treat the first monday of the month as week 0 with ref settings.
    Returns dict {date: doctor}
    """
    mondays = weeks_in_month(year, month)
    if not mondays:
        return {}

    # find reference doctor's index
    N = len(doctors)
    try:
        ref_index = doctors.index(ref_doc)
    except ValueError:
        ref_index = 0

    ref_monday = weekday_monday(ref_date)
    assign_map = {}

    for week_idx, week_monday in enumerate(mondays):
        # compute number of weeks between this week's monday and reference monday
        if continue_across_months:
            weeks_between = (week_monday - ref_monday).days // 7
        else:
            # if not continuing, treat the first monday in this month as weeks_between=0
            first_monday = mondays[0]
            weeks_between = (week_monday - first_monday).days // 7

        # doctor rotating forward per week
        doc_idx = (ref_index + weeks_between) % N
        doc = doctors[doc_idx]

        # weekday (0=Mon ... 6=Sun): moves backward 2 days per week from ref_date.weekday()
        shift_weekday = (ref_date.weekday() - 2 * weeks_between) % 7

        # get date in this week that matches shift_weekday
        shift_date = week_monday + timedelta(days=shift_weekday)
        # include only if shift_date lies within the target month
        if shift_date.year == year and shift_date.month == month:
            assign_map[shift_date] = doc

    return assign_map

# ---------------------------
# Streamlit App

st.set_page_config(page_title="Doctor Shift Scheduler", layout="wide")

# initialize session state
if 'prev_assignments' not in st.session_state:
    st.session_state.prev_assignments = {}   # {date: doctor}
if 'holidays' not in st.session_state:
    st.session_state.holidays = defaultdict(set)  # {(y,m): set(date objects)}
if 'doctors' not in st.session_state:
    st.session_state.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
if 'generated_months' not in st.session_state:
    st.session_state.generated_months = []  # list of (year,month) tuples, in generation order
if 'ref_date' not in st.session_state:
    # default reference: today (user said today is Tuesday in earlier message — don't enforce)
    st.session_state.ref_date = date.today()
if 'ref_doc' not in st.session_state:
    st.session_state.ref_doc = st.session_state.doctors[0]
if 'continue_across_months' not in st.session_state:
    st.session_state.continue_across_months = True

st.title("Doctor Shift Scheduler — Backwards 2-day weekly rotation")

# Controls layout
left, mid, right = st.columns([2,1,1])

with left:
    st.subheader("Month / Reference settings")
    year = st.number_input("Year", min_value=2000, max_value=2100, value=date.today().year)
    month = st.selectbox("Month", list(range(1,13)), index=date.today().month-1)
    start_balance = st.checkbox("Start balance from this month (reset balances)", value=False)
    st.markdown("**Reference (rotation baseline)**")
    ref_date = st.date_input("Reference date (week & weekday baseline)", value=st.session_state.ref_date)
    ref_doc = st.selectbox("Reference doctor (works on reference date)", st.session_state.doctors, index=st.session_state.doctors.index(st.session_state.ref_doc))
    continue_across = st.checkbox("Continue rotation across months (continuous)", value=st.session_state.continue_across_months)

with mid:
    st.subheader("Actions")
    if st.button("Generate Schedule for selected month"):
        # update session baseline
        st.session_state.ref_date = ref_date
        st.session_state.ref_doc = ref_doc
        st.session_state.continue_across_months = continue_across

        if start_balance:
            # reset balances = clear prev_assignments
            st.session_state.prev_assignments = {}
            st.session_state.generated_months = []
        ym = (year, month)
        # compute assignments for the month
        assign_map = assign_rotation_for_month(year, month, st.session_state.doctors,
                                              st.session_state.ref_date, st.session_state.ref_doc,
                                              continue_across_months=st.session_state.continue_across_months)
        # update prev_assignments (cumulative)
        st.session_state.prev_assignments.update(assign_map)
        if ym not in st.session_state.generated_months:
            st.session_state.generated_months.append(ym)
        st.success(f"Generated schedule for {calendar.month_name[month]} {year}")

    if st.button("Reset All"):
        st.session_state.prev_assignments = {}
        st.session_state.holidays = defaultdict(set)
        st.session_state.generated_months = []
        st.success("Reset all schedules and holidays")

    if st.button("Save State"):
        data = {
            "prev_assignments": {d.isoformat(): doc for d,doc in st.session_state.prev_assignments.items()},
            "holidays": {f"{y}-{m}": [d.isoformat() for d in s] for (y,m),s in st.session_state.holidays.items()},
            "generated_months": st.session_state.generated_months,
            "ref_date": st.session_state.ref_date.isoformat(),
            "ref_doc": st.session_state.ref_doc,
            "continue_across": st.session_state.continue_across_months
        }
        with open("schedule_state.pkl","wb") as f:
            pickle.dump(data, f)
        st.success("State saved to schedule_state.pkl")

    if st.button("Load State"):
        try:
            with open("schedule_state.pkl","rb") as f:
                data = pickle.load(f)
            # restore
            st.session_state.prev_assignments = {datetime.fromisoformat(k).date(): v for k,v in data["prev_assignments"].items()}
            st.session_state.holidays = defaultdict(set)
            for key, lst in data.get("holidays", {}).items():
                y,m = map(int, key.split("-"))
                st.session_state.holidays[(y,m)] = set(datetime.fromisoformat(d).date() for d in lst)
            st.session_state.generated_months = data.get("generated_months", [])
            st.session_state.ref_date = datetime.fromisoformat(data.get("ref_date")).date()
            st.session_state.ref_doc = data.get("ref_doc", st.session_state.doctors[0])
            st.session_state.continue_across_months = data.get("continue_across", True)
            st.success("State loaded")
        except Exception as e:
            st.error(f"Failed to load: {e}")

with right:
    st.subheader("Printing")
    if st.button("Print current month to console"):
        if not st.session_state.generated_months:
            st.warning("No month generated yet.")
        else:
            ym = st.session_state.generated_months[-1]
            y,m = ym
            st.write(f"Printed schedule for {calendar.month_name[m]} {y} to server console")
            dates = month_dates(y,m)
            print(f"\nSchedule for {calendar.month_name[m]} {y}:")
            for d in dates:
                doc = st.session_state.prev_assignments.get(d, "")
                holiday_flag = "HOLIDAY" if d in st.session_state.holidays.get(ym,set()) else ""
                print(f"{d.isoformat()}\t{calendar.day_name[d.weekday()]}\t{doc}\t{holiday_flag}")

# ---------------------------
# Month viewer & holiday toggling / balances

st.markdown("---")

if st.session_state.generated_months:
    selected_ym = st.selectbox("View generated month", st.session_state.generated_months, index=len(st.session_state.generated_months)-1)
    y,m = selected_ym
    dates = month_dates(y,m)

    # Show and edit holidays for this month (batch selection)
    st.subheader(f"Schedule for {calendar.month_name[m]} {y}")
    default_hols = list(st.session_state.holidays.get(selected_ym, []))
    # present date strings to multiselect for readability
    date_strs = [d.isoformat() + " - " + calendar.day_name[d.weekday()] for d in dates]
    date_map = {date_strs[i]: dates[i] for i in range(len(dates))}
    selected_defaults = [s.isoformat() + " - " + calendar.day_name[s.weekday()] for s in default_hols if s in dates]
    hol_selection = st.multiselect("Toggle holidays (these DO NOT change rotation — chosen shift stays)", date_strs, default=selected_defaults)
    # update holidays set
    new_hols = set(date_map[s] for s in hol_selection)
    st.session_state.holidays[selected_ym] = new_hols

    # Recompute assignments for the viewed month using rotation rules (holidays don't change rotation)
    # Note: rotation is independent, holidays only flagged for balance column
    assign_map = assign_rotation_for_month(y, m, st.session_state.doctors, st.session_state.ref_date, st.session_state.ref_doc, continue_across_months=st.session_state.continue_across_months)
    # persist into prev_assignments (overwriting that month's dates)
    st.session_state.prev_assignments.update(assign_map)

    # Prepare dataframe for display
    rows = []
    for d in dates:
        doc = st.session_state.prev_assignments.get(d, "")
        wd = calendar.day_name[d.weekday()]
        is_hol = d in st.session_state.holidays.get(selected_ym, set())
        rows.append({
            "Date": d,
            "Weekday": wd,
            "Doctor": doc,
            "Holiday": "Yes" if is_hol else ""
        })
    df = pd.DataFrame(rows)

    # display styled table (highlight holiday rows)
    def highlight_holiday(val):
        return 'background-color: yellow' if val == "Yes" else ''
    st.dataframe(df.style.applymap(lambda v: 'background-color: yellow' if v=="Yes" else '', subset=['Holiday']), height=480)

    # ---------------------------
    # Balance panel (Fridays, Saturdays, Sundays, Holidays (non-weekend))
    balance_rows = []
    for doc in st.session_state.doctors:
        fr = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==4)
        sa = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==5)
        su = sum(1 for d,dd in st.session_state.prev_assignments.items() if dd==doc and d.weekday()==6)
        # holiday (non-weekend) count:
        hol_non_weekday = 0
        for (ym_k, holset) in st.session_state.holidays.items():
            for hd in holset:
                # only count if assignment exists for that date and doctor and it's not Sat/Sun
                if st.session_state.prev_assignments.get(hd) == doc and hd.weekday() not in (5,6):
                    hol_non_weekday += 1
        balance_rows.append({
            "Doctor": doc,
            "Fridays": fr,
            "Saturdays": sa,
            "Sundays": su,
            "Holidays (non-weekend)": hol_non_weekday
        })
    st.subheader("Balance Panel (cumulative)")
    st.dataframe(pd.DataFrame(balance_rows).set_index("Doctor"))

else:
    st.info("No months generated yet. Use the controls on the left to generate a month.")

# ---------------------------
# End of file
