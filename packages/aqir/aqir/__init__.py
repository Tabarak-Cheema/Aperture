"""AQIR — Aperture Query Intermediate Representation.

The model never writes SQL. It emits an AQIR plan: a typed JSON object validated
against the Pydantic schema in :mod:`aqir.schema`. :mod:`aqir.compiler` turns a
validated plan into a dialect SQL string via ``sqlglot``, and :mod:`aqir.validator`
runs static and plausibility checks before execution.
"""

from aqir.compiler import compile_plan
from aqir.schema import (
    AQIRPlan,
    Compare,
    Filter,
    Grain,
    JoinPath,
    SortKey,
    TimeRange,
)
from aqir.validator import ValidationError, validate_plan

__all__ = [
    "AQIRPlan",
    "Compare",
    "Filter",
    "Grain",
    "JoinPath",
    "SortKey",
    "TimeRange",
    "ValidationError",
    "compile_plan",
    "validate_plan",
]

__version__ = "0.1.0"
