"""
Shared string constants.

StrEnum members are plain strings, so they store in the database and
serialise to JSON without conversion. Works on Python 3.10 and newer.
"""

import sys
from enum import Enum

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:

    class StrEnum(str, Enum):
        """Minimal backport of enum.StrEnum for Python 3.10."""

        def __str__(self) -> str:
            return str(self.value)


class Mode(StrEnum):
    CLASSICAL = "classical"
    ML = "ml"
    COMPARE = "compare"


class Method(StrEnum):
    CLASSICAL = "classical"
    ML = "ml"


class ResultStatus(StrEnum):
    OK = "ok"
    ROWS_NOT_DETECTED = "rows_not_detected"  # classical found no crop rows
    MODEL_UNAVAILABLE = "model_unavailable"  # ML model not loaded
    FAILED = "failed"
