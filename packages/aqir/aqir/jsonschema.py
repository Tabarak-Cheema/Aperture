"""Export the AQIR JSON schema and a GBNF grammar for constrained decoding.

The LLM's response_format is set to this JSON schema at call time, so the model
can only emit a well-formed AQIR plan. For local models via ``llama.cpp`` we
also emit a GBNF grammar that enforces the same shape at the token level.
"""
from __future__ import annotations

import json
from pathlib import Path

from aqir.schema import AQIRPlan


def json_schema() -> dict:
    """Return the JSON schema for :class:`AQIRPlan`."""
    return AQIRPlan.model_json_schema()


def dump_json_schema(path: str | Path) -> None:
    Path(path).write_text(json.dumps(json_schema(), indent=2, sort_keys=True))


def gbnf_grammar() -> str:
    """A minimal GBNF grammar matching AQIR.

    This is deliberately small; the Pydantic validator is the source of truth.
    The grammar rejects most malformed structures early so local inference does
    not waste tokens on invalid branches.
    """
    return r'''
root   ::= "{" ws metrics (ws "," ws dims)? (ws "," ws filters)? (ws "," ws time)? (ws "," ws sort)? (ws "," ws limit)? ws "}"
metrics::= "\"metrics\"" ws ":" ws strarr
dims   ::= "\"dimensions\"" ws ":" ws strarr
filters::= "\"filters\"" ws ":" ws farr
time   ::= "\"time\"" ws ":" ws tobj
sort   ::= "\"sort\"" ws ":" ws sarr
limit  ::= "\"limit\"" ws ":" ws int

strarr ::= "[" ws (str (ws "," ws str)*)? ws "]"
farr   ::= "[" ws (fobj (ws "," ws fobj)*)? ws "]"
sarr   ::= "[" ws (sobj (ws "," ws sobj)*)? ws "]"

fobj   ::= "{" ws "\"dim\"" ws ":" ws str ws "," ws "\"op\"" ws ":" ws str (ws "," ws "\"value\"" ws ":" ws val)? ws "}"
sobj   ::= "{" ws "\"by\"" ws ":" ws str ws "," ws "\"dir\"" ws ":" ws str ws "}"
tobj   ::= "{" ws "\"dim\"" ws ":" ws str (ws "," ws "\"range\"" ws ":" ws str)? (ws "," ws "\"grain\"" ws ":" ws str)? ws "}"

val    ::= str | int | number | bool | strarr
str    ::= "\"" ([^"\\] | "\\" .)* "\""
int    ::= "-"? [0-9]+
number ::= "-"? [0-9]+ ("." [0-9]+)?
bool   ::= "true" | "false"
ws     ::= [ \t\n]*
'''.strip()


__all__ = ["dump_json_schema", "gbnf_grammar", "json_schema"]
