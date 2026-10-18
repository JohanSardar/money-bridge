# How we built Apple Bridge (a reusable workflow)

A plain summary of what we did, in order, so the same process can be reused for the next project.

## 1. Set up the tools
- Installed **Matt Pocock's skills** as a Claude Code plugin (`mattpocock/skills`): grilling, codebase-design, domain-modeling, TDD, code-review, and more.
- Picked the models:
  - **Claude Opus 5.5**: main planner, then build leader
  - **Astra (GPT-6-Astra)**: independent designer and critic
  - **Fable**: tiebreaker when Claude and Astra disagree
  - **GPT-6.1 Sol**: research and build workers. No Opus subagents.

## 2. Grill the requirements and goals
- Claude asked questions in rounds, each with a recommended answer, so "yes" accepts it.
- Settled: who it's for (everybody), scope (everything on the Mac that syncs with the iPhone), speed (<1 s), security (high), Mac only (no iPhone app), SIP stays on.
- Every answer went into `design/DECISIONS.md`, the binding source of truth.

## 3. Research what already exists
- Sol research agents checked for existing products and reusable parts:
  - iMessage bridges: BlueBubbles, Beeper, imsg, commercial APIs
  - Apple data MCP servers
  - sync engines
  - Screen Time access
- Result: nothing does the whole thing, but many pieces can be reused.
- Ran a **real test on the actual Mac** (Screen Time data) instead of trusting reports.
- Reports went into `research/`.

## 4. Design with two independent models
- **Astra designed the system on its own** from the raw requirements only, without seeing Claude's design, so it wouldn't be biased.
- Claude compared the two designs, argued the differences in writing, and each side conceded where the other was right.
- Anything still unresolved would go to **Fable** to decide. (Everything got resolved, so Fable wasn't needed.)
- Results: `design/debate/RESOLUTION.md`.

## 5. Grill a bit more, then make the deep modular plan
- More grilling rounds: test strategy, where the code lives, safety rules, the GitHub repo, principles to follow.
- Adopted rules from **poteto's pstack** (verify by running the real thing, subtract before adding, fix root causes, no code comments, encode lessons as automatic checks).
- **Module architecture**, using Matt Pocock's deep-module method:
  - Astra and Claude each designed it independently.
  - They debated, then merged (`design/debate/MODULES-RESOLUTION.md`).
  - Covered: small interfaces, clear seams, a real second adapter for every seam (e.g. a fake Apple for testing).
- **Test strategy:** end-to-end first, at three levels (fake Apple → real Apple → a real AI agent on another computer). Unit tests only where end-to-end can't reach.

## 6. Send it to build
- Made a **public GitHub repo**, scrubbing personal data first.
- Wrote one goal file (`design/BUILD-GOAL.md`) containing everything: what to read, where things run, the milestones, the test-first rules, zero comments, the review process, git rules, safety rules, and when to ask for help.
- Started **one Opus 5.5 leader**. It:
  - writes the full spec and the feature graph itself
  - starts **Sol (medium, Fast) workers** only for real chunks of work, and handles small things itself
  - gets every change reviewed by a different agent using Matt Pocock's code-review, with the reviewer rerunning the tests
  - keeps looping until everything is done, and asks back only for genuine blockers (like macOS permission clicks)
  - keeps `design/PROGRESS.md` updated so anyone can see where it is

## The short version
1. Tools: install skills, pick models
2. Grill: requirements and goals
3. Research: what exists, plus test on the real hardware
4. Design: two models independently, debate, Fable tiebreaks
5. Grill more, then a deep modular plan with tests designed first
6. Build: one leader, cheap workers, review everything, loop until done

## Lessons
- Give the reviewer only the raw requirements first, never your own design. Otherwise it just critiques yours.
- Test claims on the real machine early. "Impossible" turned into "works" for Screen Time.
- Keep every decision in a file. The build agents read files, not chat history.
- Some things need a human (macOS permission dialogs can't be clicked over SSH). Batch them, and have agents detect when they're done instead of waiting for a reply.
