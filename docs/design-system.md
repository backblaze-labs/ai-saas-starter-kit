<!-- last_verified: 2026-04-30 -->
# Design System

The starter uses a GitHub Primer-flavored token palette with shadcn/ui
primitives. All tokens live in `apps/web/src/app/globals.css` and resolve via
Tailwind v4's `@theme inline` block.

For a live reference, open `/design` in the running app.

## Color tokens

| Token | Light | Dark | Use |
|-------|-------|------|-----|
| `--background` | `#ffffff` | `#0d1117` | Canvas |
| `--foreground` | `#1f2328` | `#f0f6fc` | Text |
| `--muted` | `#f6f8fa` | `#151b23` | Subtle surfaces, table header rows |
| `--border` | `#d1d9e0` | `#3d444d` | Divider lines |
| `--primary` | `#0969da` | `#4493f8` | CTAs, links, focus ring |
| `--accent-subtle` | `#ddf4ff` | rgba blue | Active states |
| `--success` | `#1a7f37` | `#3fb950` | Completion dots, positive deltas |
| `--attention` | `#9a6700` | `#d29922` | Warnings, folders |
| `--destructive` | `#cf222e` | `#f85149` | Danger actions |
| `--nav` | `#0d1117` | `#010409` | Top-bar chrome (always dark) |

Access via Tailwind utility (`bg-primary`, `text-muted-foreground`) when a
Tailwind theme key exists, or `var(--token)` otherwise. Semantic status
tokens (`success`, `attention`, `accent-subtle`) are mapped into Tailwind so
`bg-success` / `text-attention` compose.

## Radius

- `--radius-sm` 4px — inputs, small controls
- `--radius-md` 5px — badges, keyboard hints
- `--radius-lg` 6px — default (cards, buttons, dialogs)
- `--radius-xl` 8px — elevated surfaces (popovers)

6px is the anchor. Rarely deviate.

## Elevation

Defined as box-shadow tokens:

- `--shadow-small` — cards at rest
- `--shadow-medium` — hover states
- `--shadow-large` — dropdowns, popovers
- `--shadow-xl` — modal overlays
- `--shadow-inset` — sunken surfaces (rare)

Primer aesthetic is low-contrast — prefer `small`/`medium` for most work.

## Motion

- `--duration-short` 120ms — micro interactions (hover, focus)
- `--duration-medium` 200ms — panel open/close
- `--duration-long` 320ms — page-level transitions
- `--ease-productive` — UI feedback, the default
- `--ease-expressive` — hero/landing moments

Prefer opacity + translate transitions. Avoid scale > 1.02 — it reads as
"bouncy" and conflicts with the Primer aesthetic.

## Typography

Two font families:

