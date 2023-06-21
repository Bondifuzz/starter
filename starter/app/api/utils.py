from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from devtools import debug

if TYPE_CHECKING:
    from .error_model import ErrorModel


def filter_sensitive_data(output: str):

    #
    # Filter output of devtools
    # Inspect [key='value'] entries
    #

    pattern = (
        r"(password|token)"  # possible keys
        r"([\s=]+)"  # delimeters (space and '=')
        r"'(.+)'"  # any value
    )

    # Final result: [key='<REDACTED>']
    output = re.sub(pattern, r"\1\2'<REDACTED>'", output)

    #
    # Filter dictionaries
    # Inspect {'key': 'value'} entries
    #

    pattern = (
        r"('password|token')"  # possible keys
        r"([\s:]+)"  # delimeters (space and ':')
        r"'(.+)'"  # any value
    )

    # Final result: {'key': '<REDACTED>'}
    output = re.sub(pattern, r"\1\2'<REDACTED>'", output)

    return output


def log_operation_debug_info_to(
    logger_name: str,
    operation: str,
    info: Any,
):
    logger = logging.getLogger(logger_name)
    if not logger.isEnabledFor(logging.DEBUG):
        return

    text = "Debug info for operation '%s':\n%s"
    output = debug.format(info).str(highlight=True)
    redacted_output = filter_sensitive_data(output)
    logger.debug(text, operation, redacted_output)


def log_operation_success_to(
    logger_name: str,
    operation: str,
    **kwargs,
):
    logger = logging.getLogger(logger_name)
    kw_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
    logger.info("[OK] Operation='%s', %s", operation, kw_str)


def log_operation_error_to(
    logger_name: str,
    operation: str,
    error: ErrorModel,
    **kwargs,
):
    logger = logging.getLogger(logger_name)
    kw_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])

    msg = "[FAILED] Operation='%s', reason='%s', %s"
    logger.info(msg, operation, error.message, kw_str)


def pg_size_settings():
    return {
        "ge": 10,  # Minimal count of records in one page
        "le": 200,  # Maximum count of records in one page
        "default": 100,  # Default count of records in one page
    }


def pg_num_settings():
    return {
        "ge": 0,  # Minimal number of page
        "default": 0,  # Default number of page
    }


def max_length(value: int):
    return {
        "min_length": 1,  # Minimal data length
        "max_length": value,  # Maximum data length
    }
