import functools
import os
import hashlib
import random
from datetime import datetime, timedelta
import logging
import json
import re
import asyncio
import subprocess
import time
from typing import List, Optional, Callable, Any
from collections import defaultdict
from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi import Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, validator, conint
from pathlib import Path
from fastapi import Response
from fastapi.logger import logger as fastapi_logger
# own
from utils import create_row_iterator, xlsx_row_iterator
from utils import xlsx_write, write_csv_file
from utils import parse_emails
from send_telegram_notification import send_telegram_notification

LOG_FOLDER = Path('/home/webforms/log')
TELEGRAM_LOG = LOG_FOLDER / 'telegram-output.log'
MAIN_LOG = LOG_FOLDER / 'log.log'

PATH_DIST_ONE_TABLE = "/home/mark/clients_distribution_list.csv"
PATH_DROPDOWN = "/home/mark/swap uploader - tap.xlsx"

ADMIN_USERNAME = 'mark'

def get_path_lookupt(username):
    return f"/home/mark/clients/price_lookup_{username}.xlsx"

DIST_ONE_TABLE_HEADERS = ["Client name", "Sftp folder", "Emails"]

# -- FastAPI
try:
    app = FastAPI()
    templates = Jinja2Templates(directory="templates")
except Exception as e:
    send_telegram_notification("Exception in webforms/main.py", TELEGRAM_LOG, MAIN_LOG)
    raise e

# -- logger
logger = logging.getLogger("uvicorn.access")
logger.setLevel(logging.INFO)

# - Add a StreamHandler for console output
stream_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stream_handler.setFormatter(formatter)
# - Add a FileHandler for logging into a file, including stack traces
file_handler = logging.FileHandler(MAIN_LOG)
file_handler.setLevel(logging.ERROR)  # Log errors and above
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s\nStacktrace:\n%(exc_text)s"
)
file_handler.setFormatter(file_formatter)

# - Add handlers to the logger
logger.handlers = [stream_handler, file_handler]

# Disable propagation to prevent duplicate logging
logger = logging.getLogger("uvicorn.error")
logger.propagate = True

# # Middleware to capture unhandled exceptions
# @app.middleware("http")
# async def log_exceptions_middleware(request, call_next):
#     try:
#         return await call_next(request)
#     except Exception as exc:
#         # Log the error globally, stack trace will only appear in the file log
#         logger.error("Unhandled exception occurred", exc_info=True)
#         raise

def exception_handler(func):
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            send_telegram_notification(f"Exception in {func.__name__} of webforms.", TELEGRAM_LOG, MAIN_LOG)
            logger.error("Unhandled exception occurred", exc_info=True)
            raise e
            # if isinstance(e, HTTPException):
            #     return JSONResponse(status_code=e.status_code, content={"detail": str(e.detail)})
            # return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            send_telegram_notification(f"Exception in {func.__name__} of webforms.", TELEGRAM_LOG, MAIN_LOG)
            logger.error("Unhandled exception occurred", exc_info=True)
            raise e
            # if isinstance(e, HTTPException):
            #     return JSONResponse(status_code=e.status_code, content={"detail": str(e.detail)})
            # return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

# -- ------ load lookup table ----------
column1_options = [] # typle
column11_options = []
column12_options = []
column2_options = []



# - load dropdown list
try:
    for i, row in enumerate(xlsx_row_iterator(PATH_DROPDOWN, sheet='PLATTS')):
        if i == 0:
            continue
        if row[0] and row[2]:
            column1_options.append((row[0], str(row[2])))
        else:
            continue

    for i, row in enumerate(xlsx_row_iterator(PATH_DROPDOWN, sheet='ICE')):
        if i == 0:
            continue
        if row[2]:
            column2_options.append(row[2])
        else:
            continue

    column1_options = set(column1_options)
    column1_options = sorted(column1_options, key=lambda x: x[1])
    column11_options, column12_options = zip(*column1_options)
    column2_options = sorted(set(column2_options))
except Exception as e:
    send_telegram_notification("Exception in webforms/main.py", TELEGRAM_LOG, MAIN_LOG)
    raise e

# -- -------------- password management ----------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


USER_DB_FILE = "users.json"


class User(BaseModel):
    username: str
    hashed_password: str


