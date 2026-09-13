---
name: IPO-Wise
description: High-density financial intelligence console and automated Telegram alert engine for Indian IPOs
colors:
  primary: "#6366f1"
  primary-hover: "#4f46e5"
  emerald: "#10b981"
  cyan: "#06b6d4"
  amber: "#f59e0b"
  rose: "#f43f5e"
  neutral-bg: "#07090e"
  neutral-card: "rgba(17, 24, 39, 0.75)"
  neutral-card-hover: "rgba(26, 36, 56, 0.85)"
  border-subtle: "rgba(255, 255, 255, 0.08)"
  border-focus: "rgba(99, 102, 241, 0.5)"
  text-main: "#f8fafc"
  text-muted: "#94a3b8"
  text-dim: "#64748b"
typography:
  display:
    fontFamily: "'Outfit', -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.5px"
  headline:
    fontFamily: "'Outfit', -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.3px"
  title:
    fontFamily: "'Outfit', -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.2px"
  body:
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.5px"
rounded:
  sm: "6px"
  md: "10px"
  lg: "16px"
  full: "30px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "28px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "10px 18px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "#ffffff"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "10px 18px"
  button-emerald:
    backgroundColor: "{colors.emerald}"
    textColor: "#ffffff"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "10px 18px"
  button-secondary:
    backgroundColor: "rgba(255, 255, 255, 0.05)"
    textColor: "{colors.text-main}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "10px 18px"
  card-glass:
    backgroundColor: "{colors.neutral-card}"
    textColor: "{colors.text-main}"
    rounded: "{rounded.lg}"
    padding: "24px"
  input-field:
    backgroundColor: "rgba(13, 19, 32, 0.85)"
    textColor: "{colors.text-main}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "10px 14px 10px 38px"
---

# Design System: IPO-Wise

## Overview

**Creative North Star: "The High-Conviction Terminal"**

IPO-Wise is crafted as a precision dark financial cockpit engineered for rapid decision-making in high-frequency IPO bidding environments. It rejects decorative chart ornaments and generic dashboard bloat in favor of tactical signal density: deep OLED space foundations, frosted glass telemetry panels, and high-contrast metric badges that instantly communicate value, category, and risk.

The visual atmosphere balances the seriousness of institutional capital allocation with the fluid agility of consumer fintech. Ambient radial glows drift behind structural containers, signaling an active, live-connected pipeline without competing with typographic legibility. Every metric—from ₹ cutoffs to GMP multipliers—is rendered with razor-sharp tabular precision.

**Key Characteristics:**
- **Obsidian Space Canvas:** Pure deep dark foundation (`#07090e`) with fixed, luminous radial gradient backdrops (Indigo, Cyan, Emerald).
- **Frosted Glass Telemetry:** Multi-layer translucent cards (`rgba(17, 24, 39, 0.75)`) backed by `backdrop-filter: blur(16px)` and hairline borders (`rgba(255, 255, 255, 0.08)`).
- **Signal-to-Ink Discipline:** High-saturation chromatic accents are strictly reserved for actionable signals (GMP > 15%, live status, primary dispatch triggers).
- **Tactile Micro-Elevations:** Subtle interactive hover responses (`translateY(-2px)`) accented by diffuse ambient shadow glows.

## Colors

The color palette is built around an obsidian deep-space canvas punctuated by functional telemetry signals and high-visibility status indicators.

### Primary
- **Hyper Indigo** (`#6366f1`): The primary system accent, used for branding accents, active navigation states, primary action buttons (`btn-primary`), and focused input rings.
- **Deep Indigo Hover** (`#4f46e5`): Interactive hover state for primary action buttons, providing tactile depth.

### Secondary
- **Signal Emerald** (`#10b981`): The conviction color, signifying strong GMP (> 15%), open bidding status, active daemon toggles, and positive application signals.
- **Telemetry Cyan** (`#06b6d4`): Informational telemetry accent, used for SME category tags, secondary indicators, and gradient highlights alongside Indigo.

### Tertiary
- **Alert Amber** (`#f59e0b`): Warning and caution state, applied to paused bot states, pending subscriber approvals, and moderate GMP opportunities.
- **Risk Rose** (`#f43f5e`): Danger and negative state, used for destructive actions (unsubscribing, muting, deleting) and negative or below-threshold GMP values.

### Neutral
- **Obsidian Void** (`#07090e`): The foundational canvas background, providing maximum contrast for glowing indicators while reducing eye fatigue.
- **Deep Slate Glass** (`rgba(17, 24, 39, 0.75)`): The background of glass panels and stat cards, frosted with backdrop blur.
- **Deep Slate Glass Hover** (`rgba(26, 36, 56, 0.85)`): Elevated state for interactive cards and table rows.
- **Polar White** (`#f8fafc`): Primary high-contrast text color for titles, critical numerical values, and labels.
- **Slate Silver** (`#94a3b8`): Secondary text color for table headers, form descriptions, and subtitles.
- **Muted Steel** (`#64748b`): Tertiary text color for input placeholder icons, helper text, and subtle timestamps.
- **Subtle Border** (`rgba(255, 255, 255, 0.08)`): Hairline structural divider separating cards, table rows, and headers.

