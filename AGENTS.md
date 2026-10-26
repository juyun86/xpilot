# Working rules

- Read [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md) first. It is the highest development policy within both juyun86 Xpilot repositories; it does not override user instructions, platform requirements or OS permissions. Then read the relevant `XPILOT.md` interfaces and rules. Conflicting older wording below yields to that policy.
- Push routing (XPILOT.md rule 15): plugin changes (`plugins/<id>/`, their tests, `dist/`, `index.json`) go only to `github.com/juyun86/xpilot-plugins` on `main`. System changes (host, store, UI, core plugins, panda safety, `safety.json`, checks, docs) go only to `github.com/juyun86/xpilot` on `xpilot`. Preserve onemiless as upstream, not the user's push destination. A feature that needs both gets separate scoped commits and reviews; publish the system side first. Do not add plugin directories under `openpilot/tesla/plugins/` here; only the core plugins live there (`manifest_check.py` M12).

- Work on `xpilot` for this project. Do not create a feature branch or another worktree unless the user explicitly requests it.
- Verify the checkout, branch, HEAD, and dirty files before editing. Do not switch unrelated worktrees or overwrite another task's changes.
- Complete each coherent change on `xpilot` with a scoped commit. Include only that change's files. Use `git revert <commit>` to undo a committed change while preserving later work.
- Keep test code and candidate implementations in the same branch and record their validation status. Logs and generated replay results may live outside Git; identify the source commit and content hashes.
- Report the local commit and the device's active commit separately. A shared branch name, an uploaded test copy, or a successful replay does not establish deployment or activation.
- NEVER write unit tests after writing code. Prefer E2E validation with repeatable commands and verifiable artifacts. Before isolated testing, list the ways the system can fail.

## Task speed (owner rule 2026-10-26)

Tasks were slow because every worker read everything, ran every gate after every step and produced large evidence sets. Keep the safety gates; drop the rest.

- **Read narrowly.** Read `XPILOT.md` section 2 (hard rules) plus the sections for the files you change (`grep -n '^#' XPILOT.md`), not the whole file. Read the files in scope and their direct callers, nothing more. Continuations read only the handoff file and the diff.
- **Test in two tiers.** While working, run only the checks that cover the changed files (for example `tile_layout_check.py` for `tiles.py`). Run the full `tools/sp_tesla_e2e/*_check.py` set once, at the end. Pushing the branch runs CI, so do not also start `gh workflow run` unless the task needs a non-default `plugins_ref`.
- **Failure cases stay, ceremony goes.** List the failure cases first, as a short docstring list in the check. A fix must make one new case fail on the old code; show that once, by running the check on the base commit. Do not write separate `without_fix` scripts that patch and restore production files.
- **Evidence is the REPORT, not an artifact tree.** The REPORT (or the PR body) lists commands and exit codes. Only device work, firmware builds meant for flashing, and replays of real logs keep artifacts: one directory with `REPORT.md`, `result.json` and the input/output hashes. No per-command logs, `commands.jsonl` or `SHA256SUMS` otherwise.
- **Size tasks to finish.** A task must fit well inside the 150K context: one subsystem, at most about 10 files of production code. The coordinator splits larger work before dispatch; a worker that sees it will not fit reports that at the start instead of handing off at the end.
- **Firmware and safety are not shortened.** Panda/safety changes still run the opendbc safety tests, MISRA, the board builds and size report once on the final commit.
