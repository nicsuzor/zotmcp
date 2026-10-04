---
alias:
  - wf-finish
description: zotmcp finish template -- defines task delivery via PR to main, owner-only merge (merge publishes the server image), and independent QA for functional changes and anything that can write to Zotero.
id: wf-finish
tags:
  - wf-template
  - finish
  - zotmcp
title: zotmcp Task Finish Template
type: template
---

## What this template does

Specifies how tasks in `nicsuzor/zotmcp` finish. Every change delivers as a pull request into `main`. Merging to `main` builds and pushes the server image under the `latest` tag, so the repository owner merges. Functional changes get an independent QA pass before the merge.

## Finish Policy

- **Target branch**: `main`. There is no intermediate version branch.
- **Delivery mechanism**: Push a feature branch (`task/<task-id>-<slug>`) and open a pull request into `main` (`gh pr create --base main`). Never push to `main` directly.
- **Merging**: The repository owner merges. Workers and QA tasks do not merge.
- **Commit trailer**: Commits must carry `Task: <task-id>` (and `Epic: <epic-id>` if applicable).
- **Zotero writes**: No worker or QA task performs a live write to the Zotero library. Any write requires the repository owner's explicit confirmation first. Tests for write paths mock the Zotero client.
- **QA review**:
  - **Required**: Any change to code under `src/`, `scripts/`, or the root Python scripts; MCP tool names, signatures, or behaviour; configuration under `src/zotmcp/conf/`; dependencies (`pyproject.toml`, `uv.lock`); `deploy/`; `.github/workflows/`; and anything that can write to Zotero or modify the vector store.
  - **None**: Documentation-only changes (`README.md`, `docs/`, `.agents/` text) with no functional impact.

## Worker Completion Checklist

Before marking `status: done`, the worker must:

1. Have a sibling `buttermilk` checkout in place, as `pyproject.toml` requires, then run `uv sync` and `uv run pytest`. Report passed, failed, and skipped counts; tests skipped for missing credentials are not passes.
2. Add or update tests for any changed behaviour. Write-path tests mock the Zotero client; no test writes to a live library.
3. Run the lint gate on changed files only: `uvx pre-commit run --files <changed files>`. Fix findings in the lines you touched.
4. Push the feature branch and open a PR into `main` with a summary, the test result counts, and `Task: <task-id>` in the body.
5. Confirm the PR checks start: `CI` (`test-status`), `Build and Push ZotMCP Docker Image`, `Trigger: Enforcer`, `Trigger: QA`. Report any failure verbatim.
6. Check off each acceptance criterion on the PKB task with pinpoint evidence (`file:line`, command output, PR link).
7. Mark the task `status: done` and release the claim.

## Follow-up QA Task Specification

Where QA is required, the verifying task runs independently on a clean checkout:

- **Title**: `QA: <primary task title>`
- **Parent**: Same parent as primary task
- **Depends on**: `[<primary-task-id>]`
- **Workflow**: Composes independent verification workflow
- **Goal**: Independently verify the PR on a clean checkout against the literal acceptance criteria: rerun `uv run pytest` and record skips, confirm every PR check is green, confirm no code path writes to Zotero without the repository owner's confirmation, and confirm changes to MCP tools match their documented behaviour. Record the verdict on the PR and the PKB task, then leave the merge to the repository owner.
