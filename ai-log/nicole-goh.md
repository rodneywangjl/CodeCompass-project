# AI Use Log: Nicole Goh

## 2026-10-07 · Project context, evaluation definitions and Claude Code setup
- **Tool (model):** Claude, in the Claude app (claude-opus-5-5)
- **Files:** AGENTS.md, .gitignore, CLAUDE.local.md (local only, git-ignored)
- **Outcome:** Kept
### What I asked for
I gave Claude our project proposal, the course brief, the AI-use policy, the log template and a copy of the repo, and asked it to pull out my responsibilities as evaluation, documentation and AI-log owner. I asked it to draft a personal Claude Code context file and to propose shared evaluation rules for AGENTS.md, including a definition of a hallucinated answer and the metric definitions. I also asked it to list cross-team gaps that affect evaluation without changing my teammates' code.
### How I checked it
Claude worked only on an unpacked copy of my ZIP, never my real repo. I reviewed its diff for AGENTS.md and .gitignore (43 lines added, none removed), and `git check-ignore -v CLAUDE.local.md` confirmed the file was ignored. When an automatic hook asked it to commit, it refused because I hadn't given permission. After I copied the changes into my repo, a Claude Code check (`git status`, `git diff --ignore-cr-at-eol --stat`, `git check-ignore -v`) showed that the .gitignore lines were missing, CLAUDE.local.md was empty and the hit-rate wording in §4.3 was out of date. I fixed all three, and the re-check passed: only AGENTS.md and .gitignore changed, AGENTS.md only gained lines, and both files use CRLF. I also compared §4.3 against the constitution and Spec 002 myself, using Claude Code's list of gaps.
### What I kept or changed
I dropped the first context file it drafted from the proposal because it predated the repo and was out of date: it listed Whoosh and voyage-code as undecided and used the 32B model with a 14B fallback. I kept the AGENTS.md additions, including §4.3, which is marked provisional until the team reviews it. I also kept the .gitignore entries and the git-ignored CLAUDE.local.md.

## 2026-10-07 · Setup verification, review of §4.3 and AI log
- **Tool (model):** Claude Code (Claude Opus 5.5, claude-opus-5-5)
- **Files:** ai-log/nicole-goh.md, docs/checkpoint/ai-use-declaration.md, ai-log/rodney-wang.md, ai-log/gavin-tay.md, ai-log/kelsey-la.md, AGENTS.md (§4.3 open questions; also reviewed .gitignore, CLAUDE.local.md)
- **Outcome:** Kept
### What I asked for
I asked Claude Code to check that the earlier session's changes were in my repo as intended, and to check the new §4.3 evaluation rules against the constitution and Spec 002 without editing them. I also asked it to create this log file and draft both entries, and to prepare a commit without running it. Later I asked it for a reminder message and a blank log template for teammates without a log, and for a draft of the team AI-use declaration that summarises only what is in each member's log.
### How I checked it
I read the git output it showed and agreed with its findings: the missing .gitignore lines, the empty CLAUDE.local.md and the hit-rate wording that didn't match. I checked its list of §4.3 gaps against the constitution and Spec 002 myself. I reviewed this log file and the final diff before each commit.
### What I kept or changed
I shared all of its §4.3 findings with the team and added them to AGENTS.md §4.3 as open questions for Spec 003, leaving the existing definitions unchanged. I kept the reminder message, the blank template and the heading-only starter logs for Rodney, Gavin and Kelsey, created with their agreement. After I gave it the AI-use policy, I had the declaration draft reworked to the policy's §5.1 format: one short paragraph covering only what is in the logs.
