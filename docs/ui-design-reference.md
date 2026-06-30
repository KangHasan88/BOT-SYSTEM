# UI Design Reference

All bot web UI work should follow the existing Kanban product style so the
experience feels familiar and operational.

## Source Reference

Primary reference: `https://31.97.106.123/kanban`

Observed Kanban patterns:

- Inter/system sans font stack.
- Light operational background: `#f6f8fb` / `#f8fafc`.
- White panels with soft border, small shadow, and rounded corners.
- Compact page header with icon tile, title, short metadata, and action area.
- Toolbar actions grouped inside light-gray rounded containers.
- Buttons use icon + text, small height, hover background, and clear tooltip/title.
- Status is shown as pill badges with semantic colors.
- Lists/cards are dense, scan-friendly, and built for repeated work.
- Tables and logs should be readable, compact, and not marketing-like.
- Dark mode support can follow Kanban variable names later, but the first pass
  should keep light mode polished and consistent.

## Trading Bot UI Rules

- Use Kanban-style shell: header card, grouped toolbar, content bands/panels.
- Keep trading/safety information dense and scannable.
- Use badges for states such as `SAFE`, `NO_GO`, `PASSED`, `BLOCKED`, `EMPTY`.
- Use grouped action bars for commands instead of scattered buttons.
- Prefer icon + text for primary commands, with short labels.
- Avoid hero/landing-page layout, decorative gradients, and oversized text.
- Use the same calm gray/blue visual language as Kanban.
- Keep dangerous actions visually distinct and reason-gated.
- Do not expose live buy/sell/order controls in demo or paper UI.

## Implementation Target

Upcoming UX work should first align the local web orchestrator styles with this
reference before adding more screens:

- shared CSS variables based on Kanban;
- reusable panel, badge, toolbar, and table classes;
- responsive layout that remains dense on desktop and readable on mobile;
- visual smoke test by browser for each new page-level UI.
