import os
import math
import random
import datetime
import calendar

import pandas as pd
import streamlit as st
import fpdf as _fpdf_module
from fpdf import FPDF  # δουλεύει και με fpdf2 (προτείνεται) και με το παλιό fpdf 1.7

FPDF2 = int(str(getattr(_fpdf_module, "__version__", "1")).split(".")[0]) >= 2

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
# RULE CHECKING (used for warnings)
# ----------------------------
def _week_monday(date):
    return date - datetime.timedelta(days=date.weekday())


def _violation_reasons(doctor, date, schedule):
    """Λίστα κανόνων που παραβιάζει η εφημερία (doctor, date). Κενή λίστα = όλα εντάξει."""
    others = [d for d, doc in schedule.items() if doc == doctor and d != date]
    reasons = []
    if any(abs((d - date).days) <= 3 for d in others):
        reasons.append("κενό μικρότερο των 4 ημερών")
    wk = _week_monday(date)
    if sum(1 for d in others if _week_monday(d) == wk) >= 2:
        reasons.append("πάνω από 2 εφημερίες την εβδομάδα")
    ym = (date.year, date.month)
    if sum(1 for d in others if (d.year, d.month) == ym) >= 5:
        reasons.append("πάνω από 5 εφημερίες τον μήνα")
    if date.weekday() >= 4 and any(
        d.weekday() == date.weekday() and (d.year, d.month) == ym for d in others
    ):
        reasons.append(f"δεύτερη {WEEKDAY_LABELS[date.weekday()]} στον ίδιο μήνα")
    return reasons


def find_violations(schedule):
    out = []
    for d in sorted(schedule):
        reasons = _violation_reasons(schedule[d], d, schedule)
        if reasons:
            out.append((d, schedule[d], ", ".join(reasons)))
    return out


# ----------------------------
# HOLIDAY HELPERS
# ----------------------------
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


def get_major_holidays_in_range(start_date, end_date):
    target_dates = {}
    for year in range(start_date.year, end_date.year + 1):
        c_dates = [
            (datetime.date(year, 1, 1), "Πρωτοχρονιά"),
            (datetime.date(year, 12, 24), "Παραμονή Χριστουγέννων"),
            (datetime.date(year, 12, 25), "Χριστούγεννα"),
            (datetime.date(year, 12, 26), "Δεύτερη μέρα Χριστουγέννων"),
            (datetime.date(year, 12, 31), "Παραμονή Πρωτοχρονιάς"),
        ]
        for d, name in c_dates:
            if start_date <= d <= end_date:
                target_dates[d] = name

        easter = orthodox_easter(year)
        e_dates = [
            (easter - datetime.timedelta(days=2), "Μεγάλη Παρασκευή"),
            (easter - datetime.timedelta(days=1), "Μεγάλο Σάββατο"),
            (easter, "Κυριακή του Πάσχα"),
            (easter + datetime.timedelta(days=1), "Δευτέρα του Πάσχα"),
        ]
        for d, name in e_dates:
            if start_date <= d <= end_date:
                target_dates[d] = name

    return dict(sorted(target_dates.items()))


# ----------------------------
# ΚΑΝΟΝΕΣ ΜΕΓΑΛΩΝ ΑΡΓΙΩΝ
#  1) Κανείς δεν παίρνει δύο από: 25/12, 26/12, 31/12, 1/1, Κυριακή και Δευτέρα του Πάσχα
#  2) Όποιος παίρνει 24/12 (Παραμονή Χριστουγέννων) παίρνει και το Μεγάλο Σάββατο
#  3) Όποιος παίρνει 26/12 παίρνει και τη Μεγάλη Παρασκευή
# ----------------------------
CORE_TYPES = {"xmas", "xmas2", "nye", "ny", "easter", "easter_mon"}
PAIR_TYPES = [("xmas_eve", "holy_sat"), ("xmas2", "good_fri")]


def _major_type(d):
    if d.month == 12:
        return {24: "xmas_eve", 25: "xmas", 26: "xmas2", 31: "nye"}.get(d.day)
    if d.month == 1 and d.day == 1:
        return "ny"
    off = (d - orthodox_easter(d.year)).days
    return {-2: "good_fri", -1: "holy_sat", 0: "easter", 1: "easter_mon"}.get(off)


