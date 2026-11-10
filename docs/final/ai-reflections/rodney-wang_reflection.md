# Short Reflection on AI Usage for the Project

| | |
|---|---|
| **Name** | Rodney Wang |
| **Date written** | _2026-11-10_ |
| **AI use log** | [`ai-log/rodney-wang.md`](../../../ai-log/rodney-wang.md) |


---

## 1. What did you learn about how to use these tools effectively?

- The most useful habit was writing the tests first and checking that they failed before any code was written. This caught several bugs in the AI's first drafts that I would otherwise have missed.
- The AI did better work when I gave it the project rules and the spec up front, and told it to flag open questions instead of answering them itself. When it reviewed one of our specs, it left three decisions for the team rather than guessing.
- Passing tests were not enough. I also had to check the results by actually running the system and watching how it behaved. Several problems only showed up that way.

## 2. Where were the tools strong, and where were they weak?

**Strong**

- Small, clearly defined pieces of code needed very little correction.
- It was good at finding the cause of a problem when it could measure what was happening. When indexing a repository froze for over half an hour, it worked step by step from the symptoms to the real cause, that was a bug that produced one chunk of text far larger than intended.

**Weak**

- It guessed settings like memory limits and batch sizes instead of measuring them. Its first GPU settings ran out of memory on my 8 GB card, and its batch size made indexing a large repo hang for 36 minutes. Both were only fixed after I had it measure memory use on my machine.
- Some of the tests it wrote were wrong, or passed without actually testing anything.
- Its first drafts often looked correct but failed when run for real, for example running out of memory or breaking on a different operating system.

## 3. What went wrong, and what would you do differently?

**What went wrong**

- Partway through the project I told it to assume I had approved its tests and stop asking me. I later did a final review in the end though, but since there were so much changes, it might not be the best. I did this for the TUI mainly, which is small risk and github version control would have contained it. Next time, I should pay more attention to details.
- Sometimes i got the same model to write the tests and code, as I got lazy. I would instead get another model to do the tests.

**What I would do differently**

- Read and approve the tests myself before any code is written, and look out for tests that pass without really checking anything.
- Get different AI models to write code and test
- Ask for evidence before accepting any number the AI suggests, and test on every operating system from the start instead of adding them late.
