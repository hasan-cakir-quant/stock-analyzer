"""Registry of financial-statement parsers.

Add a new parser by writing a module under `app/services/imports/` and
appending its `ParserSpec` here. The frontend lists every entry in
`available_parsers()` so the user can pick one before uploading.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.services.imports import sec_edgar_all
from app.services.imports.types import ImportPreview

ParseFn = Callable[[str], ImportPreview]


@dataclass(frozen=True, slots=True)
class ParserSpec:
    id: str
    source: str
    statement: str  # one of STATEMENT_TYPES
    label: str
    parse: ParseFn


def _spec(module) -> ParserSpec:
    return ParserSpec(
        id=module.PARSER_ID,
        source=module.SOURCE,
        statement=module.STATEMENT,
        label=module.LABEL,
        parse=module.parse,
    )


_PARSERS: list[ParserSpec] = [
    _spec(sec_edgar_all),
]


def available_parsers() -> list[ParserSpec]:
    return list(_PARSERS)


def get_parser(parser_id: str) -> ParserSpec | None:
    return next((p for p in _PARSERS if p.id == parser_id), None)
