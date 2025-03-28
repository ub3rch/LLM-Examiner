# Imports section

# Types
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from pydantic import BaseModel, Field
from enum import Enum
from fastapi import Depends
from fastapi.responses import JSONResponse

# Database
from google.cloud import firestore

# Security
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# Fastapi
from fastapi import FastAPI, HTTPException, status



# Database section

# Data models
class User(BaseModel):
    username: str

class UserInDB(User):
    hashed_password: str


# DB initialization
database = firestore.Client.from_service_account_json('./serviceAccountKey.json')
users = database.collection("Users")


# DB operations
async def create_user(user_info: UserInDB):
    # Getting user document from DB
    user_doc = users.document(user_info.username).get()
    # Checking if user exists
    if user_doc.exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    # Hashing password
    user_info.hashed_password = pwd_context.hash(user_info.hashed_password)
    # Writing to DB
    user_doc.set(user_info.model_dump())
    
async def get_user(username: str) -> UserInDB:
    # Getting user document from DB
    user_doc = users.document(username).get()
    # Checking if user exists
    if not user_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not exists")
    # Retruning user
    return UserInDB(**user_doc.to_dict())

async def update_user(user_info: UserInDB):
    # Getting user document from DB
    user_doc = users.document(user_info.username).get()
    # Checking if user exists
    if not user_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not exists")
    # Checking if username stays unchanged
    if user_doc.to_dict()['username']!=user_info.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Username change is not allowed")
    # Update user with new values
    user_doc.update(user_info.model_dump())

def delete_user(username: str):
    # Getting user document from DB
    user_doc = users.document(username).get()
    # Checking if user exists
    if not user_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not exists")
    # Deleting from DB
    user_doc.delete()



# Authentication section

# Constants
SECRET_KEY = "3764ccba1f70d7d904f403d4c16eca09a27e8aadf9427969546a9d95af3467a3"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Data models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str

# Authorization utilities
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
auth = OAuth2PasswordBearer(tokenUrl="auth")

# Authorization operations
async def authorize_user(token: Annotated[str, Depends(auth)])->User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = await get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return User(**user.model_dump())



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
        "description": "Operations with LLM",
    }
]


# Application description and TODO list
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



# Calls section

# User authentication
@app.post("/auth", tags=[Tag.user])
async def log_in(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    # Get user
    user = await get_user(form_data.username)
    
    # Check password correcthess
    if not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create and return token
    access_token_expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {'sub': user.username, 'exp':access_token_expires}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return Token(access_token=encoded_jwt, token_type="bearer")


# User account operations
@app.get("/user", tags=[Tag.user], response_model=User)
async def receive_user_info(user: Annotated[User, Depends(authorize_user)])->User:
    return user

@app.post("/user", dependencies=[], tags=[Tag.user])
async def register_user_accoutn(user_info: UserInDB):
    await create_user(user_info)

@app.patch("/user", dependencies=[], tags=[Tag.user])
async def update_user_account(user: Annotated[User, Depends(authorize_user)]):
    return 0

@app.delete("/user", tags=[Tag.user])
async def delete_user_account(user: Annotated[User, Depends(authorize_user)]):
    await delete_user(user.username)

# TODO: add study log calls
@app.get("/user/{file_id}", tags=[Tag.user])
def receive_material(user: Annotated[User, Depends(authorize_user)]):
    return 0

@app.post("/user/{file_id}", tags=[Tag.user])
def provide_exam(user: Annotated[User, Depends(authorize_user)]):
    return 0


# File operations
@app.get("/files", tags=[Tag.files])
def search_files():
    return 0

@app.post("/files", tags=[Tag.files])
def upload_file(user: Annotated[User, Depends(authorize_user)]):
    return 0

@app.get("/files/{file_id}", tags=[Tag.files])
def check_file(user: Annotated[User, Depends(authorize_user)]):
    return 0

@app.patch("/files/{file_id}", tags=[Tag.files])
def update_file(user: Annotated[User, Depends(authorize_user)]):
    return 0

@app.delete("/files/{file_id}", tags=[Tag.files])
def delete_file(user: Annotated[User, Depends(authorize_user)]):
    return 0


# LLM operations
@app.get("/files/{file_id}/LLMOutcome", tags=[Tag.llm])
def provide_outcomes(user: Annotated[User, Depends(authorize_user)]):
    return 0

@app.patch("/files/{file_id}/LLMOutcome", tags=[Tag.llm])
def approve_outcomes(user: Annotated[User, Depends(authorize_user)]):
    return 0

@app.get("/files/{file_id}/LLMAssesment", tags=[Tag.llm])
def provide_assesment(user: Annotated[User, Depends(authorize_user)]):
    return 0

@app.patch("/files/{file_id}/LLMAssesment", tags=[Tag.llm])
def approve_assesments(user: Annotated[User, Depends(authorize_user)]):
    return 0
