# Short Reflection on AI Usage for the Project

| | |
|---|---|
| **Name** | Kelsey (La Hue Van) |
| **Date written** | 2026-11-09 |
| **AI use log** | [`ai-log/kelsey.md`](../../../ai-log/kelsey.md) |

---

## 1. What did you learn about how to use these tools effectively?

- AI works best when we give it rules to follow, such as AGENTS.md, the specs and the constitution. It followed these rules quite strictly.
- Using more than one agent helps, especially for a junior coder like me. One agent alone may not notice its own mistakes. In my workflow, I discussed the task with Claude, Claude wrote a prompt for Antigravity to build the code, and then Claude checked whether Antigravity had done anything wrong. On pull requests, my teammates' agents also reviewed the code and spotted bugs and improvements.
- Passing tests does not mean the code is correct. My tests can pass while the feature still does not work with the real model (see section 3).
- Testing with real inputs matters. When I reviewed #53, the AI-written grading merge passed all its tests, but those tests only used files the AI had made itself. A grading sheet saved from Excel as "CSV UTF-8" starts with a hidden byte-order mark, which would have broken the merge. It was fixed test-first before our official grading.
- Some work must stay human. Claude refused to grade our evaluation answers, and I think that was right: using AI to judge whether an AI's answers are hallucinated would defeat the purpose.

## 2. Where were the tools strong, and where were they weak?

**Strong**

- Explaining things to us, guiding us step by step and giving recommendations.
- Following project rules strictly once it knew them. For example, it refused to edit the constitution because only humans may change it, and it refused to grade evaluation answers because we had to grade them ourselves.

**Weak**

- It sometimes missed edge cases, and agreed too easily once we raised them. When fixing empty questions (T17.1), its first fix only checked for blank text and missed questions like "." or "?!". When I pointed this out, it said "You're right" and followed my idea. It then added many symbol test inputs and suggested four more, but when I asked for a reason for each one, several caught the same mistake, so we removed them.
- It could sound sure even when it was wrong. During grading, Claude told me the label was `fabricated citation`, but the correct one was `fabricated-citation`.
- It sometimes guessed instead of checking. It guessed the field names in our results files instead of reading them first, and had to redo the work.
- It did not always follow the rules at first. Claude wrote parts of my AI log, including "How I checked it", until it found out that section must be written by me; from then on it refused. Antigravity ignored the rules unless we told it to read them.
- It could not help with our CI. Our GitHub Actions kept failing, and the AI could only tell us the problem was the machine (the macOS runner could not be found), not our code. It could not fix it, so the CI kept showing as failed.

## 3. What went wrong, and what would you do differently?

**What went wrong**

- When I built the `open_file` and `search_again` tools (T14.1 to T14.3), all the tests passed. But in a real-model test, Gavin found the model never saw what the tools returned: the results were replaced with "No commit history found". My tests checked each tool on its own, not what the model actually received. Gavin fixed it in T19.1.

**What I would do differently**

- Ask the agent to run the tests and also check the result with the real model on the cluster, to make sure what we built is actually used.
- Check facts the AI gives me, such as a label or a number, against the file or the spec myself.
