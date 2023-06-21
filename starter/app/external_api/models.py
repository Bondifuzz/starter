from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

########################################


class ErrorModel(BaseModel):
    code: int
    message: str


class ListResultModel(BaseModel):
    pg_num: int
    pg_size: int
    items: list


class ListResponseModel(BaseModel):
    result: ListResultModel


########################################


class ORMPoolHealth(str, Enum):
    ok = "Ok"
    warning = "Warning"
    error = "Error"


class PMGRPoolNode(BaseModel):
    name: str
    cpu: int
    ram: int


class PMGRPoolRsAvail(BaseModel):
    cpu_total: int
    ram_total: int
    node_count: int
    nodes: List[PMGRPoolNode]


class PMGRNodeGroup(BaseModel):
    node_cpu: int
    node_ram: int
    node_count: int


class PMGROperationType(str, Enum):
    create = "Create"
    update = "Update"
    delete = "Delete"


class PMGROperation(BaseModel):
    type: PMGROperationType
    scheduled_for: str
    yc_operation_id: Optional[str]
    error_msg: Optional[str]


class PMGRPool(BaseModel):
    id: str
    name: str
    description: str
    user_id: Optional[str]
    exp_date: Optional[str]
    node_group: PMGRNodeGroup
    operation: Optional[PMGROperation]
    health: ORMPoolHealth
    created_at: str
    rs_avail: PMGRPoolRsAvail
