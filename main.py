from fastapi import FastAPI
from pydantic import BaseModel


class LogInItem(BaseModel):
    login: str
    password: str


app=FastAPI()

@app.get("/authentication/")
async def log_in(login_data: LogInItem) -> int:
    return 0

@app.post("/authentication/")
async def register(reg_data: LogInItem) -> int:
    return 0
