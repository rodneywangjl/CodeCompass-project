# Complexity tagging rule (draft for Nicole and Kelsey)

Spec 003 AC-3.1. Every question gets one tag: `simple` or `code-tracing`. The tag describes **what it takes to answer the question from the code**, not how hard the topic sounds or how long the answer is. It must not depend on how CodeCompass retrieves code: the tag is used to test whether RAG does well on simple questions, so defining it by what search can find would make that test circular.

## The test

Ask: **to answer correctly, must a developer follow a chain, where one place leads to the next?**

- **`simple`:** each fact the answer needs is in **one place**: one function, method, class, constant, comment, or commit message.
- **`code-tracing`:** the answer needs **connecting two or more places**: a call, data or state that flows from one to the next, or a sequence of stages. The places can be in the same file.

## How to decide

1. Find the smallest code that fully answers the question.
2. If it is one function, method or class (or one commit message or comment), tag `simple`.
3. If you must connect places, because a call, data or state flows from one to the next, tag `code-tracing`.
4. Still unsure: could a developer answer by reading one place only, without opening anything it calls or is called by? Yes means `simple`.

## Notes

- **Two independent lookups are not tracing.** A question asking for two separate facts, each in one place, is `simple`. It is `code-tracing` only if you must connect the places.
- **Ignore wording.** "Dependency chain" or "architecture" does not make a question code-tracing, and "Where is..." does not make it simple. Judge by what the code needs.
- **Judge by what the question needs, not by how many places the reference answer cites.** Reference answers, especially SWE-QA's, often cite extra tests and docs. Extra citations do not make a question code-tracing.
- **Class relationships.** A subclass or "which class creates which" fact that can be read from one definition or one line (for example `class FlaskCliRunner(CliRunner)`) is a lookup, so several such facts are `simple`. It is `code-tracing` only if the answer needs following behaviour through those classes, such as a method on one class calling into another.
- **A helper the answer only mentions in passing does not count.** Only count places you must read to answer.
- **Unanswerable questions** are tagged `simple` (there is nothing to trace).
- **"Why" questions:** one commit message or comment that states the reason is `simple`. Connecting code in two places to explain the reason is `code-tracing`.
- **History questions:** one `git blame` or `git log` lookup that gives the answer (who, when, which commit) is `simple`. It is `code-tracing` only if the answer needs combining history with code in another place.

## Examples

None of these is an evaluation question, apart from the instructor's two, which are not about Flask.

| Question | Tag | Why |
|---|---|---|
| What is the default value of `MAX_COOKIE_SIZE`? | simple | One line of config |
| From the instructor's feedback: "What line updates the username variable?" | simple | One line |
| Edge case: which file defines `ConfigAttribute`, and which defines `send_from_directory`? | simple | Two independent lookups; nothing connects them |
| Edge case: which class does `FlaskCliRunner` subclass? | simple | Read from one class definition; no behaviour is followed |
| Edge case: why does `url_for` raise an error if `_scheme` is set while `_external` is false? | simple | One comment states the reason |
| What happens between a view calling `jsonify(...)` and the JSON response being built? | code-tracing | `jsonify` → `current_app.json.response` → the provider's `response` → `dumps` |
| Edge case: why does `RequestContext.push` open the session only the first time it is pushed? | code-tracing | A comment gives the reason, but you must connect it to how `stream_with_context` re-pushes the context |
| From the instructor's feedback: "If I update the mode to 'automatic', what changes in the output?" | code-tracing | Must follow the value through the code to the output |

## Second tagging

The tags are in the question files, so the second tagger works from a **copy without the complexity field**: id, question, reference answer and citations only, using only this rule.

Nicole second-tags Kelsey's 20 core questions. Kelsey second-tags a fixed sample of 20: 10 of Nicole's answerable core questions and 10 SWE-QA questions. Unanswerable questions are not sampled, because they are `simple` by definition.

Some sampled questions were exposed before tagging, as examples in an earlier version of this rule or in review comments: `architectural-01`, `architectural-08`, `design-rationale-06` and `-07` (Kelsey's sample); `localisation-03`, `localisation-05`, `runtime-behaviour-02`, `runtime-behaviour-04`, `runtime-behaviour-07` and `design-rationale-04` (Nicole's sample). Tag them anyway, but leave them out of the agreement rate and list them in `eval/questions/tagging.md`.

Compare the two sets of tags. Record the result in `eval/questions/tagging.md`: the agreement rate (for example "35/40 = 88%") and each disagreement with its final decision (AC-3.2).

If settling the tags leaves an answerable category below 3 code-tracing questions (AC-1.4), do not bend the rule. Replace a question in that category with a real tracing question before freezing.
