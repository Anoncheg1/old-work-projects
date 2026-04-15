from utils import create_row_iterator, xlsx_row_iterator


PATH_DROPDOWN = "/home/mark/swap uploader - tap.xlsx"

column1_options = []
column1_1_options = [] # TODO
for i, row in enumerate(xlsx_row_iterator(PATH_DROPDOWN, sheet='PLATTS')):
        if i == 0:
            continue
        if any(row):
            print(row)
            if row[0]:
                column1_options.append(row[0])
            if row[2]:
                column1_1_options.append(row[2])
        else:
            break