def load_users():
    try:
        with open(USER_DB_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_users(users):
    with open(USER_DB_FILE, "w") as f:
        json.dump(users, f)


users_db = load_users()


# - functions

def get_user(username: str):
    if username in users_db:
        return User(**users_db[username])


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user


def create_or_change_user(username, password):
    hashed_password = get_password_hash(password)
    users_db[username] = {"username": username, "hashed_password": hashed_password}
    save_users(users_db)

@exception_handler
def create_sftp_user(username):
    "create sftp user with password same as username"
    logger.info(f"create_sftp_user {username}.")
    try:
        result = subprocess.run(["sudo", "/usr/local/bin/create_sftpuser.sh", username, username],
                                check=True, capture_output=True, text=True)
        if "User successfully created" in result.stdout:
            send_telegram_notification(f"SFTP User \"{username}\" with password \"{username}\" was created.", TELEGRAM_LOG, MAIN_LOG)
        else:
            send_telegram_notification("SFTP User was not created for some reason.", TELEGRAM_LOG, MAIN_LOG)
    except subprocess.CalledProcessError as e:
        print("Error occurred:", e.stderr)


# -- -- Cookie management ------------
# Cookie format: f"{user.username}:{token}"
COOKIE_NAME = "session"
COOKIE_MAX_AGE = 3600*2  # 2 hour

# Initialize two_salts with two dates
two_salts: List[datetime] = [
    datetime.utcnow() + timedelta(hours=2, minutes=random.randint(1, 30)),
    datetime.utcnow() + timedelta(hours=4, minutes=random.randint(1, 60))
]


def get_salts() -> str:
    global two_salts
    now = datetime.utcnow()

    # Check if the last salt is expiring within 1 hour or has already exipred
    if (two_salts[1] - now) <= timedelta(hours=1):
        # Remove the first date, move the last to first, and add a new date
        two_salts[0] = two_salts[1]
        two_salts[1] = now + timedelta(hours=2, minutes=random.randint(1, 60))
    return two_salts[1].isoformat()


def generate_token(username: str, salt: str | None = None) -> str:
    if not salt:
        salt = get_salts()
    token_input = f"{username}:{salt}"
    return hashlib.sha256(token_input.encode()).hexdigest()


def verify_token(token: str, username: str) -> bool:
    global two_salts
    for salt in two_salts:
        gen_token = generate_token(username, salt.isoformat())
        logger.info(f"username, salt, gent_token: {username}, {salt}, {gen_token} {token}")
        if token == gen_token:
            return True
    return False


async def get_current_user(request: Request):
    session_cookie = request.cookies.get(COOKIE_NAME)
    if not session_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    username, token = session_cookie.split(":")
    if not verify_token(token, username):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    return get_user(username)


# def create_daily_hash(username: str) -> str:
#     """
#     Create a daily hash for a user.

#     Args:
#         username (str): The username of the user.

#     Returns:
#         str: A hexadecimal string representation of the hash.

#     Raises:
#         HTTPException: If the user is not found.
#     """
#     user = get_user(username)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     today = datetime.now().date().isoformat()
#     hash_input = f"{username}:{user.hashed_password}:{today}"

#     return hashlib.sha256(hash_input.encode()).hexdigest()


# def verify_daily_hash(hash: str, username: str) -> bool:
#     """
#     Verify a daily hash for a user.

#     Args:
#         hash (str): The hash to verify.
#         username (str): The username of the user.

#     Returns:
#         bool: True if the hash is valid, False otherwise.
#     """
#     expected_hash = create_daily_hash(username)
#     return hash == expected_hash

def check_cookie(request: Request, ignore_no_cookie:bool = False) -> str | None:
    session_cookie = request.cookies.get(COOKIE_NAME)

    if not session_cookie:
        if ignore_no_cookie:
            return None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="No cookies")
    username, token = session_cookie.split(":")

    if not verify_token(token, username):
        if ignore_no_cookie:
            return None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password")

    return username

# -- -------- Tables read ---------


@exception_handler
def get_look_table(request: Request, username, scroll_down=False):
    rows = []
    for i, row in enumerate(create_row_iterator(get_path_lookupt(username))):
        if any(row):
            rows.append([i-1] + list(row))
        else:
            break
    if rows:
        table_data = rows[1:]
        # header = rows[0]
    return templates.TemplateResponse("look_table.html", {
        "request": request,
        "headers": ["Instrument name", "Balmo", "Outright"],
        "table_data": table_data,
        "column11_options": column11_options,
        "column12_options": column12_options,
        "column2_options": column2_options,
        "username": username,
        "scroll_to_bottom": scroll_down
    })


