from __future__ import annotations

from mqtransport.participants import Producer
from pydantic import BaseModel

########################################
# Producers
########################################


class MP_PodFinished(Producer):

    """Pod finish notification"""

    name = "starter.pods.finished"

    class Model(BaseModel):

        # Suitcase
        user_id: str
        project_id: str
        pool_id: str
        fuzzer_id: str
        fuzzer_rev: str
        agent_mode: str
        fuzzer_lang: str
        fuzzer_engine: str
        session_id: str

        # Other
        success: bool
        """ Whether launch was successful or not"""
