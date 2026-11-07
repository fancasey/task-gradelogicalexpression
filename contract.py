"""Typed inputs and outputs for the logical expression grading plugin."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    LIST_EXAM = "list_exam"
    GET_SUBMISSION = "get_submission"
    EVALUATE_EXPRESSION = "evaluate_expression"
    PIN_MINIMUM = "pin_minimum"


class Task(Enum):
    LIST_EXAM = "list-exam"
    GRADE_ANSWER = "grade-answer"


class QuestionId(str, Enum):
    LAB_ACCESS = "lab-access"
    BACKUP_POWER = "backup-power"
    RELAY_WARNING = "relay-warning"
    GARDEN_WATERING = "garden-watering"
    PACKAGE_RELEASE = "package-release"


class StudentId(str, Enum):
    STUDENT_01 = "synthetic-01"
    STUDENT_02 = "synthetic-02"
    STUDENT_03 = "synthetic-03"
    STUDENT_04 = "synthetic-04"
    STUDENT_05 = "synthetic-05"


@dataclass
class EmptyInput(Output):
    pass


@dataclass
class Question(Output):
    question_id: QuestionId
    prompt: str


@dataclass
class ExamOutput(Output):
    questions: list[Question]
    student_ids: list[StudentId]


@dataclass
class SelectionInput(Output):
    question_id: Annotated[QuestionId, "Select one question by ID. Ask the user if the question is unspecified."]
    student_id: Annotated[StudentId, "Select one student by ID. Ask the user if the student is unspecified."]


@dataclass
class SubmissionOutput(Output):
    question_id: QuestionId
    student_id: StudentId
    prompt: str
    variables: dict[str, str]
    variable_order: list[str]
    original_expression: str
    reference_outputs: Annotated[list[bool], "False-first row order, with the last variable changing fastest"]


@dataclass
class ExpressionInput(Output):
    question_id: QuestionId
    expression: str


@dataclass
class EvaluationOutput(Output):
    variable_order: list[str]
    outputs: list[bool] | None
    error: str | None


@dataclass
class MinimumOutput(Output):
    submission: SubmissionOutput
    minimum_edits: Annotated[int | None, "Exact minimum edit count, or null if the original cannot be parsed"]


@dataclass
class Counterexample(Output):
    assignment: dict[str, bool]
    actual: bool
    expected: bool


@dataclass
class GradeOutput(Output):
    question_id: QuestionId
    student_id: StudentId
    original_expression: str
    passed: bool
    counterexample: Counterexample | None
    parse_error: str | None
    corrected_expression: str | None
    edit_steps: Annotated[list[str], "Expression after each single edit, ending at the corrected expression"]
    explanation: Annotated[str, "Explain the grade and, when applicable, how the correction fixes the error"]


TOOLS = {
    Tool.LIST_EXAM: (EmptyInput, ExamOutput),
    Tool.GET_SUBMISSION: (SelectionInput, SubmissionOutput),
    Tool.EVALUATE_EXPRESSION: (ExpressionInput, EvaluationOutput),
    Tool.PIN_MINIMUM: (SelectionInput, MinimumOutput),
}
TASKS = {
    Task.LIST_EXAM: (EmptyInput, ExamOutput),
    Task.GRADE_ANSWER: (SelectionInput, GradeOutput),
}