def build_major_rules(major_dates):
    """Επιστρέφει (core_group, pairs).
    core_group: ημερομηνία -> ομάδα (περίοδος) για τις 'βαριές' αργίες.
    pairs: λίστα (ημ/νία Α, ημ/νία Β) που πρέπει να πάνε στον ίδιο γιατρό.
    Η ομαδοποίηση επιλέγεται αυτόματα: ημερολογιακό έτος (Ιαν-Δεκ) ή
    'Χριστούγεννα -> επόμενο Πάσχα', όποια δίνει περισσότερα πλήρη ζευγάρια στο εύρος."""
    types = {d: _major_type(d) for d in major_dates}

    def gk_calendar(d):
        return d.year

    def gk_season(d):
        return d.year if d.month == 12 else d.year - 1

    def pairs_for(gk):
        by = {(gk(d), t): d for d, t in types.items() if t}
        out = []
        for a, b in PAIR_TYPES:
            for (g, t), d in by.items():
                if t == a and (g, b) in by:
                    out.append((d, by[(g, b)]))
        return out

    p_cal, p_sea = pairs_for(gk_calendar), pairs_for(gk_season)
    gk, pairs = (gk_season, p_sea) if len(p_sea) > len(p_cal) else (gk_calendar, p_cal)
    core_group = {d: gk(d) for d, t in types.items() if t in CORE_TYPES}
    return core_group, pairs


def find_major_violations(schedule, major_holidays):
    dates = [d for d in major_holidays if d in schedule]
    core_group, pairs = build_major_rules(dates)
    out, per = [], {}
    for d, g in core_group.items():
        per.setdefault((schedule[d], g), []).append(d)
    for (doc, g), ds in per.items():
        if len(ds) > 1:
            names = ", ".join(f"{x:%d/%m/%Y} ({major_holidays[x]})" for x in sorted(ds))
            out.append((min(ds), doc, f"δύο μεγάλες της ίδιας περιόδου: {names}"))
    for a, b in pairs:
        if schedule[a] != schedule[b]:
            out.append((a, schedule[a],
                        f"{major_holidays[a]} και {major_holidays[b]} ({b:%d/%m/%Y}) "
                        f"πρέπει να πάνε στον ίδιο γιατρό (τώρα: {schedule[b]})"))
    return sorted(out, key=lambda t: t[0])