### Named Rules
**The Signal-to-Ink Rule.** Chromatic color is strictly reserved for financial telemetry, status indicators, and primary triggers. Structural cards, toolbars, and content backgrounds must remain neutral dark glass. Never apply saturated background fills to full cards.

**The Contrast Floor Rule.** All numerical metric values and status labels must achieve a minimum 7:1 contrast ratio against their glass surface backgrounds to guarantee instant scanability in fast-moving market sessions.

## Typography

**Display Font:** Outfit (fallback: -apple-system, BlinkMacSystemFont, sans-serif)  
**Body Font:** Inter (fallback: -apple-system, BlinkMacSystemFont, sans-serif)  
**Label/Mono Font:** Inter with tabular figures / uppercase tracking

**Character:** A dual-engine typographical system pairing the modern geometric precision of Outfit for confident numerical figures and panel headers with the legibility of Inter for high-density tabular records and status labels.

### Hierarchy
- **Display** (700 weight, `24px`, `1.2` line-height, `-0.5px` tracking): Main brand title and console hero headers.
- **Headline** (700 weight, `24px`, `1.2` line-height, `0` tracking): Numerical KPI metrics on stat cards and financial summaries.
- **Title** (600 weight, `17px`, `1.3` line-height, `-0.2px` tracking): Panel headers and section dividers.
- **Body** (400/500 weight, `13.5px`, `1.5` line-height): Standard descriptive copy, table cell data, and subscriber details.
- **Label** (600 weight, `12px`, `1.2` line-height, `0.5px` tracking, uppercase): Input labels, table column headers, and status pill badges.

### Named Rules
**The Tabular Number Rule.** All monetary figures (₹), share quantities, lot counts, and GMP percentages must render using tabular alignment to ensure clean vertical scanning across rows.

**The Uppercase Label Doctrine.** Micro-metadata, form labels, and status badges must be styled in uppercase with positive letter-spacing (`0.5px`) to establish distinct visual hierarchy against body text.

## Layout

The spatial model uses an auto-responsive CSS Grid structure contained within a maximum width of `1280px` (`.container`), centered with `24px` page padding.

- **Main Dashboard Layout:** Split layout with a fixed-width `380px` control sidebar on the left and a fluid `1fr` live telemetry table on the right (`grid-template-columns: 380px 1fr; gap: 24px`).
- **Settings Layout:** Multi-column adaptive grid with minmax thresholds (`repeat(auto-fit, minmax(min(100%, 380px), 1fr)); gap: 24px`).
- **Responsive Breakpoint (980px):** Below `980px`, sidebar grids collapse into a single stacked column (`1fr`) with full horizontal scrolling preserved for data tables (`.table-wrap`).
- **Quick Stats Grid:** Responsive auto-fit bar (`repeat(auto-fit, minmax(220px, 1fr)); gap: 16px`) providing high-level KPI cards directly below the main header.

## Elevation & Depth

IPO-Wise uses a layered glassmorphic depth system rather than physical drop shadows. Depth is communicated through ambient luminous backdrops, frosted translucency (`backdrop-filter`), and luminous glow rings.

### Shadow Vocabulary
- **Panel Resting Depth** (`box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25)`): Base depth applied to all glass panels, grounding them against the dark backdrop.
- **Card Hover Elevation** (`box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3)` + `transform: translateY(-2px)`): Responsive elevation on stat cards and interactive list items.
- **Primary Action Glow** (`box-shadow: 0 4px 15px rgba(99, 102, 241, 0.25)`): Ambient neon aura surrounding primary buttons and active pills.
- **Emerald Signal Glow** (`box-shadow: 0 4px 15px rgba(16, 185, 129, 0.2)`): Luminous aura indicating active automated triggers and high-conviction GMP states.

### Named Rules
**The Glass Horizon Rule.** Panels float above ambient radial gradients using `backdrop-filter: blur(16px)` and translucent fills (`rgba(17, 24, 39, 0.75)`). Structural surfaces must never be completely opaque.

**The Glowing Intent Rule.** Shadow glows are active responses to state. Never apply colored glows to inert or disabled interface elements.

## Shapes

The geometric form language balances soft modern consumer corners with technical precision.

- **Large Radius (`16px` / `--radius-lg`):** Main panels, stat cards, and modal containers.
- **Medium Radius (`10px` / `--radius-md`):** Buttons, custom form inputs, table wrappers, and switch toggles.
- **Small Radius (`6px` / `--radius-sm`):** Micro-action buttons, inline badges, and toast alerts.
- **Pill Radius (`30px` / `full`):** Status pills, navigation switchers, and slider thumb handles.
- **Borders:** Ultra-thin hairline strokes (`1px solid rgba(255, 255, 255, 0.08)`) define all structural boundaries, preventing panels from dissolving into dark space.

