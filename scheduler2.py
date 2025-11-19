import io
from fpdf import FPDF

# -------------------------------
# PDF calendar exporter with Unicode support
# -------------------------------
class CalendarPDF(FPDF):
    def header(self):
        # No default header
        pass

    def add_calendar_page(self, year, month, schedule, edits=None):
        if edits is None:
            edits = {}
        self.add_page()

        # Add Unicode-supporting font
        self.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
        self.set_font("DejaVu", "B", 16)
        self.cell(0, 10, f"{calendar.month_name[month]} {year}", 0, 1, "C")
        self.ln(4)

        # Grid settings
        col_width = 26
        row_height = 16
        left_margin = (self.w - (col_width * 7)) / 2
        self.set_x(left_margin)

        # Weekday header
        self.set_font("DejaVu", "B", 10)
        for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            self.cell(col_width, row_height, d, 1, 0, "C")
        self.ln(row_height)
        self.set_x(left_margin)

        self.set_font("DejaVu", "", 9)
        cal = calendar.Calendar(firstweekday=0)
        for week in cal.monthdatescalendar(year, month):
            for d in week:
                if d.month != month:
                    self.set_fill_color(240, 240, 240)
                    self.cell(col_width, row_height, "", 1, 0, "C", 1)
                else:
                    doc_base = schedule.get(d, "")
                    doc_edit = edits.get(d, doc_base)
                    doc_text = doc_edit
                    if d in edits and edits[d] != doc_base:
                        doc_text = f"{doc_edit} ✎"  # mark edited
                    # Color coding
                    if doc_text.strip():
                        try:
                            # convert hex to RGB
                            hexcol = DOCTOR_COLORS.get(doc_edit, "#ffffff")
                            r = int(hexcol[1:3], 16)
                            g = int(hexcol[3:5], 16)
                            b = int(hexcol[5:7], 16)
                            self.set_fill_color(r, g, b)
                        except Exception:
                            self.set_fill_color(255, 255, 255)
                    else:
                        self.set_fill_color(255, 255, 255)

                    # Keep text short: "day\ndoctor"
                    text = f"{d.day}\n{doc_text}"
                    self.multi_cell(col_width, row_height / 2, text, border=1, align="C", fill=True, ln=3)
            self.ln(row_height)
            self.set_x(left_margin)

def export_calendar_pdf(all_schedules, edits_map, filename="calendar.pdf"):
    pdf = CalendarPDF()
    for (year, month), schedule in sorted(all_schedules.items()):
        month_edits = edits_map.get((year, month), {})
        pdf.add_calendar_page(year, month, schedule, month_edits)
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf
