import streamlit as st
import datetime
import calendar
import random
import pandas as pd
from collections import defaultdict
from fpdf import FPDF

# ----------------------------
# CONSTANTS & SETUP
# ----------------------------
DOCTORS = ["Χριστίνα", "Αθηνά", "Μαρία", "Έλια", "Αλέξανδρος", "Εύα", "Έλενα"]

DOCTOR_COLORS = {
    "Έλενα": (255, 182, 193),
    "Εύα": (152, 251, 152),
    "Μαρία": (176, 196, 222),
    "Αθηνά": (255, 250, 205),
    "Αλέξανδρος": (221, 160, 221),
    "Έλια": (175, 238, 238),
    "Χριστίνα": (245, 222, 179),
}

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

GREEK_MONTHS = [
    "", "Ιανουάριος", "Φεβρουάριος", "Μάρτιος", "Απρίλιος", "Μάιος", "Ιούνιος",
    "Ιούλιος", "Αύγουστος", "Σεπτέμβριος", "Οκτώβριος", "Νοέμβριος", "Δεκέμβριος",
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

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
def _week_monday(date):
    return date - datetime.timedelta(days=date.weekday())


class ScheduleIndex:
    """The schedule plus running counters, so every rule check is a dictionary lookup
    instead of a scan over all assigned days (keeps generation linear in the range length)."""

    def __init__(self, holiday_dates, minor_dates=frozenset()):
        self.assign = {}                    # date -> doctor (this is the schedule itself)
        self.holiday_dates = holiday_dates
        self.minor_dates = minor_dates
        self.doc_dates = defaultdict(set)   # doctor -> set of dates
        self.week = {}                      # (doctor, monday) -> shifts
        self.month = {}                     # (doctor, year, month) -> shifts
        self.bucket = {}                    # (doctor, year, month, 'sat'|'sun'|'hol') -> shifts
        self.wd = {}                        # (doctor, weekday) -> shifts in the whole range
        self.minor = {}                     # doctor -> minor holidays in the whole range

    # ---- bookkeeping ----
    def bucket_of(self, d):
        """Any Saturday -> 'sat', any Sunday -> 'sun' (holiday or not),
        holiday on Mon-Fri -> 'hol', otherwise None."""
        if d.weekday() == 5:
            return "sat"
        if d.weekday() == 6:
            return "sun"
        if d in self.holiday_dates:
            return "hol"
        return None

    def _bump(self, store, key, delta):
        store[key] = store.get(key, 0) + delta

    def _apply(self, d, doc, delta):
        self._bump(self.week, (doc, _week_monday(d)), delta)
        self._bump(self.month, (doc, d.year, d.month), delta)
        b = self.bucket_of(d)
        if b:
            self._bump(self.bucket, (doc, d.year, d.month, b), delta)
        self._bump(self.wd, (doc, d.weekday()), delta)
        if d in self.minor_dates:
            self._bump(self.minor, doc, delta)

    def add(self, d, doc):
        if d in self.assign:
            self.remove(d)
        self.assign[d] = doc
        self.doc_dates[doc].add(d)
        self._apply(d, doc, +1)

    def remove(self, d):
        doc = self.assign.pop(d)
        self.doc_dates[doc].discard(d)
        self._apply(d, doc, -1)

    def _ex(self, doc, exclude_date):
        """exclude_date only matters if it is currently assigned to this doctor."""
        if exclude_date is not None and self.assign.get(exclude_date) == doc:
            return exclude_date
        return None

    # ---- queries (same meaning as the old scanning helpers) ----
    def has_nearby_shift(self, doc, date, max_gap=3):
        dates = self.doc_dates.get(doc)
        if not dates:
            return False
        one_day = datetime.timedelta(days=1)
        for k in range(1, max_gap + 1):
            delta = one_day * k
            if (date + delta) in dates or (date - delta) in dates:
                return True
        return False

    def shifts_in_week(self, doc, date, exclude_date=None):
        wk = _week_monday(date)
        n = self.week.get((doc, wk), 0)
        ex = self._ex(doc, exclude_date)
        if ex is not None and _week_monday(ex) == wk:
            n -= 1
        return n

    def total_in_month(self, doc, date, exclude_date=None):
        n = self.month.get((doc, date.year, date.month), 0)
        ex = self._ex(doc, exclude_date)
        if ex is not None and ex.year == date.year and ex.month == date.month:
            n -= 1
        return n

    def _bucket_count(self, doc, date, bucket, exclude_date=None):
        n = self.bucket.get((doc, date.year, date.month, bucket), 0)
        ex = self._ex(doc, exclude_date)
        if (ex is not None and ex.year == date.year and ex.month == date.month
                and self.bucket_of(ex) == bucket):
            n -= 1
        return n

    def special_count(self, doc, date, exclude_date=None):
        b = self.bucket_of(date)
        return 0 if b is None else self._bucket_count(doc, date, b, exclude_date)

    def month_stats(self, doc, date, exclude_date=None):
        total = self.total_in_month(doc, date, exclude_date)
        has_sat = self._bucket_count(doc, date, "sat", exclude_date) > 0
        has_sun = self._bucket_count(doc, date, "sun", exclude_date) > 0
        return total, has_sat, has_sun

    def within_month_cap(self, doc, date, exclude_date=None):
        """Max 5 shifts per month; max 4 if the doctor has both a Saturday and a Sunday that month."""
        total, has_sat, has_sun = self.month_stats(doc, date, exclude_date)
        total += 1
        if date.weekday() == 5:
            has_sat = True
        elif date.weekday() == 6:
            has_sun = True
        return total <= (4 if (has_sat and has_sun) else 5)

    def weekday_total(self, doc, d):
        """Fridays / Saturdays / Sundays (same weekday as d) the doctor has in the whole range."""
        if d.weekday() not in (4, 5, 6):
            return 0
        n = self.wd.get((doc, d.weekday()), 0)
        if self.assign.get(d) == doc:
            n -= 1
        return n

    def minor_total(self, doc, exclude=None):
        n = self.minor.get(doc, 0)
        if exclude in self.minor_dates and self.assign.get(exclude) == doc:
            n -= 1
        return n

    def has_other_weekend_day(self, doc, d):
        if d.weekday() not in (5, 6):
            return False
        other = "sun" if d.weekday() == 5 else "sat"
        return self.bucket.get((doc, d.year, d.month, other), 0) > 0


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
    return holidays


def get_holidays_in_range(start_date, end_date):
    holidays = {}
    for year in range(start_date.year, end_date.year + 1):
        holidays.update(get_cyprus_holidays(year))
    return {d: name for d, name in holidays.items() if start_date <= d <= end_date}


def get_major_holiday_blocks_in_range(start_date, end_date):
    blocks = []
    for year in range(start_date.year, end_date.year + 1):
        easter = orthodox_easter(year)
        s_sat = easter - datetime.timedelta(days=1)
        g_fri = easter - datetime.timedelta(days=2)
        sun_e = easter
        mon_e = easter + datetime.timedelta(days=1)

        year_blocks = [
            ([datetime.date(year, 12, 25)], f"Χριστούγεννα {year}"),
            ([datetime.date(year, 1, 1)], f"Πρωτοχρονιά {year}"),
            ([sun_e], f"Κυριακή του Πάσχα {year}"),
            ([mon_e], f"Δευτέρα του Πάσχα {year}"),
            ([datetime.date(year, 12, 24), s_sat], f"Παραμονή Χριστουγέννων & Μεγάλο Σάββατο {year}"),
            ([datetime.date(year, 12, 26), g_fri], f"2η Χριστουγέννων & Μεγάλη Παρασκευή {year}"),
            ([datetime.date(year, 12, 31)], f"Παραμονή Πρωτοχρονιάς {year}"),
        ]

        for dates, name in year_blocks:
            valid_dates = [d for d in dates if start_date <= d <= end_date]
            if valid_dates:
                blocks.append({"name": name, "dates": valid_dates, "year": year})
    return blocks


def is_valid_assignment(doctor, date, idx, exclude_date=None,
                        strict_monthly=True, max_gap=3, max_special=1):
    if max_gap > 0 and idx.has_nearby_shift(doctor, date, max_gap=max_gap):
        return False
    if idx.shifts_in_week(doctor, date, exclude_date=exclude_date) >= 2:
        return False
    # Max 1 Saturday, 1 Sunday, 1 weekday-holiday per month (holidays on Sat/Sun count as Sat/Sun)
    if idx.special_count(doctor, date, exclude_date=exclude_date) >= max_special:
        return False
    if strict_monthly:
        if not idx.within_month_cap(doctor, date, exclude_date=exclude_date):
            return False
    return True


def find_weekend_violations(schedule):
    """Scan the final schedule for a doctor having 2+ Saturdays or 2+ Sundays in a month."""
    counts = defaultdict(list)
    for d, doc in sorted(schedule.items()):
        if d.weekday() in (5, 6):
            counts[(doc, d.year, d.month, d.weekday())].append(d)
    msgs = []
    for (doc, y, m, wd), dates in counts.items():
        if len(dates) > 1:
            kind = "Σάββατα" if wd == 5 else "Κυριακές"
            days = ", ".join(x.strftime("%d/%m") for x in dates)
            msgs.append(f"{doc}: {len(dates)} {kind} τον {m:02d}/{y} ({days})")
    return msgs


def find_month_cap_violations(schedule):
    stats = defaultdict(lambda: [0, False, False])
    for d, doc in schedule.items():
        st_ = stats[(doc, d.year, d.month)]
        st_[0] += 1
        if d.weekday() == 5:
            st_[1] = True
        elif d.weekday() == 6:
            st_[2] = True
    msgs = []
    for (doc, y, m), (total, sat, sun) in sorted(stats.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        if total > 5:
            msgs.append(f"{doc}: {total} εφημερίες τον {m:02d}/{y} (μέγιστο 5)")
        elif sat and sun and total > 4:
            msgs.append(f"{doc}: Σάββατο & Κυριακή με {total} εφημερίες τον {m:02d}/{y} (μέγιστο 4)")
    return msgs


def find_gap_violations(schedule, min_free_days=2):
    msgs = []
    by_doc = defaultdict(list)
    for d, doc in schedule.items():
        by_doc[doc].append(d)
    for doc, ds in by_doc.items():
        ds.sort()
        for a, b in zip(ds, ds[1:]):
            if (b - a).days - 1 < min_free_days:
                msgs.append(f"{doc}: εφημερίες {a.strftime('%d/%m/%Y')} και {b.strftime('%d/%m/%Y')} "
                            f"με λιγότερες από {min_free_days} ελεύθερες μέρες ανάμεσα")
    return msgs


def find_all_violations(schedule):
    return (find_weekend_violations(schedule) + find_month_cap_violations(schedule)
            + find_gap_violations(schedule))


# ----------------------------
# SCHEDULING LOGIC
# ----------------------------
def _generate_once(start_date, end_date, initial_week, manual_assignments=None, order=None):
    order = order or list(DOCTORS)
    manual_assignments = manual_assignments or {}
    warnings = []

    total_days = (end_date - start_date).days + 1
    holiday_names = get_holidays_in_range(start_date, end_date)
    holiday_dates = set(holiday_names.keys())
    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    minor_dates = {d for d in holiday_dates if d not in all_major_dates}

    idx = ScheduleIndex(holiday_dates, minor_dates)
    schedule = idx.assign

    # Manual assignments go in first
    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            idx.add(d, doc)

    # STEP 1: major holiday packages (1 package per doctor per year)
    doctor_yearly_major_count = {
        doc: {y: 0 for y in range(start_date.year - 1, end_date.year + 2)} for doc in order
    }

    for block in major_blocks:
        block_dates = block["dates"]
        if any(bd in schedule for bd in block_dates):
            continue

        block_year = block["year"]
        is_jan_1 = (len(block_dates) == 1 and block_dates[0].month == 1 and block_dates[0].day == 1)
        target_year = block_year if not is_jan_1 else block_year - 1

        eligible = [doc for doc in order if doctor_yearly_major_count[doc][target_year] == 0]
        others = [doc for doc in order if doc not in eligible]
        by_load = lambda d: sum(doctor_yearly_major_count[d].values())
        candidates = sorted(eligible, key=by_load) + sorted(others, key=by_load)

        best_doc = None
        for doc in candidates:
            if all(is_valid_assignment(doc, bd, idx, exclude_date=bd,
                                       strict_monthly=True, max_gap=2) for bd in block_dates):
                best_doc = doc
                break

        if not best_doc:
            best_doc = min(candidates, key=lambda doc: (
                sum(idx.has_nearby_shift(doc, bd, max_gap=2) for bd in block_dates),
                sum(idx.special_count(doc, bd) for bd in block_dates)))
            warnings.append(f"{block['name']}: ανατέθηκε χωρίς πλήρη τήρηση κανόνων ({best_doc})")

        for bd in block_dates:
            idx.add(bd, best_doc)
        doctor_yearly_major_count[best_doc][target_year] += 1

    # STEP 2: remaining special days BEFORE weekdays.
    # Order: minor holidays first (shared equally), then Sat/Sun, then Fridays.
    all_days = [start_date + datetime.timedelta(days=i) for i in range(total_days)]

    special_dates = [
        d for d in all_days
        if d not in schedule and (d.weekday() in (4, 5, 6) or d in holiday_dates)
    ]
    special_dates.sort(key=lambda d: (0 if d in minor_dates else 1 if d.weekday() in (5, 6) else 2, d))

    for d in special_dates:
        chosen = None
        for max_special, gap in [(1, 3), (1, 2), (2, 3), (2, 2)]:
            valid = [doc for doc in order if is_valid_assignment(
                doc, d, idx, exclude_date=d,
                strict_monthly=True, max_gap=gap, max_special=max_special)]
            if valid:
                chosen = min(valid, key=lambda doc: (
                    idx.minor_total(doc, d) if d in minor_dates else 0,
                    idx.weekday_total(doc, d),
                    idx.special_count(doc, d, exclude_date=d),
                    idx.has_other_weekend_day(doc, d),
                    idx.total_in_month(doc, d, exclude_date=d)))
                if idx.special_count(chosen, d, exclude_date=d) >= 1:
                    warnings.append(
                        f"{d.strftime('%d/%m/%Y')}: ο/η {chosen} έχει 2η ίδια ημέρα "
                        f"(Σάββατο/Κυριακή/αργία) τον μήνα")
                break
        if chosen is None:
            chosen = min(order, key=lambda doc: (
                idx.has_nearby_shift(doc, d, max_gap=2),
                not idx.within_month_cap(doc, d, exclude_date=d),
                idx.special_count(doc, d, exclude_date=d),
                idx.total_in_month(doc, d, exclude_date=d)))
            warnings.append(f"{d.strftime('%d/%m/%Y')}: καμία έγκυρη επιλογή, ανατέθηκε {chosen}")
        idx.add(d, chosen)

    # STEP 3: weekdays (Mon-Thu) from the initial rota, respecting the monthly cap
    start_monday = _week_monday(start_date)
    for current_date in all_days:
        if current_date in schedule:
            continue
        week_num = (_week_monday(current_date) - start_monday).days // 7
        doc_index = (current_date.weekday() + week_num * 2) % len(initial_week)
        rota_doc = initial_week[doc_index]

        chosen = None
        for gap in (2,):
            valid = [doc for doc in order if is_valid_assignment(
                doc, current_date, idx, exclude_date=current_date,
                strict_monthly=True, max_gap=gap)]
            if not valid:
                continue
            # Remaining capacity this month (limit is 4 with Sat+Sun, else 5); weekend
            # assignments are already final here, so the limits are known.
            rem = {}
            for doc in valid:
                tot, hs, hu = idx.month_stats(doc, current_date)
                rem[doc] = (4 if (hs and hu) else 5) - tot
            best = max(rem.values())
            if rota_doc in valid and rem[rota_doc] >= best - 1:
                chosen = rota_doc
            else:
                chosen = min(valid, key=lambda doc: (-rem[doc], idx.total_in_month(doc, current_date)))
            break
        if chosen is None:
            chosen = min(order, key=lambda doc: (
                idx.has_nearby_shift(doc, current_date, max_gap=2),
                not idx.within_month_cap(doc, current_date, exclude_date=current_date),
                idx.total_in_month(doc, current_date)))
            warnings.append(f"{current_date.strftime('%d/%m/%Y')}: καμία έγκυρη επιλογή, ανατέθηκε {chosen}")
        idx.add(current_date, chosen)

    # Re-apply manual assignments so they always win
    for d, doc in manual_assignments.items():
        if start_date <= d <= end_date:
            schedule[d] = doc

    if minor_dates:
        mc = {doc: sum(1 for dd, dc in schedule.items() if dc == doc and dd in minor_dates)
              for doc in order}
        if max(mc.values()) - min(mc.values()) > 1:
            warnings.append("Οι μικρές αργίες δεν μοιράστηκαν ισόποσα: " +
                            ", ".join(f"{doc} {n}" for doc, n in mc.items()))

    for wd, label in [(4, "Παρασκευές"), (5, "Σάββατα"), (6, "Κυριακές")]:
        wc = {doc: sum(1 for dd, dc in schedule.items() if dc == doc and dd.weekday() == wd)
              for doc in order}
        if max(wc.values()) - min(wc.values()) > 1:
            warnings.append(f"Οι {label} δεν μοιράστηκαν ισόποσα: " +
                            ", ".join(f"{doc} {n}" for doc, n in wc.items()))

    warnings += find_all_violations(schedule)
    return schedule, holiday_names, warnings


def generate_full_schedule(start_date, end_date, initial_week, manual_assignments=None, max_attempts=40):
    """Runs the generator several times with different tie-break orders and keeps the
    attempt with the fewest rule violations (tight months can defeat a single greedy pass)."""
    best = None
    for attempt in range(max_attempts):
        order = list(DOCTORS)
        if attempt:
            random.Random(attempt).shuffle(order)
        result = _generate_once(start_date, end_date, initial_week, manual_assignments, order)
        warns = result[2]
        score = (sum(1 for w in warns if not w.startswith("Οι ")), len(warns))
        if best is None or score < best[0]:
            best = (score, result)
        if score[0] == 0 and (score[1] == 0 or attempt >= 10):
            break
    return best[1]


# ----------------------------
# BALANCE & REPORTING
# ----------------------------
def compute_major_holidays_summary(schedule, start_date, end_date):
    blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    summary = {doc: {"Count": 0, "Details": []} for doc in DOCTORS}

    for block in blocks:
        primary_date = block["dates"][0]
        doc = schedule.get(primary_date, "-")
        if doc in summary:
            summary[doc]["Count"] += 1
            dates_str = ", ".join(d.strftime('%d/%m/%Y') for d in block["dates"])
            summary[doc]["Details"].append(f"• {block['name']} ({dates_str})")

    data = []
    for doc in DOCTORS:
        data.append({
            "Ακτινολόγος": doc,
            "Σύνολο Πακέτων": summary[doc]["Count"],
            "Ανατεθειμένα Πακέτα": "\n".join(summary[doc]["Details"]) if summary[doc]["Details"] else "Κανένα",
        })
    return pd.DataFrame(data)


def compute_regular_holidays_summary(schedule, regular_holidays):
    summary = {doc: {"Count": 0, "Details": []} for doc in DOCTORS}
    for d in sorted(regular_holidays.keys()):
        doc = schedule.get(d, "-")
        if doc in summary:
            summary[doc]["Count"] += 1
            summary[doc]["Details"].append(f"{d.strftime('%d/%m/%Y')} ({regular_holidays[d]})")
    data = []
    for doc in DOCTORS:
        data.append({
            "Ακτινολόγος": doc,
            "Σύνολο": summary[doc]["Count"],
            "Ημερομηνίες & Εορτές": ", ".join(summary[doc]["Details"]) if summary[doc]["Details"] else "Καμία",
        })
    return pd.DataFrame(data)


def compute_balance(schedule, start_date, end_date, holiday_names):
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in DOCTORS}
    for date, doc in schedule.items():
        if doc in counts:
            counts[doc][WEEKDAY_LABELS[date.weekday()]] += 1

    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]

    major_df = compute_major_holidays_summary(schedule, start_date, end_date)
    major_dict = dict(zip(major_df["Ακτινολόγος"], major_df["Σύνολο Πακέτων"]))

    major_blocks = get_major_holiday_blocks_in_range(start_date, end_date)
    all_major_dates = {d for block in major_blocks for d in block["dates"]}
    regular_hols = {d: n for d, n in holiday_names.items() if d not in all_major_dates}
    regular_df = compute_regular_holidays_summary(schedule, regular_hols)
    regular_dict = dict(zip(regular_df["Ακτινολόγος"], regular_df["Σύνολο"]))

    df["Αργίες"] = df["Doctor"].apply(lambda doc: major_dict.get(doc, 0) + regular_dict.get(doc, 0))
    df["Total"] = df["Weekdays"] + df["Fri"] + df["Sat"] + df["Sun"]
    return df[["Doctor", "Weekdays", "Fri", "Sat", "Sun", "Αργίες", "Total"]]


