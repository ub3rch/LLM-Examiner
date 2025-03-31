# Imports section

# Types
from datetime import datetime, timedelta, timezone
from typing import Annotated
from pydantic import BaseModel
from enum import Enum
from fastapi import Depends, Body

# Database
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# Security
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# Fastapi
from fastapi import FastAPI, HTTPException, status, Query



# Database section

# Data models
class UserInfo(BaseModel):
    username: str
    studied_files: dict[str,int] = {}

class UserInDB(UserInfo):
    hashed_password: str

class FileInDB(BaseModel):
    filename: str
    author: str = ''
    tags: list[str] = []

class FileInfo(FileInDB):
    id: str

class FileFilters(BaseModel):
    name: str | None = None
    author: str | None = None
    tags: list[str] | None = None


# DB initialization
database = firestore.Client.from_service_account_json('./serviceAccountKey.json')
users = database.collection("Users")
files = database.collection("Files")


# DB operations
# Users
async def create_user(user_info: UserInDB):
    # Getting user document from DB
    user_ref = users.document(user_info.username)
    user_doc = user_ref.get()
    # Checking if user exists
    if user_doc.exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    # Hashing password
    user_info.hashed_password = pwd_context.hash(user_info.hashed_password)
    # Writing to DB
    user_ref.set(user_info.model_dump())
    
async def get_user(username: str) -> UserInDB:
    # Getting user document from DB
    user_ref = users.document(username)
    user_doc = user_ref.get()
    # Checking if user exists
    if not user_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not exists")
    # Retruning user
    return UserInDB(**user_doc.to_dict())

async def update_user(user_info: UserInDB):
    # Getting user document from DB
    user_ref = users.document(username)
    user_doc = user_ref.get()
    # Checking if user exists
    if not user_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not exists")
    # Checking if username stays unchanged
    if user_doc.to_dict()['username']!=user_info.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Username change is not allowed")
    # Update user with new values
    user_ref.update(user_info.model_dump())

async def delete_user(username: str):
    # Getting user document from DB
    user_ref = users.document(username)
    user_doc = user_ref.get()
    # Checking if user exists
    if not user_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not exists")
    # Deleting from DB
    user_ref.delete()

async def log_user_study(username:str, file_id: str, status_code: int):
    # Getting user document from DB
    user_ref = users.document(username)
    user_doc = user_ref.get()
    # Checking if user exists
    if not user_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not exists")
    # Getting file document from DB
    file_ref = files.document(file_id)
    file_doc = file_ref.get()
    # Checking if file exists
    if not user_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File does not exists")
    user_info = UserInfo(**user_doc.to_dict())
    user_info.studied_files[file_id] = status_code
    user_ref.update(user_info.model_dump())


# Files
async def create_file_db(file_info: FileInDB)->str:
    # Creating file document in DB
    file_ref = files.document()
    # Filling document
    file_ref.set(file_info.model_dump())
    return file_ref.id

async def get_file_db(file_id: str)->FileInDB:
    # Getting file document from DB
    file_ref = files.document(file_id)
    file_doc = file_ref.get()
    # Checking if file exists
    if not user_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File does not exists")
    return FileInDB(**file_doc.to_dict())

async def update_file_db(file_info: FileInfo):
    # Getting file document from DB
    file_ref = files.document(file_info.id)
    file_doc = file_ref.get()
    # Checking if current user can delete the file
    if not file_info.author == file_doc.to_dict()['author']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User cannot change this file")
    # Checking if file exists
    if not file_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File does not exists")
    file_ref.update(FileInDB(**file_info.model_dump()).model_dump())

async def delete_file_db(file_id: str, cur_user: str):
    # Getting file document from DB
    file_ref = files.document(file_id)
    file_doc = file_ref.get()
    # Checking if current user can delete the file
    if not cur_user == file_doc.to_dict()['author']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User cannot delete this file")
    # Checking if file exists
    if not file_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File does not exists")
    # Deleting file
    file_ref.delete()

async def convert_query_to_list(query)->list[FileInfo]:
    result = []
    for file in query:
        result.append(FileInfo(**file.to_dict(), id=str(file.id)))
    return result



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
async def authorize_user(token: Annotated[str, Depends(auth)])->UserInfo:
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
    return UserInfo(**user.model_dump())



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

* **Check your account**
* **Create account**
* **Update account**
* **Delete account**
* **Study material** (_not implemented_)
* **Try to pass assesment for material** (_not implemented_)

## Files

File operations:

* **Search for files**
* **Uploas files**
* **Update files**
* **Delete files**
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
# Get user info
@app.get("/user", tags=[Tag.user], response_model=UserInfo)
async def receive_user_info(user: Annotated[UserInfo, Depends(authorize_user)])->UserInfo:
    return user

# Register new user
@app.post("/user", dependencies=[], tags=[Tag.user])
async def register_user_accoutn(user_info: UserInDB):
    await create_user(user_info)

# Update user info
@app.patch("/user", dependencies=[], tags=[Tag.user])
async def update_user_account(user: Annotated[UserInfo, Depends(authorize_user)]):
    return 0

# Delete user account
@app.delete("/user", tags=[Tag.user])
async def delete_user_account(user: Annotated[UserInfo, Depends(authorize_user)]):
    await delete_user(user.username)

# Log study process to user
@app.get("/user/{file_id}", tags=[Tag.user])
async def study_material(
    user: Annotated[UserInfo, Depends(authorize_user)],
    file_id: str
):
    await log_user_study(user.username, file_id, -1)

# Log passed assesment to user
@app.post("/user/{file_id}", tags=[Tag.user])
async def prove_studied_material(
    user: Annotated[UserInfo, Depends(authorize_user)],
    file_id: str,
    assesment_score: Annotated[int, Body()]
):
    await log_user_study(user.username, file_id, assesment_score)



# File operations
@app.get("/files", tags=[Tag.files])
async def search_files(filter: Annotated[FileFilters, Query()])->list[FileInfo]:
    query = files.where(filter=FieldFilter('filename', '>=', ''))
    if filter.name:
        query = query.where(filter=FieldFilter('filename', '==', filter.name))
    if filter.author:
        query = query.where(filter=FieldFilter('author', '==', filter.author))
    if filter.tags:
        query = query.where(filter=FieldFilter('tags', 'array_contains_any', filter.tags))
    return await convert_query_to_list(query.stream())

@app.post("/files", tags=[Tag.files])
async def upload_file(
    user: Annotated[UserInfo, Depends(authorize_user)],
    file_info: FileInDB
)->str:
    file_info.author = user.username
    return await create_file_db(file_info)

@app.patch("/files/{file_id}", tags=[Tag.files])
async def update_file(
    user: Annotated[UserInfo, Depends(authorize_user)],
    file_id: str,
    file_info: FileInDB
):
    file_info.author = user.username
    file_info = FileInfo(**file_info.model_dump(), id=file_id)
    await update_file_db(file_info)

@app.delete("/files/{file_id}", tags=[Tag.files])
async def delete_file(
    user: Annotated[UserInfo, Depends(authorize_user)],
    file_id: str
):
    await delete_file_db(file_id, user.username)
