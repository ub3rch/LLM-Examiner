# Imports section

# Types
from datetime import datetime, timedelta, timezone
from typing import Annotated
from pydantic import BaseModel
from enum import Enum
from fastapi import Depends

# Security
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# Fastapi
from fastapi import FastAPI, HTTPException, status



# Database operations section
from google.cloud import firestore
db = firestore.Client.from_service_account_json('./serviceAccountKey.json')

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)



# Authentication section
SECRET_KEY = "3764ccba1f70d7d904f403d4c16eca09a27e8aadf9427969546a9d95af3467a3"
ALGORITHM = "HS256"
ACESS_TOKEN_EXPIRE_MINUTES = 60

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str

class User(BaseModel):
    username: str
    email: str | None = None

class UserInDB(User):
    hashed_password: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
auth = OAuth2PasswordBearer(tokenUrl="auth")

def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not pwd_context.verify(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(auth)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user



# Metadata section

# Tags metadata
class Tag(Enum):
    user = "Users"
    files = "Files"
    llm = "LLM"

tags_metadata = [
    {
        "name": Tag.user,
        "description": "Operations with users and login logic",
    }, {
        "name": Tag.files,
        "description": "Operations with files",
    }, {
        "name": Tag.llm,
        "description": "Operations with lLM",
    }
]


# Application description
description = """
## Users

User account operations:

* **Check your account** (_not implemented_)
* **Create account** (_not implemented_)
* **Update account** (_not implemented_)
* **Delete account** (_not implemented_)

* **Study material** (_not implemented_)
* **Try to pass assesment for material** (_not implemented_)

## Files

File operations:

* **Search for files** (_not implemented_)
* **Uploas files** (_not implemented_)
* **Watch files** (_not implemented_)
* **Update files** (_not implemented_)
* **Delete files** (_not implemented_)

## LLM

LLM operations:

* **Ask LLM for material outcomes** (_not implemented_)
* **Upload edited and approved outcomes** (_not implemented_)
* **Ask LLM for material assesments** (_not implemented_)
* **Upload edited and approved assesments** (_not implemented_)
"""


# Application itself
app=FastAPI(
    title="LLM Examiner",
    description=description,
    openapi_tags=tags_metadata,
    summary="Teach and study with LLM",
    version="0.0.1"
)



# Implementation section

# User authentication
@app.post("/token", tags=[Tag.user])
async def log_in(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


# User account operations
@app.get("/user", tags=[Tag.user])
def user_info(): return 0

@app.post("/user", tags=[Tag.user])
def register_user(): return 0

@app.patch("/user", tags=[Tag.user])
def update_user(): return 0

@app.delete("/user", tags=[Tag.user])
def delete_user(): return 0

@app.get("/user/{file_id}", tags=[Tag.user])
def receive_material(): return 0

@app.post("/user/{file_id}", tags=[Tag.user])
def provide_exam(): return 0


# File operations
@app.get("/files", tags=[Tag.files])
def search_files(): return 0

@app.post("/files", tags=[Tag.files])
def upload_file(): return 0

@app.get("/files/{file_id}", tags=[Tag.files])
def check_file(): return 0

@app.patch("/files/{file_id}", tags=[Tag.files])
def update_file(): return 0

@app.delete("/files/{file_id}", tags=[Tag.files])
def delete_file(): return 0


# LLM operations
@app.get("/files/{file_id}/LLMOutcome", tags=[Tag.llm])
def provide_outcomes(): return 0

@app.patch("/files/{file_id}/LLMOutcome", tags=[Tag.llm])
def approve_outcomes(): return 0

@app.get("/files/{file_id}/LLMAssesment", tags=[Tag.llm])
def provide_assesment(): return 0

@app.patch("/files/{file_id}/LLMAssesment", tags=[Tag.llm])
def approve_assesments(): return 0
