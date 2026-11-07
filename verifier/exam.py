"""Read the bundled exam for the plugin and verifier."""

import json
from pathlib import Path

from contract import ExamOutput, Question, QuestionId, StudentId, SubmissionOutput

EXAM = Path(__file__).resolve().parents[1] / "examples" / "synthetic-exam.json"


def load_exam():
    return json.loads(EXAM.read_text(encoding="utf-8"))


def catalog():
    data = load_exam()
    return ExamOutput(
        [Question(QuestionId(question["id"]), question["prompt"]) for question in data["questions"]],
        [StudentId(student["student_id"]) for student in data["submissions"]],
    )


def question_for(question_id):
    return next(question for question in load_exam()["questions"] if question["id"] == question_id.value)


def submission_for(selection):
    question = question_for(selection.question_id)
    student = next(
        student for student in load_exam()["submissions"] if student["student_id"] == selection.student_id.value
    )
    return SubmissionOutput(
        selection.question_id,
        selection.student_id,
        question["prompt"],
        question["variables"],
        question["variable_order"],
        student["answers"][question["id"]],
        question["reference_outputs"],
    )