# ----------------------------
# OPTIMIZER
# Ισοκατανέμει ταυτόχρονα: μεγάλες αργίες, μικρές αργίες, σύνολο αργιών,
# Παρασκευές/Σάββατα/Κυριακές ανά γιατρό, μήνες με Σάββατο ΚΑΙ Κυριακή,
# και εφημερίες ανά μήνα. Οι κανόνες (κενό 3 ημερών, 2/εβδομάδα, 5/μήνα,
# μία Παρ/Σαβ/Κυρ τον μήνα) είναι απαράβατοι.
# ----------------------------
def optimize_schedule(schedule, holiday_names, major_holidays, locked,
                      prior_major=None, prior_minor=None,
                      window=14, iters=40000, seed=0,
                      w_wd=15, w_dbl=10, w_mon=5, w_core=400, w_pair=400):
    rng = random.Random(seed)
    prior_major = prior_major or {}
    prior_minor = prior_minor or {}
    kind = {d: ("M" if d in major_holidays else "m") for d in holiday_names}

    core_group, pairs = build_major_rules([d for d in major_holidays if d in schedule])
    pairs_of = {}
    for a, b in pairs:
        pairs_of.setdefault(a, []).append((a, b))
        pairs_of.setdefault(b, []).append((a, b))

    maj = {k: prior_major.get(k, 0) for k in DOCTORS}
    mnr = {k: prior_minor.get(k, 0) for k in DOCTORS}
    wd = {k: {4: 0, 5: 0, 6: 0} for k in DOCTORS}
    wkend = {k: {} for k in DOCTORS}     # doc -> {(y, m): [Σαβ, Κυρ]}
    mcnt = {k: {} for k in DOCTORS}      # doc -> {(y, m): εφημερίες}
    dbl = {k: 0 for k in DOCTORS}        # μήνες με Σάββατο ΚΑΙ Κυριακή
    ddates = {k: set() for k in DOCTORS}
    mon_sq = {k: 0 for k in DOCTORS}
    core_cnt = {k: {} for k in DOCTORS}  # doc -> {ομάδα: πλήθος 'βαριών' αργιών}
    core_dup = {k: 0 for k in DOCTORS}   # ζεύγη 'βαριών' αργιών στον ίδιο γιατρό/περίοδο

    def apply(date, doc, s):
        if s > 0:
            ddates[doc].add(date)
        else:
            ddates[doc].discard(date)
        kd = kind.get(date)
        if kd == "M":
            maj[doc] += s
        elif kd == "m":
            mnr[doc] += s
        g = core_group.get(date)
        if g is not None:
            c = core_cnt[doc].get(g, 0)
            core_dup[doc] += (c + s) * (c + s - 1) // 2 - c * (c - 1) // 2
            core_cnt[doc][g] = c + s
        w = date.weekday()
        if w >= 4:
            wd[doc][w] += s
        ym = (date.year, date.month)
        if w in (5, 6):
            pair = wkend[doc].setdefault(ym, [0, 0])
            before = pair[0] > 0 and pair[1] > 0
            pair[w - 5] += s
            after = pair[0] > 0 and pair[1] > 0
            dbl[doc] += int(after) - int(before)
        c = mcnt[doc].get(ym, 0)
        mon_sq[doc] += (c + s) ** 2 - c ** 2
        mcnt[doc][ym] = c + s

    for d, doc in schedule.items():
        apply(d, doc, +1)

    def doc_cost(k):
        return (
            100 * maj[k] ** 2 + 10 * mnr[k] ** 2 + (maj[k] + mnr[k]) ** 2
            + w_wd * sum(v * v for v in wd[k].values())
            + w_dbl * dbl[k] ** 2
            + w_mon * mon_sq[k]
            + w_core * core_dup[k]
        )

    def valid(doc, date):
        others = ddates[doc] - {date}
        if any(abs((o - date).days) <= 3 for o in others):
            return False
        wk = _week_monday(date)
        if sum(1 for o in others if _week_monday(o) == wk) >= 2:
            return False
        ym = (date.year, date.month)
        if sum(1 for o in others if (o.year, o.month) == ym) >= 5:
            return False
        if date.weekday() >= 4 and any(
            o.weekday() == date.weekday() and (o.year, o.month) == ym for o in others
        ):
            return False
        return True

    free = sorted(d for d in schedule if d not in locked)
    if len(free) < 2:
        return schedule

    total = (sum(doc_cost(k) for k in DOCTORS)
             + w_pair * sum(1 for a, b in pairs if schedule[a] != schedule[b]))
    best_total, best = total, dict(schedule)
    T0, T1 = 60.0, 0.5

    for i in range(iters):
        T = T0 * (T1 / T0) ** (i / iters)
        x = rng.choice(free)
        y = x + datetime.timedelta(days=rng.randint(-window, window))
        if y == x or y not in schedule or y in locked:
            continue
        P, Q = schedule[x], schedule[y]
        if P == Q:
            continue

        affected = set(pairs_of.get(x, ())) | set(pairs_of.get(y, ()))
        pair_before = sum(1 for a, b in affected if schedule[a] != schedule[b])
        pair_after = sum(
            1 for a, b in affected
            if (Q if a == x else P if a == y else schedule[a])
            != (Q if b == x else P if b == y else schedule[b])
        )

        before = doc_cost(P) + doc_cost(Q)
        apply(x, P, -1); apply(y, Q, -1)
        apply(y, P, +1); apply(x, Q, +1)
        delta = doc_cost(P) + doc_cost(Q) - before + w_pair * (pair_after - pair_before)

        if valid(P, y) and valid(Q, x) and (delta <= 0 or rng.random() < math.exp(-delta / T)):
            schedule[x], schedule[y] = Q, P
            total += delta
            if total < best_total - 1e-9:
                best_total, best = total, dict(schedule)
        else:
            apply(y, P, -1); apply(x, Q, -1)
            apply(x, P, +1); apply(y, Q, +1)

    schedule.clear()
    schedule.update(best)
    return schedule


