import sys
import json
from passlib.context import CryptContext
from pydantic import BaseModel

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


def get_password_hash(password):
    return pwd_context.hash(password)


def create_or_change_user(username, password):
    hashed_password = get_password_hash(password)
    users_db[username] = {"username": username, "hashed_password": hashed_password}
    save_users(users_db)

def check_user_exists(username):
    return username in users_db



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python change_user.py <username> [password]")
        sys.exit(1)

    username = sys.argv[1]

    if len(sys.argv) == 2:
        # Check if user exists
        if check_user_exists(username):
            print(f"User '{username}' exists.")
        else:
            print(f"User '{username}' does not exist.")
    elif len(sys.argv) == 3:
        # Create or change user
        password = sys.argv[2]
        create_or_change_user(username, password)
        action = "changed" if check_user_exists(username) else "created"
        print(f"User '{username}' has been {action}.")
    else:
        print("Too many arguments. Usage: python change_user.py <username> [password]")
        sys.exit(1)
