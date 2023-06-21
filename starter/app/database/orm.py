from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ORMLaunch(BaseModel):

    id: Optional[str]
    exp_date: str

    fuzzer_id: str
    fuzzer_rev: str
    fuzzer_engine: str
    agent_mode: str
    fuzzer_lang: str
    session_id: str
    project_id: str
    user_id: str

    start_time: str
    finish_time: str
    exit_reason: str
    agent_logs: Optional[str]
    sandbox_logs: Optional[str]


class Paginator:
    def __init__(self, pg_num: int, pg_size: int):
        self.pg_num = pg_num
        self.pg_size = pg_size
        self.offset = pg_num * pg_size
        self.limit = pg_size
