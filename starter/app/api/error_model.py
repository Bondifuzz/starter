from pydantic import BaseModel

from .error_codes import *

API_ERROR_MESSAGES = {
    E_NO_ERROR: "No error. Operation successful",
    E_INTERNAL_ERROR: "Internal error occurred. Please, try again later or contact support service",
    E_POOL_NOT_FOUND: "Target resource pool was not found",
    E_POOL_TOO_SMALL: "Target resource pool capacity is too small",
    E_POOL_NO_RESOURCES: "Unable to run fuzzer: not enough CPU/RAM in target resource pool",
    E_POOL_LOCKED: "Target resource pool is locked. Please, try again later, when it will be unlocked",
}


class ErrorModel(BaseModel):
    message: str
    code: int


def error_msg(*error_codes):
    messages = [API_ERROR_MESSAGES[ec] for ec in error_codes]
    return "<br>".join(messages)


def error_model(error_code: int):
    return ErrorModel.construct(
        message=API_ERROR_MESSAGES[error_code],
        code=error_code,
    )


def error_details(error_code: int):
    return {
        "error": {
            "code": error_code,
            "message": API_ERROR_MESSAGES[error_code],
        }
    }


def error_body(error_code: int):
    return {
        "code": error_code,
        "message": API_ERROR_MESSAGES[error_code],
    }
