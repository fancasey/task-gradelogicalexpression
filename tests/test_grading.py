from dataclasses import replace

import pytest

from contract import Counterexample, EmptyInput, ExpressionInput, GradeOutput, QuestionId, SelectionInput, StudentId
from plugin.grading import evaluate_expression, get_submission, list_exam, pin_minimum
from verifier import verify_output, verify_task
from verifier.exam import question_for
from verifier.logic import assignments

MINIMUMS = [
    [0, 0, 0, 0, 0],
    [1, 1, 1, 2, 1],
    [None, None, 0, 0, 0],
    [0, 1, 0, 2, 0],
    [1, 0, 1, 0, 1],
]
REPAIRS = {
    (StudentId.STUDENT_02, QuestionId.LAB_ACCESS): ["B AND (S OR E)"],
    (StudentId.STUDENT_02, QuestionId.BACKUP_POWER): ["NOT M AND R"],
    (StudentId.STUDENT_02, QuestionId.RELAY_WARNING): ["L XOR R"],
    (StudentId.STUDENT_02, QuestionId.GARDEN_WATERING): ["F AND D AND R", "F AND D AND NOT R"],
    (StudentId.STUDENT_02, QuestionId.PACKAGE_RELEASE): ["S AND A OR E"],
    (StudentId.STUDENT_04, QuestionId.BACKUP_POWER): ["NOT M AND R"],
    (StudentId.STUDENT_04, QuestionId.GARDEN_WATERING): ["F AND NOT R", "(F AND D) AND NOT R"],
    (StudentId.STUDENT_05, QuestionId.LAB_ACCESS): ["B AND (S OR E)"],
    (StudentId.STUDENT_05, QuestionId.RELAY_WARNING): ["L XOR R"],
    (StudentId.STUDENT_05, QuestionId.PACKAGE_RELEASE): ["(S AND A) OR E"],
}


def make_report(selection):
    submission = get_submission(selection)
    original = submission.original_expression
    evaluated = evaluate_expression(ExpressionInput(selection.question_id, original))
    correct = evaluated.outputs == submission.reference_outputs
    counterexample = None
    correction = None
    steps = []
    if evaluated.error:
        correction = question_for(selection.question_id)["reference_expression"]
    elif not correct:
        rows = assignments(submission.variable_order)
        for row, actual, expected in zip(rows, evaluated.outputs, submission.reference_outputs, strict=True):
            if actual != expected:
                counterexample = Counterexample(row, actual, expected)
                break
        steps = REPAIRS[selection.student_id, selection.question_id]
        correction = steps[-1]
    return GradeOutput(
        selection.question_id,
        selection.student_id,
        original,
        correct,
        counterexample,
        evaluated.error,
        correction,
        steps,
        "Assessment with supporting evidence.",
    )


@pytest.mark.parametrize("question", QuestionId)
@pytest.mark.parametrize("student", StudentId)
def test_all_exam_selections(student, question):
    selection = SelectionInput(question, student)
    pinned = pin_minimum(selection)
    expected = MINIMUMS[list(StudentId).index(student)][list(QuestionId).index(question)]
    assert pinned.minimum_edits == expected
    assert verify_output("pin_minimum", selection, pinned, ".")["valid"]
    report = make_report(selection)
    assert report.passed == (expected == 0)
    verdict = verify_task("grade-answer", selection, report, pinned, ".")
    assert verdict["valid"] and verdict["score"] == 1
    assert verdict["details"]["minimum_edits"] == expected


def test_catalog_lists_every_pair():
    result = list_exam(EmptyInput())
    assert [q.question_id for q in result.questions] == list(QuestionId)
    assert result.student_ids == list(StudentId)
    assert verify_task("list-exam", EmptyInput(), result, None, ".")["valid"]


@pytest.mark.parametrize("question", QuestionId)
def test_reference_expression_matches_all_rows(question):
    row = question_for(question)
    result = evaluate_expression(ExpressionInput(question, row["reference_expression"]))
    assert result.error is None
    assert result.outputs == row["reference_outputs"]


def test_garden_and_package_tables_match_the_scenario_rules():
    garden = question_for(QuestionId.GARDEN_WATERING)
    garden_rows = assignments(garden["variable_order"])
    assert [row for row, waters in zip(garden_rows, garden["reference_outputs"], strict=True) if waters] == [
        {"F": True, "D": True, "R": False}
    ]
    release = question_for(QuestionId.PACKAGE_RELEASE)
    release_rows = assignments(release["variable_order"])
    for row, releases in zip(release_rows, release["reference_outputs"], strict=True):
        assert releases == (row["E"] or (row["S"] and row["A"]))


