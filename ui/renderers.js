import { h } from "./kit/components.js";

export default {
  ExamOutput: ({ questions, student_ids }, { send }) =>
    h("div", { class: "exam-options" }, ...questions.map(({ question_id, prompt }) =>
      h("section", {},
        h("h3", { text: question_id }),
        h("p", { text: prompt }),
        h("div", { class: "student-options" }, ...student_ids.map((student) =>
          h("button", {
            class: "button small",
            type: "button",
            text: student,
            onclick: () => send(`Grade ${student} on ${question_id}.`),
          }),
        )),
      ),
    )),
};
