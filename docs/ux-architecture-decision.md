# UX0 Architecture Decision: Local Web First

The bot UI should start as a local web orchestrator, not a native desktop app
and not a public internet dashboard.

## Decision

Use a lightweight local web UI as the first operator experience.

- Development mode: run on the laptop at `localhost`.
- VPS mode: run on the VPS bound to localhost/private network only.
- Engine mode: bot cycle, scheduler, QA reports, and data collection must keep
  working without the UI open.
- Live mode: no live order action is exposed by the UI until all readiness gates
  and owner approval pass.

## Why Local Web First

- Browser UI is easier to run across laptop and VPS than a native desktop app.
- It can be opened from one URL instead of clicking individual files.
- It keeps the engine independent from the UI, so closing the browser does not
  stop scheduled work.
- It can handle slow laptop-to-VPS links with lightweight polling and cached
  last-known status.
- It can reuse existing JSON/CSV reports without adding a database first.

## Rejected Options

Native desktop is postponed because it adds packaging, update, and OS-specific
launcher work before the operator workflow is proven.

Public web dashboard is rejected for v1 because it increases security exposure.
If remote access is needed, use VPN, SSH tunnel, or private network access.

## UX Principles

- UI is an operator surface, not the trading engine.
- All actions call audited CLI/service commands.
- Every command result must appear in an activity timeline.
- The UI must show stale/last-known status clearly when the connection is slow.
- Paper/research actions are visible; live execution remains blocked.
- The kill switch and incident status must be visible from the home view.

## Initial Screens

- Home: bot mode, safety status, data health, paper status, go/no-go summary.
- Controls: run cycle, sync market data, build dashboard, run QA reports.
- Activity: audit log and recent command output.
- Reports: backtest, walk-forward, paper, daily journal, QA reports.
- Safety: kill switch status, incident drill, rollback references.

## Acceptance Criteria

- Decision record exists and favors local web first.
- Desktop app is explicitly postponed.
- Public internet exposure is explicitly rejected for v1.
- Engine independence from UI is documented.
- Slow connection behavior uses cached status and lightweight polling.
- Live action remains unavailable before readiness gates and owner approval.
