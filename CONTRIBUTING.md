# Contributing to xpilot

xpilot is a Tesla-only sunnypilot fork. Read [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md), the highest development policy for the two juyun86 repositories, first; then read `AGENTS.md` and the relevant `XPILOT.md` interfaces. User instructions, platform requirements and OS permissions take precedence over repository policy.

## Which repository

- **This repository** (`juyun86/xpilot`, branch `xpilot`): the plugin host, the store, the UI, the core plugins (`sp_engagement`, `sp_models`, `sp_safety_fallback`), panda safety code and `opendbc/safety/plugins/safety.json`, checks and docs.
- **`juyun86/xpilot-plugins`**, branch `main`: every other plugin. New features go there as `plugins/<id>/`. CI here rejects new directories under `openpilot/tesla/plugins/`. Preserve onemiless as upstream; do not push user changes there.

A feature that needs both (for example a plugin that sends a new CAN message and needs a panda safety plugin) gets two pull requests. Merge the system one first. CI here runs `store_e2e` against the plugin repository's default branch, so after the plugin pull request is merged, re-run CI on `xpilot` to check that the two work together.

## Pull requests

1. Work on the authorized checkout/branch; do not create another branch/worktree without an explicit user request. For requested pull request work, target `xpilot`.
2. Run the host checks from `XPILOT.md` section 11. CI runs the same checks and must pass before merge.
3. Say in the pull request what you verified where: host checks, build, safety tests, device. Do not report one as another.
4. Changes to panda safety code also need the panda build, `test_tesla.py`, `test_xpilot_plugins.py` and MISRA (XPILOT.md section 6).
5. CI does not build panda or run the safety tests or MISRA. Paste the commands, results and the machine for each of them into the pull request.
6. A new panda safety plugin's header is `<plugin id>.h` (`gen_safety.py` rejects anything else). Every TX it allows without `controls_allowed` is listed in the XPILOT.md section 6 rules with the exact condition; the code must not allow more than the text says.
7. Fill in the pull request template. Leave a box unchecked if you did not do that step and say why.
8. Pull requests from accounts new to GitHub wait for a maintainer to approve the CI run.

## Automatic merge

When CI passes, `.github/workflows/automerge.yml` squash-merges a pull request from a collaborator if `tools/ci/pr_risk.py`
finds only documentation or `openpilot/tesla/ui/` changes. Anything else (car processes, panda safety, the store,
checks, CI, rule files, SP files) or any outside author gets one comment asking the owner to review. A failing check
on `xpilot` after a merge opens an issue.
