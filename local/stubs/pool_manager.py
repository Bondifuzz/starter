# Run: python -m uvicorn pool_manager:app --host 127.0.0.1 --port 8089

from fastapi import FastAPI
from pydantic import BaseModel


class ErrorModel(BaseModel):
    code: int
    message: str


class ListResultModel(BaseModel):
    pg_num: int
    pg_size: int
    items: list


class ListResponseModel(BaseModel):
    result: ListResultModel


class ResourcePoolModel(BaseModel):
    id: str
    cpu: int
    ram: int


app = FastAPI()


@app.get("/api/v1/pools")
async def list_pools():
    return ListResponseModel.construct(
        result=ListResultModel(
            pg_num=0,
            pg_size=100,
            items=[
                ResourcePoolModel(id="1111", cpu=2000, ram=4000),
            ],
        )
    )