## Components

### Buttons
- **Shape:** Medium radius (`10px`).
- **Primary (`.btn-primary`):** Linear gradient (`135deg, #6366f1, #4f46e5`), white text, `padding: 10px 18px`, with a glowing shadow (`0 4px 15px rgba(99, 102, 241, 0.25)`). On hover, brightens (`filter: brightness(1.1)`) and lifts (`translateY(-1px)`).
- **Emerald Action (`.btn-emerald`):** Linear gradient (`135deg, #10b981, #059669`), white text, with an emerald glow (`0 4px 15px rgba(16, 185, 129, 0.2)`). Used for instant live checks ("⚡ Check Now").
- **Secondary Ghost (`.btn-secondary`):** Translucent fill (`rgba(255, 255, 255, 0.05)`), subtle border, white text. On hover, shifts to `rgba(255, 255, 255, 0.1)`.
- **Danger Outline (`.btn-danger-outline`):** Transparent background, hairline rose border (`rgba(244, 63, 94, 0.3)`), rose text (`#fb7185`). On hover, transitions to subtle rose tint (`rgba(244, 63, 94, 0.15)`).

### Status Pills
- **Style:** Rounded pill (`30px`), frosted dark background (`rgba(17, 24, 39, 0.6)`), hairline border.
- **Active State (`.status-pill.active`):** Embedded `8px` pulsating dot with Signal Emerald fill and `box-shadow: 0 0 10px #10b981`.
- **Paused State (`.status-pill.paused`):** Amber dot with `box-shadow: 0 0 10px #f59e0b`.

### Cards & Panels
- **Container (`.glass-panel`):** Translucent slate glass (`rgba(17, 24, 39, 0.75)`), `16px` radius, `backdrop-filter: blur(16px)`, `24px` internal padding, `1px solid rgba(255, 255, 255, 0.08)`.
- **Stat Card (`.stat-card`):** Flexible KPI card with `44px` icon container, uppercase label, and `24px` Outfit metric value.

### Inputs & Form Controls
- **Custom Input (`.custom-input`):** Deep charcoal fill (`rgba(13, 19, 32, 0.85)`), hairline border, `10px` radius, `padding: 10px 14px 10px 38px` (accommodating absolute left icon). On focus, borders illuminate Hyper Indigo (`#6366f1`) with a `3px` focus ring (`rgba(99, 102, 241, 0.25)`).
- **Range Slider (`.range-slider`):** Native range accent colored Hyper Indigo paired with a live numerical value badge in Telemetry Cyan (`#06b6d4`).
- **Master Toggle (`.switch`):** `46px` x `24px` pill with smooth sliding toggle knob transitioning from dark slate (`#334155`) to Signal Emerald (`#10b981`).

### Navigation Bar
- **Container (`.header-nav`):** Encapsulated dark pill (`rgba(13, 19, 32, 0.6)`), `border-radius: 30px`, `padding: 4px`.
- **Links (`.nav-link`):** Subdued text (`#94a3b8`), transitions to active pill (`background: linear-gradient(135deg, #6366f1, #4f46e5)`) with white text and `box-shadow: 0 2px 12px rgba(99, 102, 241, 0.25)`.

### Live Data Tables
- **Wrap (`.table-wrap`):** Horizontally scrollable wrapper with `10px` radius and hairline outer border.
- **Headers (`thead th`):** Subdued uppercase labels (`11.5px`, `#94a3b8`), `letter-spacing: 0.5px`, `padding: 12px 16px`, sticky top.
- **Rows (`tbody tr`):** Subtle bottom border (`rgba(255, 255, 255, 0.05)`). Alternating hover highlight (`rgba(26, 36, 56, 0.5)`).

## Do's and Don'ts

### Do:
- **Do** preserve the fixed ambient radial gradients on the canvas background to give depth to frosted glass panels.
- **Do** format all currency and lot numbers with exact monetary symbols (`₹`) and commas for rapid cognitive scanning.
- **Do** render GMP percentage values with color-coded conviction badges: Signal Emerald for `>= 15%`, Alert Amber for `< 15%`, and Risk Rose for negative/nil.
- **Do** use `backdrop-filter: blur(16px)` on elevated panels and modals.
- **Do** pair all primary interactive actions with their respective luminous shadow glow tokens.

### Don't:
- **Don't** use solid opaque gray or white card backgrounds that eliminate the subtle glassmorphic depth.
- **Don't** introduce generic primary blue (`#0000ff`) or basic bootstrap colors; adhere strictly to Hyper Indigo, Signal Emerald, Telemetry Cyan, Alert Amber, and Risk Rose.
- **Don't** use serif typography or decorative script fonts anywhere in the application.
- **Don't** use harsh `1px solid #ffffff` borders; keep all container borders at `rgba(255, 255, 255, 0.08)`.
- **Don't** clutter data table cells with unnecessary icons or unformatted raw numbers.
