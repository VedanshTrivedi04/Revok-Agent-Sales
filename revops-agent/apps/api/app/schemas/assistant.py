"""Riddhi, the workspace assistant: plain-language questions about the caller's own organization.
Every number in an answer is computed from the operational tables at request time; nothing is
generated or stored."""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

ParamKey = Literal["min_score", "days", "limit"]


class AssistantParam(BaseModel):
    """One adjustable value of a question, with the range the API accepts."""

    key: ParamKey
    label: str
    default: int
    min: int
    max: int


class AssistantQuestion(BaseModel):
    id: str
    text: str  # the question with its default values filled in
    params: list[AssistantParam]


class AssistantCatalog(BaseModel):
    questions: list[AssistantQuestion]


class AssistantAskIn(BaseModel):
    """Either a typed question, or a catalog question by id (optionally with its values changed)."""

    question: str | None = Field(default=None, min_length=1, max_length=500)
    question_id: str | None = None
    params: dict[ParamKey, int] = {}

    @model_validator(mode="after")
    def _one_of(self) -> Self:
        if (self.question is None) == (self.question_id is None):
            raise ValueError("send exactly one of 'question' or 'question_id'")
        return self


class AnswerRow(BaseModel):
    """A record behind the answer; the ids let the UI link to it."""

    title: str
    detail: str | None = None
    account_id: UUID | None = None
    finding_id: UUID | None = None
    card_id: UUID | None = None


class AssistantAnswer(BaseModel):
    # not_found = the records were searched and nothing in them answers the question
    status: Literal["answered", "unsupported", "not_found"]
    question_id: str | None = None
    params: dict[ParamKey, int] = {}  # the values the answer was computed with
    interpreted_as: str | None = None  # the catalog question, with those values, that was answered
    text: str
    # True = `text` was written by the model from the records in `rows` (and checked against
    # them); False = it was built by code from query results.
    generated: bool = False
    basis: str | None = None  # how the numbers were worked out
    rows: list[AnswerRow] = []
    total: int = 0  # matching records; `rows` holds at most `limit` of them
    suggestions: list[AssistantQuestion] = []  # what can be asked, when the question is unsupported
    as_of: datetime
