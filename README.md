# Logical Expression Grading

Select one question and one student. The grading agent compares the student's
Boolean expression with the reference truth table. It gives a pass or fail and,
for a parseable wrong answer, shows a counterexample and proposes a repair. A
deterministic verifier checks both the assessment and the repair.

The five scenarios, reference answers, and five student submissions in
[`src/plugin/synthetic-exam.json`](src/plugin/synthetic-exam.json) were synthesized
for this project. They contain no real student work.

## Tools

| Tool | Purpose |
|---|---|
| `list_exam` | Lists question IDs, prompts, and student IDs. |
| `get_submission` | Reads the selected question, variable definitions, exact student expression, and reference truth table. |
| `evaluate_expression` | Returns an expression's output on every input row, or a specific parse error. |
| `pin_minimum` | Pins the selected submission and its exact minimum repair count. NanoAgent calls it privately before grading. |

### Tasks

| Task | Runner | Purpose |
|---|---|---|
| `list-exam` | Tool | Shows the exam and lets the user choose a student for a question. |
| `grade-answer` | Agent | Takes one question ID and one student ID. It evaluates the orviginal, explains the grade, and checks a proposed correction before submitting. The verifier uses the private reference from `pin_minimum`. |

In the plugin chat, ask “List the exam,” then choose a student under a question
or ask “Grade synthetic-04 on garden-watering.”

### Grading and repair rules

Truth-table rows are ordered false first, with the last variable in
`variable_order` changing fastest. The notation uses uppercase variables and
`NOT`, `AND`, `XOR`, and `OR`, in that order of precedence. Binary operators
associate left to right.

Each of the following costs one edit at one position in the expression.

- Replace one variable or one binary operator.
- Add or remove one `NOT`.
- Add a binary operator and a variable on either side of an existing
  subexpression, or remove a binary operator and one of its variable operands.
- Regroup three adjacent operands with a single tree rotation that preserves
  their operand and operator order.

Whitespace and redundant parentheses are free. The reference tool searches
expressions by increasing edit count, so its first truth-table match establishes
the minimum. A repair can end at any expression with the right truth table. Its
edit list must show the full expression after each edit.
Expressions are limited to 512 characters and a submitted repair can contain
up to 16 edit steps.

The verifier checks the original grade and any reported counterexample first.
It then checks the correction's truth table and replays the edits. A valid,
minimal repair earns a verifier score of 1. Each extra step deducts 0.25,
with a floor of zero. A wrong grade, wrong correction, or invalid edit sequence
scores zero. The student's grade remains pass/fail. For blank or malformed
answers, the agent reports a fail with the parse error and a correct model
expression. Structural edit distance is unavailable for those answers.

### Example outcomes

Numbers are the minimum repair counts for parseable failures.

| Student | Lab access | Backup power | Relay warning | Garden watering | Package release |
|---|---|---|---|---|---|
| `synthetic-01` | Pass | Pass | Pass | Pass | Pass |
| `synthetic-02` | Fail, 1 | Fail, 1 | Fail, 1 | Fail, 2 | Fail, 1 |
| `synthetic-03` | Fail, syntax error | Fail, blank | Pass | Pass | Pass |
| `synthetic-04` | Pass | Fail, 1 | Pass | Fail, 2 | Pass |
| `synthetic-05` | Fail, 1 | Pass | Fail, 1 | Pass | Fail, 1 |

For example, `synthetic-04` submitted `F AND R` for garden watering. It waters
when the schedule permits and rain is forecast, even if the soil is wet. One
minimal repair negates `R`, then adds `AND D` to `F`, yielding
`(F AND D) AND NOT R`.

## Layout

| Path | Contents |
|---|---|
| `nanoagent.yaml`, `contract.py` | Plugin manifest and typed tool and task contracts |
| `src/plugin/` | MCP server and tool implementations |
| `verifier/` | Exam reader, expression rules, and deterministic verification |
| `src/plugin/synthetic-exam.json` | Synthetic questions, references, and submissions |
| `product/`, `ui/` | Catalog metadata and question and student picker |
| `tests/` | Exam, verifier, MCP, and NanoAgent task integration tests |

## Develop and run

Requires Python 3.12 or newer and uv. Run from the plugin root.

```bash
uv sync --frozen --extra dev
uv run --frozen pytest
uv run --frozen ruff check .
```

Open this folder as a NanoAgent plugin to run the tasks in chat. The plugin
requires no environment variables or network access. The tests cover all 25
exam selections and the real MCP transport. The NanoAgent task integration test
uses a scripted agent and runs when NanoAgent is installed in the same Python
environment.