# ----------------------------
# SCHEDULE GENERATION
# ----------------------------
def generate_full_schedule(start_date, end_date, initial_week, ref_monday,
                           manual_assignments=None, prior_major=None, prior_minor=None):
    manual_assignments = manual_assignments or {}
    base = {}

    # Βασική ροτά (ξεκινά από την Δευτέρα αναφοράς, ώστε να δουλεύει σωστά
    # ακόμα κι όταν η ημερομηνία έναρξης δεν είναι Δευτέρα)
    for i in range((end_date - start_date).days + 1):
        cur = start_date + datetime.timedelta(days=i)
        off = (cur - ref_monday).days
        base[cur] = initial_week[((off % 7) + (off // 7) * 2) % len(initial_week)]

    # Χειροκίνητες αλλαγές (κλειδωμένες)
    for d, doc in manual_assignments.items():
        if d in base:
            base[d] = doc

    holiday_names = get_holidays_in_range(start_date, end_date)
    major = get_major_holidays_in_range(start_date, end_date)
    locked = {d for d in manual_assignments if d in base}

    # Έως 6 προσπάθειες μέχρι να τηρηθούν πλήρως οι κανόνες των μεγάλων αργιών
    best = None
    for attempt in range(6):
        sch = dict(base)
        optimize_schedule(sch, holiday_names, major, locked, prior_major, prior_minor, seed=attempt)
        n_viol = len(find_major_violations(sch, major))
        if best is None or n_viol < best[0]:
            best = (n_viol, sch)
        if n_viol == 0:
            break
    return best[1], holiday_names


# ----------------------------
# BALANCE & REPORTING
# ----------------------------
def compute_balance(schedule, holiday_dates=None):
    holiday_dates = holiday_dates or set()
    counts = {doc: {wd: 0 for wd in WEEKDAY_LABELS} for doc in DOCTORS}
    holiday_counts = {doc: 0 for doc in DOCTORS}
    for date, doc in schedule.items():
        if doc not in counts:
            continue
        counts[doc][WEEKDAY_LABELS[date.weekday()]] += 1
        if date in holiday_dates:
            holiday_counts[doc] += 1
    df = pd.DataFrame.from_dict(counts, orient="index").reset_index()
    df.rename(columns={"index": "Doctor"}, inplace=True)
    df["Weekdays"] = df["Mon"] + df["Tue"] + df["Wed"] + df["Thu"]
    df["Αργίες"] = df["Doctor"].map(holiday_counts)
    df["Total"] = df["Weekdays"] + df["Fri"] + df["Sat"] + df["Sun"]
    return df[["Doctor", "Weekdays", "Fri", "Sat", "Sun", "Αργίες", "Total"]]


def compute_holidays_summary(schedule, holidays):
    summary = {doc: {"Count": 0, "Details": []} for doc in DOCTORS}
    for d in sorted(holidays):
        doc = schedule.get(d)
        if doc in summary:
            summary[doc]["Count"] += 1
            summary[doc]["Details"].append(f"{d.strftime('%d/%m/%Y')} ({holidays[d]})")
    return pd.DataFrame([
        {
            "Ακτινολόγος": doc,
            "Σύνολο": summary[doc]["Count"],
            "Ημερομηνίες & Εορτές": ", ".join(summary[doc]["Details"]) or "Καμία",
        }
        for doc in DOCTORS
    ])


def compute_weekend_summary(schedule):
    """Πόσους μήνες έχει ο καθένας και Σάββατο ΚΑΙ Κυριακή."""
    months = {}
    for d, doc in schedule.items():
        if d.weekday() in (5, 6):
            months.setdefault((d.year, d.month, doc), set()).add(d.weekday())
    both = {doc: 0 for doc in DOCTORS}
    for (_, _, doc), days in months.items():
        if len(days) == 2:
            both[doc] += 1
    return pd.DataFrame({"Ακτινολόγος": DOCTORS,
                         "Μήνες με Σάββατο ΚΑΙ Κυριακή": [both[d] for d in DOCTORS]})


# ----------------------------
# PDF
# ----------------------------
def _find_font(name):
    try:
        here = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        here = os.getcwd()
    for folder in (here, os.getcwd(), "/usr/share/fonts/truetype/dejavu",
                   "/usr/share/fonts/dejavu"):
        path = os.path.join(folder, name)
        if os.path.exists(path):
            return path
    return None


def _pdf_cell(pdf, w, h, txt, border=0, align="", newline=False):
    """Κελί που δουλεύει σε fpdf2 και σε παλιό fpdf."""
    if FPDF2:
        extra = {"new_x": "LMARGIN", "new_y": "NEXT"} if newline else {}
        pdf.cell(w, h, txt, border=border, align=align, **extra)
    else:
        pdf.cell(w, h, txt, border=border, align=align, ln=1 if newline else 0)


def create_balance_pdf(df, start_date, end_date):
    regular = _find_font("DejaVuSans.ttf")
    if regular is None:
        raise FileNotFoundError("Λείπει το DejaVuSans.ttf δίπλα στο αρχείο της εφαρμογής")
    bold = _find_font("DejaVuSans-Bold.ttf") or regular

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    if FPDF2:
        pdf.add_font("DejaVu", "", regular)
        pdf.add_font("DejaVu", "B", bold)
    else:
        pdf.add_font("DejaVu", "", regular, uni=True)
        pdf.add_font("DejaVu", "B", bold, uni=True)

    pdf.set_font("DejaVu", "B", 16)
    _pdf_cell(pdf, 0, 10, "Doctor Balance Summary", align="C", newline=True)
    pdf.set_font("DejaVu", "", 12)
    _pdf_cell(pdf, 0, 8, f"Period: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}",
              align="C", newline=True)
    pdf.ln(6)

    col_widths = [45, 25, 18, 18, 18, 22, 22]
    pdf.set_font("DejaVu", "B", 12)
    for h, w in zip(df.columns, col_widths):
        _pdf_cell(pdf, w, 8, str(h), border=1, align="C")
    pdf.ln()
    pdf.set_font("DejaVu", "", 12)
    for _, row in df.iterrows():
        for val, w in zip(row, col_widths):
            _pdf_cell(pdf, w, 8, str(val), border=1, align="C")
        pdf.ln()

    if FPDF2:
        return bytes(pdf.output())
    out = pdf.output(dest="S")
    return out if isinstance(out, (bytes, bytearray)) else out.encode("latin-1")


# ----------------------------
# UI HELPERS
# ----------------------------
def show_df(df, height=None):
    kw = {"height": height} if height else {}
    try:
        st.dataframe(df, width="stretch", **kw)
    except Exception:
        st.dataframe(df, use_container_width=True, **kw)


def display_calendar(schedule, holiday_names):
    manual_assignments = st.session_state.get("manual_assignments", {})
    last_month = None
    for date in sorted(schedule.keys()):
        month_name = date.strftime("%B %Y")
        if month_name != last_month:
            st.markdown(f"## {month_name}")
            last_month = month_name
            headers = st.columns(7)
            for i, d in enumerate(WEEKDAY_LABELS):
                headers[i].markdown(f"**{d}**")
            cal = calendar.Calendar(firstweekday=0)
            weeks = cal.monthdatescalendar(date.year, date.month)
            for week in weeks:
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day.month == date.month:
                        doc = schedule.get(day, "")
                        is_holiday = day in holiday_names
                        icon = " ✏️" if day in manual_assignments else ""
                        holiday_tag = (
                            f"<br><span style='font-size:10px'>🎉 {holiday_names[day]}</span>"
                            if is_holiday else ""
                        )
                        color = "#%02x%02x%02x" % DOCTOR_COLORS.get(doc, (220, 220, 220))
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

for key, default in {
    "manual_assignments": {},
    "schedule": None,
    "holiday_names": {},
    "balance": None,
    "initial_week": None,
    "start_date": datetime.date.today(),
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

left_col, right_col = st.columns([0.35, 0.65])

# ---------- LEFT: status, manual override, reports ----------
with left_col:
    st.subheader("📊 Κατάσταση Εφημεριών Εύρους")
    schedule = st.session_state.schedule

    if schedule:
        first_day, last_day = min(schedule), max(schedule)

        manual_date = st.date_input(
            "Επιλέξετε ημερομηνία για αλλαγή",
            value=first_day, min_value=first_day, max_value=last_day, key="manual_date",
        )
        manual_doctor = st.selectbox("Επιλογή Ακτινολόγου", DOCTORS, key="manual_doc")

        b1, b2 = st.columns(2)
        if b1.button("✅ Επικύρωση"):
            st.session_state.manual_assignments[manual_date] = manual_doctor
            st.session_state.schedule[manual_date] = manual_doctor
            st.session_state.balance = compute_balance(
                st.session_state.schedule,
                holiday_dates=set(st.session_state.holiday_names.keys()),
            )
            st.rerun()
        if b2.button("🧹 Καθαρισμός αλλαγών", help="Ισχύει στην επόμενη δημιουργία προγράμματος"):
            st.session_state.manual_assignments = {}
            st.rerun()

        problems = find_violations(schedule) + find_major_violations(
            schedule, get_major_holidays_in_range(first_day, last_day))
        problems.sort(key=lambda t: t[0])
        if problems:
            with st.expander(f"⚠️ {len(problems)} παραβιάσεις κανόνων", expanded=False):
                for d, doc, why in problems:
                    st.write(f"{d.strftime('%d/%m/%Y')} – {doc}: {why}")

    if st.session_state.balance is not None and not st.session_state.balance.empty:
        show_df(st.session_state.balance, height=290)

        first_day, last_day = min(schedule), max(schedule)
        major_hols = get_major_holidays_in_range(first_day, last_day)
        if major_hols:
            with st.expander("🎄🐣 Ανάλυση Μεγάλων Εορτών"):
                show_df(compute_holidays_summary(schedule, major_hols))

        regular_hols = {d: n for d, n in st.session_state.holiday_names.items()
                        if d not in major_hols}
        if regular_hols:
            with st.expander("🎈 Ανάλυση Μικρών Αργιών"):
                show_df(compute_holidays_summary(schedule, regular_hols))

        with st.expander("📆 Σάββατο ΚΑΙ Κυριακή στον ίδιο μήνα"):
            show_df(compute_weekend_summary(schedule))

        try:
            pdf_bytes = create_balance_pdf(st.session_state.balance, first_day, last_day)
            st.download_button("📄 Κατέβασε κατάσταση σε PDF", data=pdf_bytes,
                               file_name="balance_summary.pdf", mime="application/pdf")
        except Exception as e:  # το PDF δεν πρέπει να ρίχνει ποτέ την εφαρμογή
            st.caption(f"PDF μη διαθέσιμο: {e}")

# ---------- RIGHT: initial rota, range, calendar ----------
with right_col:
    selected_date = st.date_input("Ημερομηνία έναρξης:", datetime.date.today())
    week_dates = [
        selected_date - datetime.timedelta(days=selected_date.weekday()) + datetime.timedelta(days=i)
        for i in range(7)
    ]

    initial_week = {}
    cols = st.columns(7)
    for i, d in enumerate(week_dates):
        with cols[i]:
            initial_week[d] = st.selectbox(d.strftime("%a %d/%m"), DOCTORS,
                                           index=i % 7, key=f"doc_{d}")

    if st.button("💾 Αποθήκευση Αρχικής Ρότας"):
        chosen = [initial_week[d] for d in week_dates]
        if len(set(chosen)) != len(DOCTORS):
            st.error("Κάθε ακτινολόγος πρέπει να εμφανίζεται ακριβώς μία φορά στην εβδομάδα.")
        else:
            st.session_state.initial_week = chosen
            st.session_state.start_date = week_dates[0]  # Δευτέρα αναφοράς
            st.rerun()

    if st.session_state.initial_week:
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start date", st.session_state.start_date)
        with c2:
            end_date = st.date_input("End date", start_date + datetime.timedelta(days=30))

        with st.expander("⚖️ Αργίες από προηγούμενες περιόδους (προαιρετικό)"):
            st.caption("Πόσες αργίες έχει ήδη κάνει ο καθένας, ώστε η κατανομή να είναι δίκαιη στον χρόνο.")
            prior_major, prior_minor = {}, {}
            for doc in DOCTORS:
                a, b = st.columns(2)
                prior_major[doc] = a.number_input(f"{doc} – μεγάλες", 0, 30, 0, key=f"pm_{doc}")
                prior_minor[doc] = b.number_input(f"{doc} – μικρές", 0, 30, 0, key=f"pn_{doc}")

        if st.button("🗓️ Δημιουργία Προγράμματος"):
            if end_date < start_date:
                st.error("Η ημερομηνία λήξης είναι πριν την έναρξη.")
            else:
                with st.spinner("Υπολογισμός δίκαιης κατανομής..."):
                    sch, hols = generate_full_schedule(
                        start_date, end_date, st.session_state.initial_week,
                        ref_monday=st.session_state.start_date,
                        manual_assignments=st.session_state.manual_assignments,
                        prior_major=prior_major, prior_minor=prior_minor,
                    )
                st.session_state.schedule = sch
                st.session_state.holiday_names = hols
                st.session_state.balance = compute_balance(sch, holiday_dates=set(hols.keys()))
                st.rerun()

    if st.session_state.schedule:
        display_calendar(st.session_state.schedule, st.session_state.holiday_names)