# ----------------------------
# PDF HELPERS (fpdf2)
# Needs DejaVuSans.ttf and DejaVuSans-Bold.ttf next to this script.
# ----------------------------
def create_balance_pdf(df, start_date, end_date):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Doctor Balance Summary", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"Period: {start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
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
    return bytes(pdf.output())


def display_calendar(schedule, holiday_names):
    manual_assignments = st.session_state.get("manual_assignments", {})
    last_month = None
    for date in sorted(schedule.keys()):
        month_key = (date.year, date.month)
        if month_key != last_month:
            st.markdown(f"## {GREEK_MONTHS[date.month]} {date.year}")
            last_month = month_key
            headers = st.columns(7)
            for i, d in enumerate(WEEKDAY_LABELS):
                headers[i].markdown(f"**{d}**")
            cal = calendar.Calendar(firstweekday=0)
            for week in cal.monthdatescalendar(date.year, date.month):
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day.month == date.month:
                        doc = schedule.get(day, "")
                        is_holiday = day in holiday_names
                        icon = " ✏️" if day in manual_assignments else ""
                        holiday_tag = (f"<br><span style='font-size:10px'>🎉 {holiday_names[day]}</span>"
                                       if is_holiday else "")
                        color = '#%02x%02x%02x' % DOCTOR_COLORS.get(doc, (220, 220, 220))
                        border = "border:2px solid #d9534f;" if is_holiday else ""
                        cols[i].markdown(
                            f"<div style='background-color:{color}; {border} padding:6px; "
                            f"border-radius:4px; text-align:center'>"
                            f"<b>{day.day}</b><br>{doc}{icon}{holiday_tag}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        cols[i].markdown("")


# ----------------------------
# STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="📅 Πρόγραμμα Εφημεριών", layout="wide")
st.title("📅 Πρόγραμμα Εφημεριών Ακτινολόγων")
st.markdown("<span style='font-size:14px; color:gray;'>© Γιώργος Μενοίκου, PhD</span>",
            unsafe_allow_html=True)

for key, default in [
    ("manual_assignments", {}), ("schedule", None), ("holiday_names", {}),
    ("balance", None), ("initial_week", None), ("warnings", []),
    ("start_date", datetime.date.today()),
]:
    if key not in st.session_state:
        st.session_state[key] = default

left_col, right_col = st.columns([0.35, 0.65])

with left_col:
    st.subheader("📊 Κατάσταση Εφημεριών Εύρους")
    if st.session_state.start_date and st.session_state.schedule:
        manual_date = st.date_input(
            "Επιλέξετε ημερομηνία για αλλαγή",
            min_value=min(st.session_state.schedule.keys()),
            max_value=max(st.session_state.schedule.keys()),
        )
        manual_doctor = st.selectbox("Επιλογή Ακτινολόγου", DOCTORS)
        if st.button("✅ Επικύρωση"):
            st.session_state.manual_assignments[manual_date] = manual_doctor
            st.session_state.schedule[manual_date] = manual_doctor
            end_d = max(st.session_state.schedule.keys())
            st.session_state.balance = compute_balance(
                st.session_state.schedule, st.session_state.start_date, end_d,
                st.session_state.holiday_names)
            st.session_state.warnings = find_all_violations(st.session_state.schedule)
            st.success(f"Ο/Η {manual_doctor} ανατέθηκε στις {manual_date.strftime('%d/%m/%Y')}")
            st.rerun()

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        st.dataframe(st.session_state.balance, use_container_width=True, height=260)

        if st.session_state.schedule:
            end_d = max(st.session_state.schedule.keys())
            st.markdown("### 🎄🐣 Κατάσταση 7 Πακέτων Μεγάλων Εορτών")
            major_df = compute_major_holidays_summary(
                st.session_state.schedule, st.session_state.start_date, end_d)
            st.dataframe(major_df, use_container_width=True, height=240)

        if st.session_state.holiday_names:
            major_blocks = get_major_holiday_blocks_in_range(st.session_state.start_date, end_d)
            all_major_dates = {d for block in major_blocks for d in block["dates"]}
            regular_hols = {d: n for d, n in st.session_state.holiday_names.items()
                            if d not in all_major_dates}
            if regular_hols:
                with st.expander("🎈 Ανάλυση Μικρών Αργιών"):
                    regular_df = compute_regular_holidays_summary(st.session_state.schedule, regular_hols)
                    st.dataframe(regular_df, use_container_width=True)

        try:
            pdf_bytes = create_balance_pdf(st.session_state.balance, st.session_state.start_date, end_d)
            st.download_button("📄 Κατέβασε κατάσταση σε PDF", pdf_bytes,
                               file_name="balance_summary.pdf", mime="application/pdf")
        except Exception as e:
            st.error(f"Σφάλμα δημιουργίας PDF (έλεγξε ότι υπάρχουν τα DejaVuSans.ttf και "
                     f"DejaVuSans-Bold.ttf): {e}")

with right_col:
    selected_date = st.date_input("Ημερομηνία έναρξης:", datetime.date.today())
    week_dates = [selected_date - datetime.timedelta(days=selected_date.weekday())
                  + datetime.timedelta(days=i) for i in range(7)]

    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            initial_week[d] = st.selectbox(d.strftime("%a %d/%m"), DOCTORS, index=i % 7, key=f"doc_{d}")

    if st.button("💾 Αποθήκευση Αρχικής Ρότας"):
        st.session_state.initial_week = [initial_week[d] for d in sorted(initial_week)]
        st.session_state.start_date = week_dates[0]
        st.rerun()

    if st.session_state.initial_week:
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start date", st.session_state.start_date)
        with c2:
            end_date = st.date_input("End date", start_date + datetime.timedelta(days=30))

        if st.button("🗓️ Δημιουργία Προγράμματος"):
            sch, hols, warns = generate_full_schedule(
                start_date, end_date, st.session_state.initial_week,
                manual_assignments=st.session_state.manual_assignments,
            )
            st.session_state.schedule = sch
            st.session_state.holiday_names = hols
            st.session_state.warnings = warns
            st.session_state.balance = compute_balance(sch, start_date, end_date, hols)
            st.rerun()

    for w in st.session_state.get("warnings", []):
        st.warning(w)

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule, st.session_state.holiday_names)
