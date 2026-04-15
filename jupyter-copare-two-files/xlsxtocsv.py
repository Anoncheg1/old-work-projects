import os
import sys
import csv
import openpyxl
# own
from utils import xlsx_row_iterator
from utils import csv_row_iterator
from utils import xlsx_write

def xlsx_to_csv(xlsx_file, csv_file):
    ri = xlsx_row_iterator(xlsx_file)
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        c = csv.writer(f)
        for i, r in enumerate(ri):
            if not any(r):
                break
            c.writerow(r)
        print("Rows written:", i)


def csv_to_xlsx(csv_file, xlsx_file):
    "Warning: memory limitied."
    ri = csv_row_iterator(csv_file)
    rows = list(ri)
    xlsx_write(header=None, data=rows, filename=xlsx_file)
    print("Rows written:", len(rows))


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python script.py input.xlsx [output.csv]")
        sys.exit(1)

    xlsx_file = sys.argv[1]
    csv_file = sys.argv[2] if len(sys.argv) == 3 else None

    # If csv_file is not provided, create it from xlsx_file
    if csv_file is None:
        base_name = os.path.splitext(xlsx_file)[0]
        csv_file = base_name + ".csv"

    xlsx_to_csv(xlsx_file, csv_file)
    print(f"Conversion complete. CSV file saved as {csv_file}")