# @exception_handler
# def load_dist_one_table():
#     "return table_data with id"
#     table_data = []
#     for i, row in enumerate(create_row_iterator(PATH_DIST_ONE_TABLE)):
#         if any(row):
#             table_data.append([i] + row)
#         else:
#             break
#     return DIST_ONE_TABLE_HEADERS, table_data


# def get_user_lineid_in_dist_one_table(dist_table:list, username: str) -> int | None:
#     "dist_table is result of load_dist_one_table"
#     username = username.lower()
#     for i, name, sftp, email in dist_table:
#         if (name and nname == name.lower()) or (sftp and nname in sftp.lower()):
#             return i
#     return None

def load_dist_one_table() -> list:
    dist_table = []
    for row in create_row_iterator(PATH_DIST_ONE_TABLE):
        if any(row):
            dist_table.append(row)
    return dist_table


@exception_handler
def dist_one_table_email(username: str, dist_table: list | None = None) -> str | None:
    "get email for user"
    # - load table
    if not dist_table:
        dist_table = load_dist_one_table()

    nname = username.lower()

    email_to_edit = None
    # - get id of line in table for client
    inum = None
    for i, v in enumerate(dist_table):
        name, sftp, email = v
        if (name and nname == name.lower()) or (sftp and nname in sftp.lower()):
            inum = i
            break

    if inum is None:
        return None

    # - get email from line
    name, sftp, email = dist_table[inum]
    logger.info(f"dist_one_table_email, name {name}, nname {nname}, email {email}")
    if not email:
        return HTTPException(status_code=404, detail=f"No email or user {username}.")

    email_to_edit = parse_emails(email)
    logger.info(f"dist_one_table_email, email {email}, email_to_edit {email_to_edit}")

    if email_to_edit:
        return email_to_edit
    else:
        return None


# @exception_handler
# def get_dist_one_table(request: Request, username, table_data: list | None = None):



# -- -------- paths - login with bruteforce protection ---------------
@app.get("/",		response_class=HTMLResponse)
@app.get("/login",	response_class=HTMLResponse)
@exception_handler
async def home(request: Request):

    # username = check_cookie(request, ignore_no_cookie=True)
    # if username:
    #     return RedirectResponse(url=f"/lookup_table/{username}", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        # request=request,
        name="login.html", context=
        {
            "request": request,
            "post_path": "/login"
        })


# Dictionary to store login attempts
login_attempts = defaultdict(list)

# Maximum number of attempts allowed
MAX_ATTEMPTS = 5

# Time window for tracking attempts (in seconds)
TIME_WINDOW = 300  # 5 minutes

@exception_handler
def check_brute_force(ip_address: str) -> bool:
    current_time = time.time()

    # Remove old attempts outside the time window
    login_attempts[ip_address] = [attempt for attempt in login_attempts[ip_address] if current_time - attempt < TIME_WINDOW]

    # Check if the number of attempts exceeds the limit
    if len(login_attempts[ip_address]) >= MAX_ATTEMPTS:
        return True

    # Add the current attempt
    login_attempts[ip_address].append(current_time)

    return False

@app.post("/login", response_class=HTMLResponse)
@exception_handler
async def login_receive(request: Request, response: Response,
                        form_data: OAuth2PasswordRequestForm = Depends()):

    client_ip = request.client.host

    # - check password
    username = form_data.username
    password = form_data.password
    if not username or not password:
        if check_brute_force(client_ip):
            raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")
        return Response(content="Incorrect username or password", status_code=401)
        # raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
        #                     detail="Incorrect username")

    user: User = authenticate_user(username, password)
    if not user:
        if check_brute_force(client_ip):
            raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")
        return Response(content="Incorrect username or password", status_code=401)
        # raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
        #                     detail="Incorrect username or password")

    # - create cookie
    token = generate_token(user.username)
    session_cookie = f"{user.username}:{token}"
    logger.info(f"session_cookie {session_cookie}")

    logger.info(f"{user} == {ADMIN_USERNAME}")
    if user.username == ADMIN_USERNAME:
        red = RedirectResponse(url="/dist_one_table", status_code=status.HTTP_302_FOUND)
    else:
        red = RedirectResponse(url=f"/lookup_table/{username}", status_code=status.HTTP_302_FOUND)

    # r = get_look_table(request, username, scroll_down=False)
    red.set_cookie(
        key=COOKIE_NAME,
        value=session_cookie,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="strict"
    )
    return red


    # redirect = RedirectResponse(url=f"/lookup_table/{username}", status_code=status.HTTP_302_FOUND)

    # redirect.set_cookie(
    #     key=COOKIE_NAME,
    #     value=session_cookie,
    #     max_age=COOKIE_MAX_AGE,
    #     httponly=True,
    #     secure=True,
    #     samesite="strict"
    # )

    # # response.set_cookie(
    # #     key=COOKIE_NAME,
    # #     value=session_cookie,
    # #     max_age=COOKIE_MAX_AGE,
    # #     httponly=True,
    # #     secure=True,
    # #     samesite="strict"
    # # )
    # return redirect

