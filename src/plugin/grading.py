"""Read the exam, evaluate an expression, and pin the private grading reference."""

from contract import EvaluationOutput, MinimumOutput
from verifier.exam import catalog, question_for, submission_for
from verifier.logic import assignments, minimum_edits, parse, truth_table


def list_exam(arguments):
    return catalog()


def get_submission(arguments):
    return submission_for(arguments)


def evaluate_expression(arguments):
    variables = question_for(arguments.question_id)["variable_order"]
    try:
        tree = parse(arguments.expression, variables)
    except ValueError as error:
        return EvaluationOutput(variables, None, str(error))
    return EvaluationOutput(variables, truth_table(tree, assignments(variables)), None)


def pin_minimum(arguments):
    submission = submission_for(arguments)
    return MinimumOutput(
        submission,
        minimum_edits(submission.original_expression, submission.variable_order, submission.reference_outputs),
    )
