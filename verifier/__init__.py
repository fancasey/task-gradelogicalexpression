"""Independently check tool outputs and grade reports against the exam."""

from contract import EvaluationOutput, Task, Tool

from .exam import catalog, question_for, submission_for
from .logic import MAX_EDIT_STEPS, assignments, minimum_edits, neighbors, parse, truth_table


def verdict(valid, message, *, score=None, **details):
    return {"valid": valid, "message": message, "score": float(valid) if score is None else score, "details": details}


def verify_input(tool, value):
    # The contract restricts IDs to the bundled exam and accepts malformed expressions for diagnosis.
    Tool(tool)
    return verdict(True, "Valid input.")


def pin_matches(selection, pinned):
    submission = submission_for(selection)
    return (
        pinned is not None
        and pinned.submission == submission
        and pinned.minimum_edits
        == minimum_edits(submission.original_expression, submission.variable_order, submission.reference_outputs)
    )


def verify_output(tool, input_value, output_value, workspace):
    tool = Tool(tool)
    if tool == Tool.LIST_EXAM:
        matches = output_value == catalog()
    elif tool == Tool.GET_SUBMISSION:
        matches = output_value == submission_for(input_value)
    elif tool == Tool.PIN_MINIMUM:
        matches = pin_matches(input_value, output_value)
    else:
        variables = question_for(input_value.question_id)["variable_order"]
        try:
            outputs = truth_table(parse(input_value.expression, variables), assignments(variables))
        except ValueError as error:
            expected = EvaluationOutput(variables, None, str(error))
        else:
            expected = EvaluationOutput(variables, outputs, None)
        matches = output_value == expected
    return verdict(matches, "Tool output verified." if matches else "Tool output differs from the exam or evaluation.")


def check_grade(output, reference):
    submission = reference.submission
    variables = submission.variable_order
    expected = submission.reference_outputs
    rows = assignments(variables)

    if (output.question_id, output.student_id, output.original_expression) != (
        submission.question_id,
        submission.student_id,
        submission.original_expression,
    ):
        return verdict(False, "The report must identify the selected question, student, and original answer.")
    if not output.explanation.strip():
        return verdict(False, "The report must explain the assessment.")

    try:
        original = parse(submission.original_expression, variables)
    except ValueError as error:
        original = None
        if output.passed or output.parse_error != str(error) or output.counterexample is not None:
            return verdict(False, "The original answer cannot be evaluated. Report the parse error and a fail.")
    else:
        observed = truth_table(original, rows)
        passed = observed == expected
        if output.passed != passed or output.parse_error is not None:
            return verdict(False, "The grade disagrees with the original answer's truth table.")
        if passed:
            if output.counterexample is not None or output.corrected_expression is not None or output.edit_steps:
                return verdict(False, "A passing answer has no counterexample or correction.")
            return verdict(True, "The original answer matches the reference.", minimum_edits=0)
        example = output.counterexample
        if example is None or example.assignment not in rows:
            return verdict(False, "Give a counterexample with values for every variable.")
        index = rows.index(example.assignment)
        if (
            example.actual != observed[index]
            or example.expected != expected[index]
            or example.actual == example.expected
        ):
            return verdict(False, "The counterexample must show the actual and expected values on a mismatching row.")

    if output.corrected_expression is None:
        return verdict(False, "The failing answer needs a corrected expression.")
    try:
        corrected = parse(output.corrected_expression, variables)
    except ValueError as error:
        return verdict(False, f"The correction cannot be parsed. {error}")
    if truth_table(corrected, rows) != expected:
        return verdict(False, "The correction disagrees with the reference truth table.")

    if original is None:
        if output.edit_steps:
            return verdict(False, "A blank or malformed original has no structural edit sequence.")
        return verdict(True, "The parse error and model answer are correct.", minimum_edits=None)

    if len(output.edit_steps) > MAX_EDIT_STEPS:
        return verdict(False, f"Submit at most {MAX_EDIT_STEPS} edit steps.")
    previous = original
    for index, expression in enumerate(output.edit_steps, start=1):
        try:
            current = parse(expression, variables)
        except ValueError as error:
            return verdict(False, f"Edit {index} cannot be parsed. {error}")
        if current == previous or current not in neighbors(previous, variables):
            return verdict(False, f"Edit {index} must make exactly one allowed structural change.")
        previous = current
    if previous != corrected:
        return verdict(False, "The edit sequence must end at the submitted correction.")

    extra = len(output.edit_steps) - reference.minimum_edits
    if extra < 0:
        return verdict(False, "The edit sequence is shorter than the pinned minimum.")
    return verdict(
        extra == 0,
        "The correction matches the pinned minimum." if extra == 0 else f"The correction uses {extra} extra edits.",
        score=max(0.0, 1.0 - 0.25 * extra),
        minimum_edits=reference.minimum_edits,
        edit_count=len(output.edit_steps),
        extra_edits=extra,
    )


def verify_task(task, arguments, output, reference, workspace):
    if Task(task) == Task.LIST_EXAM:
        return verify_output(Tool.LIST_EXAM, arguments, output, workspace)
    if not pin_matches(arguments, reference):
        return verdict(False, "The pinned reference is missing or disagrees with the selected exam record.")
    return check_grade(output, reference)
