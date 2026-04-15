from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
# own
from utils import xlsx_row_iterator
from utils import xlsx_write


app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Sample data
table_data = None
header = None

column1_options = []
column2_options = []

path_dropdown = "/home/mark/swap uploader - tap.xlsx"
path_lookupt = "/home/mark/clients/price_lookup_TAP.xlsx"

# -- load dropdown list
for i, row in enumerate(xlsx_row_iterator(path_dropdown, sheet='ICE')):
    if i == 0:
        continue
    if any(row):
        column1_options.append(row[0])
        column2_options.append(row[2])
    else:
        break

column1_options = sorted(column1_options)
column2_options = sorted(column2_options)
print(column2_options)

@app.get("/", response_class=HTMLResponse)
async def read_table(request: Request):
    global table_data, header
    rows = []
    for row in xlsx_row_iterator(path_lookupt):
        if any(row):
            rows.append(row)
        else:
            break
    if rows:
        table_data = rows[1:]
        header = rows[0]
    return templates.TemplateResponse("table_template.html", {
        "request": request,
        "table_data": table_data,
        "column1_options": column1_options,
        "column2_options": column2_options,
        "column3_options": column2_options,
    })


@app.post("/add_row")
async def add_row(column1: str = Form(...), column2: str = Form(...), column3: str = Form(...)):
    global table_data, header, path
    if table_data:
        table_data.append([column1, column2, column3])
        xlsx_write(header, table_data, path_lookupt)
        return RedirectResponse(url="/", status_code=303)
    else:
        return 500 #TODO make error
