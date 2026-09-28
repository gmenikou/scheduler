fpdf.errors.FPDFUnicodeEncodingException: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:

File "/home/adminuser/venv/lib/python3.14/site-packages/fpdf/fpdf.py", line 5904, in normalize_text
    return text.encode(self.core_fonts_encoding).decode("latin-1")
           ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
UnicodeEncodeError
The above exception was the direct cause of the following exception:
File "/mount/src/scheduler/scheduler3.py", line 475, in <module>
    major_pdf = create_major_holidays_pdf(major_df)
File "/mount/src/scheduler/scheduler3.py", line 354, in create_major_holidays_pdf
    pdf.cell(0, 8, txt, new_x="LMARGIN", new_y="NEXT")
    ~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.14/site-packages/fpdf/fpdf.py", line 288, in wrapper
    return fn(*args, **kwargs)
File "/home/adminuser/venv/lib/python3.14/site-packages/fpdf/deprecation.py", line 36, in wrapper
    return fn(*args, **kwargs)
File "/home/adminuser/venv/lib/python3.14/site-packages/fpdf/fpdf.py", line 3921, in cell
    text = self.normalize_text(text)
File "/home/adminuser/venv/lib/python3.14/site-packages/fpdf/fpdf.py", line 5906, in normalize_text
    raise FPDFUnicodeEncodingException(
    ...<3 lines>...
    ) from error