## - Disabled
# @app.get("/register", response_class=HTMLResponse)
# async def register_form(request: Request):
#     return templates.TemplateResponse("register.html", {"request": request})




# @app.get("/lookup_table/{user_name}", response_class=HTMLResponse)  # from login.html
# async def login(user_name: str, request: Request):

# -- --- paths - lookup table ------------
@app.get("/lookup_table/{user_name}", response_class=HTMLResponse)
@exception_handler
async def lookup_table(user_name: str, request: Request, scrolldown:bool=False):

    # - check cookie
    try:
        username = check_cookie(request)
        logger.info(f"lookup_table scrolldown {scrolldown} user_name {user_name} username {username}.")
    except HTTPException as e:
        return RedirectResponse(url=f"/login",
                                status_code=status.HTTP_302_FOUND)
        # return Response(content=e.detail, status_code=e.status_code)
    #
    if not (username == user_name or username == ADMIN_USERNAME):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password")

    return get_look_table(request, user_name, scroll_down=scrolldown)


class DeltaForm(BaseModel):
    operation: str = Field(..., description="Operation to perform")
    number: Optional[float] = Field(None, description="Number to add or subtract")

    @validator('operation')
    def validate_operation(cls, v):
        if v not in ['+', '-']:
            raise ValueError('Operation must be either + or -')
        return v


@app.post("/lookup_table/{user_name}")
@exception_handler
async def lookup_table_add_row(request: Request,
                  field0: str = Form(...),
                  field1: str = Form(...),
                  field2: str = Form(...),
                  field3: str = Form(...),
                  field4: str = Form(None), # operation for add
                  field5: str = Form(None), # diff for add
                  action: str = Form(...)):
    # - check cookies
    username = check_cookie(request)

    # - load table
    rows = []
    for row in create_row_iterator(get_path_lookupt(username)):
        if any(row):
            rows.append(row)
        else:
            break
    if rows:
        table_data = rows[1:]
        header = rows[0]

    # - actions
    field0 = int(field0)

    if action in ["save", "delete"] and not (0 <= field0 < len(table_data)):
        return HTTPException(status_code=400, detail="Invalid number format")

    if action == "add":
        # - add row
        if field5:
            form_data = DeltaForm(operation=field4, number=float(field5))
            table_data.append([field1,
                               field2 + form_data.operation + str(form_data.number),
                               field3 + form_data.operation + str(form_data.number)])
        else:
            table_data.append([field1, field2, field3])

    elif action == "save":
        # - modify row
        table_data[field0] = [field1, field2, field3]
    elif action == "delete":
        del table_data[field0]

    xlsx_write(header, table_data, get_path_lookupt(username))

    return RedirectResponse(url=f"/lookup_table/{username}?scrolldown=True",
                            status_code=status.HTTP_302_FOUND)


# -- --- dist_one_table ---------------------------------------

@app.get("/dist_one_table", response_class=HTMLResponse)
@exception_handler
async def dist_one_table(request: Request):
    # - check cookie
    username = check_cookie(request)

    table_data = load_dist_one_table()

    table_data = [[i] + v for i, v in enumerate(table_data)]
    headers = DIST_ONE_TABLE_HEADERS

    return templates.TemplateResponse("dist_one_table.html", {
        "request": request,
        "headers": headers,
        "table_data": table_data,
        "username": username
    })

    # return get_dist_one_table(request, username)



