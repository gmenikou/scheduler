import os
import math
import random
import datetime
import calendar

import pandas as pd
import streamlit as st
from fpdf import FPDF  # pip install fpdf2

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
# OPTIMIZER
# Ισοκατανέμει ταυτόχρονα: μεγάλες αργίες, μικρές αργίες, σύνολο αργιών,
# Παρασκευές/Σάββατα/Κυριακές ανά γιατρό, μήνες με Σάββατο ΚΑΙ Κυριακή,
# και εφημερίες ανά μήνα. Οι κανόνες (κενό 3 ημερών, 2/εβδομάδα, 5/μήνα,
# μία Παρ/Σαβ/Κυρ τον μήνα) είναι απαράβατοι.
# ----------------------------
def optimize_schedule(schedule, holiday_names, major_holidays, locked,
                      prior_major=None, prior_minor=None,
                      window=14, iters=40000, seed=0,
                      w_wd=15, w_dbl=10, w_mon=5):
    rng = random.Random(seed)
    prior_major = prior_major or {}
    prior_minor = prior_minor or {}
    kind = {d: ("M" if d in major_holidays else "m") for d in holiday_names}

    maj = {k: prior_major.get(k, 0) for k in DOCTORS}
    mnr = {k: prior_minor.get(k, 0) for k in DOCTORS}
    wd = {k: {4: 0, 5: 0, 6: 0} for k in DOCTORS}
    wkend = {k: {} for k in DOCTORS}     # doc -> {(y, m): [Σαβ, Κυρ]}
    mcnt = {k: {} for k in DOCTORS}      # doc -> {(y, m): εφημερίες}
    dbl = {k: 0 for k in DOCTORS}        # μήνες με Σάββατο ΚΑΙ Κυριακή
    ddates = {k: set() for k in DOCTORS}
    mon_sq = {k: 0 for k in DOCTORS}

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

    total = sum(doc_cost(k) for k in DOCTORS)
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

        before = doc_cost(P) + doc_cost(Q)
        apply(x, P, -1); apply(y, Q, -1)
        apply(y, P, +1); apply(x, Q, +1)
        delta = doc_cost(P) + doc_cost(Q) - before

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
    schedule = {}

    # Βασική ροτά (ξεκινά από την Δευτέρα αναφοράς, ώστε να δουλεύει σωστά
    # ακόμα κι όταν η ημερομηνία έναρξης δεν είναι Δευτέρα)
    for i in range((end_date - start_date).days + 1):
        cur = start_date + datetime.timedelta(days=i)
        off = (cur - ref_monday).days
        schedule[cur] = initial_week[((off % 7) + (off // 7) * 2) % len(initial_week)]

    # Χειροκίνητες αλλαγές (κλειδωμένες)
    for d, doc in manual_assignments.items():
        if d in schedule:
            schedule[d] = doc

    holiday_names = get_holidays_in_range(start_date, end_date)
    major = get_major_holidays_in_range(start_date, end_date)
    locked = {d for d in manual_assignments if d in schedule}

    optimize_schedule(schedule, holiday_names, major, locked, prior_major, prior_minor)
    return schedule, holiday_names


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


def create_balance_pdf(df, start_date, end_date):
    regular = _find_font("DejaVuSans.ttf")
    if regular is None:
        raise FileNotFoundError("Λείπει το DejaVuSans.ttf δίπλα στο app.py")
    bold = _find_font("DejaVuSans-Bold.ttf") or regular

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", "", regular)
    pdf.add_font("DejaVu", "B", bold)

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

        problems = find_violations(schedule)
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
        except FileNotFoundError as e:
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
