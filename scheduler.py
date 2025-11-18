# Doctor Shift Scheduler - PySide6 Desktop App
# Full version with batch holiday selection, schedule rules, and printing

import sys
import calendar
from datetime import date, timedelta
from collections import defaultdict, deque
import pickle

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QTableWidget, QTableWidgetItem, QGroupBox, QGridLayout,
    QCheckBox, QHeaderView, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt

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

def assign_shifts(dates, doctors, prev_assignments=None, weekend_history=None, friday_history=None):
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
        # Strict 2-day gap
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

    # Step 1: Weekends
    weekend_days = sorted(saturdays + sundays)
    total_weekends = len(weekend_days)
    base_count = total_weekends // len(doctors)
    extras = total_weekends - base_count*len(doctors)
    weekend_assign_counts = defaultdict(int)

    for d in weekend_days:
        sorted_docs = sorted(doctors, key=lambda doc: (weekend_history[doc], weekend_assign_counts[doc]))
        assigned = False
        for doc in sorted_docs:
            max_shifts = base_count + (1 if extras > 0 else 0)
            if weekend_assign_counts[doc] >= max_shifts:
                continue
            if not can_assign(doc, d, is_weekend=True):
                continue
            assign_map[d] = doc
            weekend_assign_counts[doc] += 1
            weekend_history[doc] += 1
            last_weekend_doc[doc] = d
            if extras > 0 and weekend_assign_counts[doc] > base_count:
                extras -= 1
            assigned = True
            break
        if not assigned:
            doc = sorted_docs[0]
            assign_map[d] = doc
            weekend_assign_counts[doc] += 1
            weekend_history[doc] += 1
            last_weekend_doc[doc] = d

    # Step 2: Fridays
    total_fridays = len(fridays)
    base_count = total_fridays // len(doctors)
    extras = total_fridays - base_count*len(doctors)
    friday_assign_counts = defaultdict(int)

    for d in fridays:
        sorted_docs = sorted(doctors, key=lambda doc: (weekend_assign_counts[doc], friday_history[doc]))
        assigned = False
        for doc in sorted_docs:
            max_shifts = base_count + (1 if extras > 0 else 0)
            if friday_assign_counts[doc] >= max_shifts:
                continue
            if not can_assign(doc, d):
                continue
            assign_map[d] = doc
            friday_assign_counts[doc] += 1
            friday_history[doc] += 1
            if extras > 0 and friday_assign_counts[doc] > base_count:
                extras -= 1
            assigned = True
            break
        if not assigned:
            doc = sorted_docs[0]
            assign_map[d] = doc
            friday_assign_counts[doc] += 1
            friday_history[doc] += 1

    # Step 3: Weekdays
    weekday_cycle = deque(doctors)
    for d in weekdays:
        for _ in range(len(weekday_cycle)):
            doc = weekday_cycle[0]
            if can_assign(doc, d):
                assign_map[d] = doc
                weekday_cycle.rotate(-1)
                break
            weekday_cycle.rotate(-1)
        else:
            assign_map[d] = weekday_cycle[0]
            weekday_cycle.rotate(-1)

    return assign_map

# ---------------------------
# GUI code

class SchedulerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Doctor Shift Scheduler")
        self.resize(1400, 850)
        self.prev_assignments = {}
        self.weekend_history = defaultdict(int)
        self.friday_history = defaultdict(int)
        self.doctors = ["Αθηνά","Αλέξανδρος","Έλενα","Έλια","Εύα","Μαρία","Χριστίνα"]
        self.generated_month_tables = {}
        self.holidays = defaultdict(set)
        self.temp_holiday_changes = set()
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        # Controls panel
        controls = QVBoxLayout()
        controls_group = QGroupBox("Settings")
        controls_group.setLayout(controls)
        controls_group.setMaximumWidth(380)

        # Year/Month
        ym_layout = QHBoxLayout()
        year_label = QLabel("Year:")
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(date.today().year)
        month_label = QLabel("Month:")
        self.month_combo = QComboBox()
        for m in range(1,13):
            self.month_combo.addItem(f"{m:02d} - {calendar.month_name[m]}", m)
        self.month_combo.setCurrentIndex(date.today().month-1)
        ym_layout.addWidget(year_label)
        ym_layout.addWidget(self.year_spin)
        ym_layout.addWidget(month_label)
        ym_layout.addWidget(self.month_combo)
        controls.addLayout(ym_layout)

        self.start_balance_checkbox = QCheckBox("Start balance from this month")
        controls.addWidget(self.start_balance_checkbox)

        self.generate_btn = QPushButton("Generate Schedule")
        self.generate_btn.clicked.connect(self.on_generate)
        controls.addWidget(self.generate_btn)

        self.reset_btn = QPushButton("Reset All")
        self.reset_btn.clicked.connect(self.reset_all)
        controls.addWidget(self.reset_btn)

        self.save_btn = QPushButton("Save State")
        self.save_btn.clicked.connect(self.save_state)
        controls.addWidget(self.save_btn)

        self.load_btn = QPushButton("Load State")
        self.load_btn.clicked.connect(self.load_state)
        controls.addWidget(self.load_btn)

        self.print_btn = QPushButton("Print Schedule")
        self.print_btn.clicked.connect(self.on_print)
        controls.addWidget(self.print_btn)

        # Apply Holidays button
        self.apply_holidays_btn = QPushButton("Apply Holidays")
        self.apply_holidays_btn.clicked.connect(self.apply_holidays)
        controls.addWidget(self.apply_holidays_btn)

        # Generated months combo
        controls.addWidget(QLabel("View Generated Month:"))
        self.generated_months_combo = QComboBox()
        self.generated_months_combo.currentIndexChanged.connect(self.show_selected_month)
        controls.addWidget(self.generated_months_combo)

        # Balance panel
        self.balance_panel = QTableWidget()
        self.balance_panel.setColumnCount(4)
        self.balance_panel.setHorizontalHeaderLabels(["Doctor","Fridays","Saturdays","Sundays"])
        self.balance_panel.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        controls.addWidget(self.balance_panel)
        controls.addStretch()
        main_layout.addWidget(controls_group)

        # Scrollable calendar
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, stretch=2)

    # ---------------------------
    # Generate month
    def on_generate(self):
        year = int(self.year_spin.value())
        month = int(self.month_combo.currentData())
        ym = (year, month)

        if self.start_balance_checkbox.isChecked():
            self.weekend_history = defaultdict(int)
            self.friday_history = defaultdict(int)
            self.prev_assignments = {}

        self.temp_holiday_changes.clear()
        self._generate_month(ym)

    def _generate_month(self, ym):
        year, month = ym
        dates = month_dates(year, month)
        assign_map = assign_shifts(dates, self.doctors,
                                   prev_assignments=self.prev_assignments,
                                   weekend_history=self.weekend_history,
                                   friday_history=self.friday_history)
        self.prev_assignments.update({d: assign_map[d] for d in dates})

        cal = calendar.Calendar(firstweekday=0)
        month_matrix = cal.monthdayscalendar(year, month)
        tbl = QTableWidget()
        tbl.setRowCount(len(month_matrix))
        tbl.setColumnCount(7)
        tbl.setHorizontalHeaderLabels(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl.setWordWrap(True)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.cellClicked.connect(lambda r,c,ym=ym: self.toggle_holiday_temp(r,c))
        self.current_year = year
        self.current_month = month
        self.current_table = tbl

        for r, week in enumerate(month_matrix):
            for c, day in enumerate(week):
                if day==0:
                    item = QTableWidgetItem("")
                else:
                    doc_name = assign_map[date(year, month, day)]
                    item = QTableWidgetItem(f"{day}\n{doc_name}")
                    item.setTextAlignment(Qt.AlignCenter)
                    if day in self.holidays[ym]:
                        item.setBackground(Qt.yellow)
                tbl.setItem(r,c,item)

        self.generated_month_tables[ym] = tbl
        if self.generated_months_combo.findData(ym)==-1:
            self.generated_months_combo.addItem(f"{calendar.month_name[month]} {year}", ym)
            self.generated_months_combo.setCurrentIndex(self.generated_months_combo.count()-1)
        else:
            idx = self.generated_months_combo.findData(ym)
            self.generated_months_combo.setCurrentIndex(idx)

        self.update_balance_panel()
        self.show_month_table(ym)

    # ---------------------------
    # Batch holiday selection
    def toggle_holiday_temp(self, row, col):
        tbl = self.current_table
        item = tbl.item(row, col)
        if not item or item.text() == "":
            return
        day = int(item.text().split("\n")[0])
        ym = (self.current_year, self.current_month)
        key = (ym[0], ym[1], day)
        if key in self.temp_holiday_changes:
            self.temp_holiday_changes.remove(key)
            if day in self.holidays[ym]:
                item.setBackground(Qt.yellow)
            else:
                item.setBackground(Qt.white)
        else:
            self.temp_holiday_changes.add(key)
            item.setBackground(Qt.cyan)

    def apply_holidays(self):
        ym = (self.current_year, self.current_month)
        for y, m, day in self.temp_holiday_changes:
            if day in self.holidays[ym]:
                self.holidays[ym].remove(day)
            else:
                self.holidays[ym].add(day)
        self.temp_holiday_changes.clear()
        # Recalculate month
        self._generate_month(ym)

    # ---------------------------
    def show_selected_month(self, index):
        if index<0:
            return
        ym = self.generated_months_combo.itemData(index)
        self.show_month_table(ym)

    def show_month_table(self, ym):
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        label = QLabel(f"Schedule for {calendar.month_name[ym[1]]} {ym[0]}")
        self.scroll_layout.addWidget(label)
        self.scroll_layout.addWidget(self.generated_month_tables[ym])
        self.current_year, self.current_month = ym
        self.current_table = self.generated_month_tables[ym]

    # ---------------------------
    def update_balance_panel(self):
        self.balance_panel.setRowCount(len(self.doctors))
        for i, doc in enumerate(self.doctors):
            self.balance_panel.setItem(i,0,QTableWidgetItem(doc))
            self.balance_panel.setItem(i,1,QTableWidgetItem(str(self.friday_history[doc])))
            sat_count = sum(1 for d in self.prev_assignments if self.prev_assignments[d]==doc and d.weekday()==5)
            sun_count = sum(1 for d in self.prev_assignments if self.prev_assignments[d]==doc and d.weekday()==6)
            self.balance_panel.setItem(i,2,QTableWidgetItem(str(sat_count)))
            self.balance_panel.setItem(i,3,QTableWidgetItem(str(sun_count)))

    # ---------------------------
    def on_print(self):
        idx = self.generated_months_combo.currentIndex()
        if idx<0:
            return
        ym = self.generated_months_combo.itemData(idx)
        tbl = self.generated_month_tables[ym]
        print(f"\nSchedule for {calendar.month_name[ym[1]]} {ym[0]}:\n")
        for r in range(tbl.rowCount()):
            row_data = []
            for c in range(tbl.columnCount()):
                item = tbl.item(r,c)
                row_data.append(item.text() if item else "")
            print("\t".join(row_data))
        print("\n")

    # ---------------------------
    def reset_all(self):
        self.prev_assignments.clear()
        self.weekend_history.clear()
        self.friday_history.clear()
        self.generated_month_tables.clear()
        self.generated_months_combo.clear()
        self.holidays.clear()
        self.temp_holiday_changes.clear()
        self.update_balance_panel()
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    # ---------------------------
    def save_state(self):
        state = {
            "prev_assignments": self.prev_assignments,
            "weekend_history": dict(self.weekend_history),
            "friday_history": dict(self.friday_history),
            "generated_months": list(self.generated_month_tables.keys()),
            "holidays": {k:list(v) for k,v in self.holidays.items()}
        }
        with open("schedule_state.pkl","wb") as f:
            pickle.dump(state,f)
        QMessageBox.information(self,"Saved","Schedule state saved to schedule_state.pkl")

    # ---------------------------
    def load_state(self):
        try:
            with open("schedule_state.pkl","rb") as f:
                state = pickle.load(f)
            self.prev_assignments = state["prev_assignments"]
            self.weekend_history = defaultdict(int, state["weekend_history"])
            self.friday_history = defaultdict(int, state["friday_history"])
            self.generated_month_tables.clear()
            self.generated_months_combo.clear()
            self.holidays = defaultdict(set,{k:set(v) for k,v in state.get("holidays",{}).items()})
            for ym in state["generated_months"]:
                self._generate_month(ym)
        except Exception as e:
            QMessageBox.warning(self,"Error",f"Failed to load: {e}")

# ---------------------------
# Main

def main():
    app = QApplication(sys.argv)
    scheduler = SchedulerApp()
    scheduler.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