class DistOneTableForm(BaseModel):
    field0: conint(gt=-1)
    field1: str
    field2: str
    field3: str
    action: str

    @validator('action')
    def validate_action(cls, v):
        if v not in ['add', 'save', 'delete', 'email']:
            raise ValueError('action must be one of: add, save, delete')
        return v

    @validator('field1')
    def validate_field1(cls, v):
        if v == '':
            return v
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
            raise ValueError('field1 must be a valid ASCII name for a Python variable')
        return v

    @validator('field2')
    def validate_field2(cls, v):
        if v == '':
            return v
        path = Path(v)
        if not path.is_absolute():
            raise ValueError('Must be an absolute path')
        if not re.match(r'^(/[\w.-]+)+/?$', str(path)):
            raise ValueError('Invalid Linux path format')
        if path.suffix:
            raise ValueError('Must be a directory path, not a file')
        return v

    @validator('field3')
    def validate_field3(cls, v):
        if v == '':
            return v

        emails = parse_emails(v)

        # Regular expression for email validation
        email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

        if not emails:
            raise ValueError('Email list cannot be empty')

        # Check if it's a single email
        for em in emails:
            if not re.match(email_regex, em) or ' ' in em:
                raise ValueError(f'Invalid email address: {v}')

        return v


class DistOneTableEmailForm(BaseModel):
    field0: conint(gt=-1)
    field1: str
    action: str

    @validator('action')
    def validate_action(cls, v):
        if v not in ['add', 'save', 'delete', 'email']:
            raise ValueError('action must be one of: add, save, delete')
        return v

    @validator('field1')
    def validate_field3(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Email can't be empty.")

        emails = parse_emails(v)

        # Regular expression for email validation
        email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

        if not re.match(email_regex, v):
            raise ValueError(f'Invalid email address: {v}')
        else:
            return v


@app.post("/dist_one_table")
@exception_handler
async def dist_one_table_add_row(request: Request,
                                 form_data: DistOneTableForm = Form(...)):
    """ action: add, save, email, delete """
    field0 = form_data.field0
    field1 = form_data.field1
    field2 = form_data.field2
    field3 = form_data.field3
    action = form_data.action

    logger.info(f"/dist_one_table/edit field0 {field0} field1 {field1} field2 {field2} field3 {field3} action {action}")


    # - check cookies
    username = check_cookie(request)
    if username != ADMIN_USERNAME:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password")

    # - load table
    table_data = []
    for row in create_row_iterator(PATH_DIST_ONE_TABLE):
        if any(row):
            table_data.append(row)
        else:
            break

    # - actions
    field0 = int(field0)

    if action in ["save", "delete"] and not (0 <= field0 < len(table_data)):
        return HTTPException(status_code=400, detail="Invalid number format")

    if action == "add":
        # - add row
        logger.info(f"ADD /dist_one_table field0 {field0} field1 {field1} field2 {field2} field3 {field3} action {action}")
        if not any((field1, field2, field3)):
            logger.info(f"ADD /dist_one_table - all fields are empty.")
            return HTTPException(status_code=400, detail=f"All fields are empty at /dist_one_table_add_row.")
        table_data.append([field1, field2, field3])
        if field1:
            create_sftp_user(field1)
        elif field2:
            create_sftp_user(field2.split('/')[-1])

    elif action == "save":
        # - modify row
        table_data[field0] = [field1, field2, field3]
    elif action == "delete":
        del table_data[field0]
    elif action == "email":
        if not field1:
            HTTPException(status_code=400, detail=f"Unknown user name {field1}.")
        return RedirectResponse(url=f"/email_edit/{field1}?admin=True", status_code=status.HTTP_302_FOUND)
    else:
        return HTTPException(status_code=400, detail=f"Wrong action {action}.")

    write_csv_file(PATH_DIST_ONE_TABLE, table_data)
    # get_dist_one_table(request, username, table_data)
    return RedirectResponse(url="/dist_one_table", status_code=status.HTTP_302_FOUND)


# -- --- email_edit -------------------------------------------
# @exception_handler
@app.get("/email_edit/{user_name}", response_class=HTMLResponse)
@exception_handler
async def email_edit(user_name: str, request: Request, admin: bool = False):
    # - check cookie
    username = check_cookie(request)
    if not (username == user_name or username == ADMIN_USERNAME):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password")

    # - get email for user, from loaded dist table
    email_to_edit = dist_one_table_email(user_name)

    if not email_to_edit:
        # return HTTPException(status_code=404, detail=f"No email or user {username}.")
        table_data = [""]
    else:
        table_data = [(i, e) for i, e in enumerate(email_to_edit)]

    if admin:
        back_link = "/dist_one_table"
    else:
        back_link = f"/lookup_table/{user_name}"
    return templates.TemplateResponse("email_edit.html", {
        "request": request,
        "table_data": table_data,
        "username": user_name,
        "back_link": back_link
        # "dist_tab_nav": True if username == "TAP" else False
    })


@app.post("/email_edit/{user_name}")
async def email_edit_add(request: Request,
                         user_name: str,
                         form_data: DistOneTableEmailForm = Form(...)):
    """ action: add, save, delete """
    field0 = form_data.field0
    field1 = form_data.field1
    action = form_data.action

    logger.info(f"/email_edit/{user_name} field0 {field0} field1 {field1}.")

    # - check cookies
    username = check_cookie(request)
    if not (username == user_name or username == ADMIN_USERNAME):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password")

    # - load dist table
    dist_table = load_dist_one_table()

    # - get id of line in table for client
    inum = None
    nname = user_name.lower()
    for i, v in enumerate(dist_table):
        name, sftp, email = v
        if (name and nname == name.lower()) or (sftp and nname in sftp.lower()):
            inum = i
            break

    # - prepare for actions
    # if action in ["save", "delete"] and not (0 <= field0 < len(dist_table)):
    #     return HTTPException(status_code=400, detail="Invalid number format")

    # - actions
    if action == "add":
        # - add row
        logger.info(f"dist_one_table_add ADD field0 {field0} field1 {field1} action {action}")
        if not field1:
            logger.info(f"dist_one_table_add ADD /email_edit_add - email field is empty.")
            return HTTPException(status_code=400, detail=f"All fields are empty at /email_edit_add.")

        dist_table[inum][2] += " " + field1
        logger.info(f"before add {dist_table[inum]}")
        write_csv_file(PATH_DIST_ONE_TABLE, dist_table)
        # dist_table = load_dist_one_table()
        # logger.info(f"after save {dist_table[inum]}")
        return RedirectResponse(url=f"/email_edit/{user_name}", status_code=status.HTTP_302_FOUND)

    elif action == "save":
        # - modify row
        emails = parse_emails(dist_table[inum][2])
        logger.info(f"field0 {field0} dist_table[inum][2] {dist_table[inum][2]}")
        if emails and (0 <= field0 < len(emails)):
            emails[field0] = field1
            dist_table[inum][2] = " ".join(emails)
        else:
            dist_table[inum][2] += " " + field1  # just add

        write_csv_file(PATH_DIST_ONE_TABLE, dist_table)
        return RedirectResponse(url=f"/email_edit/{user_name}", status_code=status.HTTP_302_FOUND)
    elif action == "delete":
        emails = parse_emails(dist_table[inum][2])
        if emails and (0 <= field0 < len(emails)):
            del emails[field0]
            dist_table[inum][2] = " ".join(emails)
            write_csv_file(PATH_DIST_ONE_TABLE, dist_table)
        return RedirectResponse(url=f"/email_edit/{user_name}", status_code=status.HTTP_302_FOUND)
    else:
        return HTTPException(status_code=400, detail=f"Wrong action {action}.")


# @app.post("/register")  # from register.html
# async def register(username: str = Form(...), password: str = Form(...)):
#     if username in users_db:
#         raise HTTPException(status_code=400, detail="Username already registered")
#     hashed_password = get_password_hash(password)
#     users_db[username] = {"username": username, "hashed_password": hashed_password}
#     save_users(users_db)
#     # return RedirectResponse(url="/login", status_code=303)
#     raise HTTPException(status_code=400, detail="User successfully created. You may login.")



# @app.post("/token")  # from login.html
# async def login(form_data: OAuth2PasswordRequestForm = Depends()):
#     user = authenticate_user(form_data.username, form_data.password)
#     if not user:
#         raise HTTPException(status_code=400, detail="Incorrect username or password")
#     return RedirectResponse(url="/table", status_code=303)
#     # return {"access_token": user.username, "token_type": "bearer"}

# -- main -------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
