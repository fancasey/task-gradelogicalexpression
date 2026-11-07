"""Parse Boolean expressions and measure structural repairs."""

import re
from itertools import product

BINARY = {"OR": 1, "XOR": 2, "AND": 3}
TOKEN = re.compile(r"\s*([A-Za-z_][A-Za-z_0-9]*|[()]|[^\s])")
MAX_EXPRESSION_LENGTH = 512
MAX_EDIT_STEPS = 16


def parse(expression, variables):
    """Return a tree represented by nested tuples. Parentheses only affect grouping."""
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ValueError(f"Expression exceeds {MAX_EXPRESSION_LENGTH} characters.")
    tokens = iter(TOKEN.findall(expression))
    token = next(tokens, None)

    def advance():
        nonlocal token
        token = next(tokens, None)

    def read(minimum_precedence):
        term = token
        advance()
        if term == "NOT":
            tree = ("NOT", read(4))
        elif term == "(":
            tree = read(1)
            if token != ")":
                raise ValueError("Expected a closing parenthesis.")
            advance()
        elif term in variables:
            tree = (term,)
        else:
            found = "the end of the expression" if term is None else repr(term)
            raise ValueError(f"Expected a variable, NOT, or an opening parenthesis. Found {found}.")

        while BINARY.get(token, 0) >= minimum_precedence:
            operator = token
            advance()
            tree = (operator, tree, read(BINARY[operator] + 1))
        return tree

    if token is None:
        raise ValueError("The answer is blank.")
    tree = read(1)
    if token is not None:
        raise ValueError(f"Unexpected token {token!r}.")
    return tree


def assignments(variables):
    return [dict(zip(variables, row)) for row in product((False, True), repeat=len(variables))]


def evaluate(tree, assignment):
    operator, *children = tree
    if not children:
        return assignment[operator]
    left = evaluate(children[0], assignment)
    if operator == "NOT":
        return not left
    right = evaluate(children[1], assignment)
    if operator == "AND":
        return left and right
    if operator == "OR":
        return left or right
    return left != right


def truth_table(tree, rows):
    return [evaluate(tree, row) for row in rows]


def neighbors(tree, variables):
    """Yield every tree reachable by one structural edit at any position."""
    operator, *children = tree
    yield ("NOT", tree)
    for variable in variables:
        leaf = (variable,)
        for binary in BINARY:
            yield (binary, tree, leaf)
            yield (binary, leaf, tree)

    if not children:
        for variable in variables:
            if variable != operator:
                yield (variable,)
    elif operator == "NOT":
        child = children[0]
        yield child
        for changed in neighbors(child, variables):
            yield ("NOT", changed)
    else:
        left, right = children
        for binary in BINARY:
            if binary != operator:
                yield (binary, left, right)
        if len(left) == 1:
            yield right
        if len(right) == 1:
            yield left
        if len(left) == 3:
            inner, first, second = left
            yield (inner, first, (operator, second, right))
        if len(right) == 3:
            inner, second, third = right
            yield (inner, (operator, left, second), third)
        for changed in neighbors(left, variables):
            yield (operator, changed, right)
        for changed in neighbors(right, variables):
            yield (operator, left, changed)


def minimum_edits(original, variables, reference):
    try:
        start = parse(original, variables)
    except ValueError:
        return None
    rows = assignments(variables)
    frontier = {start}
    seen = {start}
    distance = 0
    while not any(truth_table(tree, rows) == reference for tree in frontier):
        frontier = {next_tree for tree in frontier for next_tree in neighbors(tree, variables)} - seen
        seen.update(frontier)
        distance += 1
    return distance