- **Display — Mona Sans** (GitHub's open-source display face), loaded via
  `next/font/google` in `layout.tsx`, exposed as `--font-display` / the
  `font-display` Tailwind utility. Used for: headings, page titles, stat
  values, logo, Copilot surfaces.
- **Body — system stack**: `-apple-system, BlinkMacSystemFont, "Segoe UI", ...`
  Fast, native, zero payload.

Monospace stack: `ui-monospace, SFMono-Regular, "SF Mono", Menlo, ...` — used
for sizes, keys, shortcuts, and file paths.

**Base size: 15px / line-height 1.55.** Bumped from 14px — feels far less
cramped in dashboard contexts without breaking Primer's dense tables.

### Scale

| Role | Size | Weight | Font | Tracking |
|------|------|--------|------|----------|
| Page title | 26px (`.page-title`) | 600 | Display | `-0.015em` |
| Card title | 16px (`.card-title`) | 600 | Display | `-0.01em` |
| Stat value | 28px | 600 | Display | `-0.015em` |
| Body | 15px (default) | 400 | Body | — |
| Small | 13px (`text-sm`) | 400 | Body | — |
| Caption | 12px (`text-xs`) | 500 | Body | — |
| Column header | 11–12px uppercase `tracking-wider` | 600 | Body | — |
| Mono numeric | `font-mono text-xs tabular-nums` | 400 | Mono | — |

Always use `tabular-nums` for numeric columns.

## AI design elements

The kit ships **primitives for AI/chat surfaces** but intentionally does
*not* ship a live assistant. Compose these into your own drawer, inline
panel, or modal — and brand them however you want (these defaults use the
Primer palette so they drop into any Primer-styled app).

### Utilities

- `.ai-avatar` — solid Primer-blue disc. Put a `lucide` icon inside (Bot,
  Sparkles, MessageSquare — pick per your assistant's identity).
- `.chat-bubble.user` / `.chat-bubble.assistant` — message bubble pair with
  asymmetric tail radii. User bubbles use `accent-subtle`, assistant uses
  `muted`.
- `.chat-typing` — three-dot bounce indicator for streaming placeholders.
- `.prompt-chip` — rounded pill for empty-state starter questions.

### Composing a chat

```tsx
<div className="flex flex-col gap-3">
  <div className="flex items-start gap-2">
    <span className="ai-avatar h-7 w-7">
      <Bot className="h-3.5 w-3.5" />
    </span>
    <div className="chat-bubble assistant">Hi — how can I help?</div>
  </div>
  <div className="flex justify-end">
    <div className="chat-bubble user">Summarize my bucket activity.</div>
  </div>
</div>
```

Wire an input, a streaming fetch to your LLM provider, and an open/close
trigger (Sheet works well) to turn these primitives into a full experience.

## Generating loader

`<GeneratingLoader />` (in `components/ui/generating-loader/`) is the
brand-tinted "something is generating" indicator. Self-contained: the
blaze palette (red/amber/yellow) is scoped to `.blaze-orb` and the
component reads only `--muted-foreground`, `--foreground`, and
`--background` from the host theme — drops into either light or dark
mode without changes.

### Sizes

- `sm` (16px) — inline inside a button. Always renders a single
  continuously-rotating sparkle in the center; the variant prop is
  ignored at this size because the field compositions don't read.
- `md` (48px) — tile / thumbnail placeholder. Default.
- `lg` (96px) — hero canvas placeholder. Pair with a `label` so the
  shimmer text reads as part of the moment.

### Variants

- `flames` (default) — rising vertical scanlines through red/amber/yellow.
  Use during the first generation, before any output exists.
- `stars` — interior AI sparkles popping in/out. Use when iterating on
  existing content (refining, regenerating).

### Placement constraint

The `stars` variant includes one or more **white** sparkles whose dark
1px stroke disappears on pure white. Render `stars` on `bg-muted` (or
darker) — never directly on `bg-card` / `bg-background` in light mode.
For overlays, pair with `.blaze-scrim` to dim the underlying content.

Why this lives in `components/ui/`: shared non-shadcn primitives
(`EmptyState`, `DataTable`, `GeneratingLoader`) sit alongside the
generated shadcn components in that directory. The "never modify" rule
applies to the shadcn-generated files themselves, not to net-new custom
primitives added in their own subdirectory.

## Empty / error states

Two persistent full-content states for "the data isn't there":

- **`<EmptyState>`** — the underlying *data* is empty (no files in the
  bucket, no results for a query). Friendly icon + copy + optional CTA.
- **`<ErrorState>`** — the *fetch* failed. Pass the thrown error (typically
  an `ApiError`) and `ErrorState` derives readable copy: status `0` becomes
  "Can't reach the API" with the configured base URL; `401`/`403` becomes
  "Not authorized"; `5xx` becomes "Backend error". Pair with `onRetry` to
  let the user re-trigger the fetch.

Always prefer `ErrorState` over a stale `EmptyState` on fetch failure —
showing "no files" when the API is unreachable is actively misleading.

Both live in `components/ui/` next to the shadcn primitives.

## Spacing

Tailwind defaults. Load-bearing steps:

- `p-6` / `gap-6` — page-level separation
- `p-4` / `gap-4` — card content
- `p-3` / `gap-3` — dense lists, upload rows
- `p-2` / `gap-2` — toolbar groups, button clusters
- `gap-1.5` — icon + label

## Iconography

`lucide-react` only. Size conventions:

- `h-4 w-4` — default (inline with 14px body text)
- `h-3.5 w-3.5` — inside dense controls (buttons size=sm)
- `h-5 w-5` — feature card emphasis
- Use `stroke-width` default. Avoid filled variants.

## Components

See `/design` route for live examples. Authoring rules:

- Never hand-modify files in `src/components/ui/` — regenerate via
  `npx shadcn@latest add <name>` (or if the CLI fails on this monorepo's
  workspace resolver, copy the shadcn reference source verbatim and swap
  `@radix-ui/react-*` imports for the `radix-ui` meta package to match the
  kit's existing primitives).
- Shared non-shadcn primitives like `EmptyState` and `DataTable` also live
  in `src/components/ui/`; treat them the same way.

## Accessibility

- Global `:focus-visible` ring uses `--ring` at 2px with 2px offset.
- All interactive controls must be reachable by keyboard — tested via
  `⌘K` / `/` palette navigation.
- `aria-label` on icon-only buttons. Breadcrumbs carry `aria-current`.
- Color alone never signals state — pair with an icon or text label.
