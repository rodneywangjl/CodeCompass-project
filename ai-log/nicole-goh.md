# AI Use Log: Nicole Goh

## 2026-10-07 · Project context, evaluation definitions and Claude Code setup
- **Tool (model):** Claude, in the Claude app (claude-opus-5-5)
- **Files:** AGENTS.md, .gitignore, CLAUDE.local.md (local only, git-ignored)
- **Outcome:** Kept
<!-- TODO (Nicole): confirm the Outcome above (Kept / Changed / Rejected) or change it. -->
### What I asked for
I gave Claude our project proposal, the course brief, the AI-use policy, the log template and a copy of the repo, and asked it to pull out my responsibilities as evaluation, documentation and AI-log owner. I asked it to draft a personal Claude Code context file and to propose shared evaluation rules for AGENTS.md, including a definition of a hallucinated answer and the metric definitions. I also asked it to list cross-team gaps that affect evaluation without changing my teammates' code.
### How I checked it
TODO (Nicole): keep only the checks you actually did, in your own words.
- Did it work only on an unpacked copy of my ZIP, never my real repo?
- Did I review the AGENTS.md and .gitignore diff (43 lines added, none removed)?
- Did `git check-ignore -v CLAUDE.local.md` confirm the file is ignored?
- Did it refuse to commit when a hook asked it to, because I hadn't given permission?
- In the Claude Code session that followed, `git status`, `git diff --ignore-cr-at-eol --stat` and `git check-ignore -v` showed that the .gitignore lines were missing and CLAUDE.local.md was empty at first. I fixed both, and the re-check passed: only AGENTS.md and .gitignore changed, AGENTS.md only gained lines, and both files use CRLF.
- Did I compare §4.3 against the constitution and Spec 002 myself, or rely on Claude Code's check?
### What I kept or changed
I dropped the first context file it drafted from the proposal because it predated the repo and was out of date: it listed Whoosh and voyage-code as undecided and used the 32B model with a 14B fallback. I kept the AGENTS.md additions, including §4.3, which is marked provisional until the team reviews it. I also kept the .gitignore entries and the git-ignored CLAUDE.local.md.

## 2026-10-07 · Setup verification, review of §4.3 and AI log
- **Tool (model):** Claude Code (Claude Opus 5.5, claude-opus-5-5)
- **Files:** ai-log/nicole-goh.md, docs/checkpoint/ai-use-declaration.md (also reviewed AGENTS.md, .gitignore, CLAUDE.local.md)
- **Outcome:** Kept
<!-- TODO (Nicole): confirm the Outcome above (Kept / Changed / Rejected) or change it. -->
### What I asked for
I asked Claude Code to check that the earlier session's changes were in my repo as intended, and to check the new §4.3 evaluation rules against the constitution and Spec 002 without editing them. I also asked it to create this log file and draft both entries, and to prepare a commit without running it. Later I asked it for a reminder message and a blank log template for teammates without a log, and for a draft of the team AI-use declaration that summarises only what is in each member's log.
### How I checked it
TODO (Nicole): keep only the checks you actually did, in your own words.
- Did I read the git output it showed and agree with its findings (missing .gitignore lines, empty CLAUDE.local.md, hit-rate wording that didn't match)?
- Did I check its list of §4.3 gaps against the constitution and Spec 002 myself?
- Did I review this log file and the final diff before committing?
### What I kept or changed
TODO (Nicole): say which of its §4.3 findings you're taking to the team, and anything you changed in these log entries.