@pytest.mark.parametrize(
    ("expression", "error"),
    [
        ("", "blank"),
        (" \t ", "blank"),
        ("B AND (S OR E", "closing parenthesis"),
        ("B AND", "end of the expression"),
        ("B AND Q", "'Q'"),
        ("B S", "Unexpected token"),
        ("B + E", "Unexpected token"),
        ("B OR E)", "Unexpected token"),
        ("NOT " * 129 + "B", "512 characters"),
    ],
)
def test_bad_syntax(expression, error):
    arguments = ExpressionInput(QuestionId.LAB_ACCESS, expression)
    result = evaluate_expression(arguments)
    assert result.outputs is None and error in result.error
    assert verify_output("evaluate_expression", arguments, result, ".")["valid"]


def test_operator_precedence_and_whitespace():
    def values(expression):
        return evaluate_expression(ExpressionInput(QuestionId.LAB_ACCESS, expression)).outputs

    assert values(" NOT B AND S XOR E OR B ") == values("(((NOT B) AND S) XOR E) OR B")
    assert values("B AND S OR E") != values("B AND (S OR E)")


@pytest.fixture
def relay_failure():
    selection = SelectionInput(QuestionId.RELAY_WARNING, StudentId.STUDENT_02)
    return selection, make_report(selection), pin_minimum(selection)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"passed": True}, "grade disagrees"),
        ({"original_expression": "L XOR R"}, "original answer"),
        ({"counterexample": Counterexample({"L": False, "R": False}, False, False)}, "mismatching row"),
        ({"counterexample": Counterexample({"L": True}, True, False)}, "every variable"),
        ({"corrected_expression": "L AND R"}, "correction disagrees"),
        ({"corrected_expression": "(L XOR R"}, "cannot be parsed"),
        ({"edit_steps": []}, "must end"),
        ({"edit_steps": ["(L OR R)", "L XOR R"]}, "exactly one"),
        ({"edit_steps": ["NOT (L XOR R)", "L XOR R"]}, "exactly one"),
        ({"edit_steps": ["L AND R"]}, "must end"),
    ],
)
def test_verifier_rejects_invalid_reports(relay_failure, changes, message):
    selection, report, pinned = relay_failure
    verdict = verify_task("grade-answer", selection, replace(report, **changes), pinned, ".")
    assert not verdict["valid"] and verdict["score"] == 0
    assert message in verdict["message"]


@pytest.mark.parametrize("extra", range(1, 6))
def test_correct_but_nonminimal_repairs(relay_failure, extra):
    selection, report, pinned = relay_failure
    # Each detour is a distinct allowed operator replacement. It costs one step.
    detours = (["L AND R", "L OR R"] * 3)[:extra]
    report = replace(report, edit_steps=[*detours, "L XOR R"])
    result = verify_task("grade-answer", selection, report, pinned, ".")
    assert not result["valid"]
    assert result["score"] == max(0, 1 - 0.25 * extra)
    assert result["details"] == {"minimum_edits": 1, "edit_count": 1 + extra, "extra_edits": extra}


def test_alternative_minimal_correction_and_harmless_parentheses():
    selection = SelectionInput(QuestionId.GARDEN_WATERING, StudentId.STUDENT_04)
    report = make_report(selection)
    report = replace(
        report,
        edit_steps=["F AND (D AND R)", "F AND (D AND NOT R)"],
        corrected_expression=" (( F AND (D AND NOT R) )) ",
    )
    assert verify_task("grade-answer", selection, report, pin_minimum(selection), ".")["valid"]


def test_rejects_missing_or_tampered_reference(relay_failure):
    selection, report, pinned = relay_failure
    for bad in (
        None,
        replace(pinned, minimum_edits=2),
        replace(pinned, submission=replace(pinned.submission, reference_outputs=[False] * 4)),
    ):
        assert not verify_task("grade-answer", selection, report, bad, ".")["valid"]
    assert not verify_output("pin_minimum", selection, replace(pinned, minimum_edits=2), ".")["valid"]


def test_parse_failure_still_needs_correct_model_answer():
    selection = SelectionInput(QuestionId.LAB_ACCESS, StudentId.STUDENT_03)
    report = make_report(selection)
    pinned = pin_minimum(selection)
    assert not verify_task("grade-answer", selection, replace(report, parse_error=None), pinned, ".")["valid"]
    assert not verify_task("grade-answer", selection, replace(report, corrected_expression="B"), pinned, ".")["valid"]
    assert not verify_task(
        "grade-answer", selection, replace(report, edit_steps=[report.corrected_expression]), pinned, "."
    )["valid"]
