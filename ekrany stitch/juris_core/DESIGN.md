# Design System Document: The Sovereign Interface

## 1. Overview & Creative North Star
**Creative North Star: "The Architectural Ledger"**

This design system moves away from the cluttered, bureaucratic aesthetic typical of legal and governmental software. Instead, it adopts a high-end editorial approach—"The Architectural Ledger." The goal is to convey absolute authority and trust through structured breathing room, sophisticated tonal depth, and a rejection of traditional containment.

We achieve this by breaking the "template" look. We favor intentional asymmetry, where large typographic headings anchor the page, and content "floats" within a hierarchy of light and shadow rather than rigid boxes. This is not just a SaaS tool; it is a premium digital environment designed for focus, clarity, and decisiveness.

---

## 2. Colors: Tonal Sovereignty
The palette is built on a foundation of "Deep Midnight" and "Atmospheric Blues," moving beyond flat hex codes to create a sense of environmental depth.

### Core Palette (Dark Mode Optimized)
*   **Primary (Action):** `#b8c4ff` (Light Blue) / **Primary Container:** `#1e40af` (Deep Blue). 
*   **Surface:** `#0c1322` (Midnight)
*   **Surface Containers:** Range from `Lowest (#070e1d)` to `Highest (#2e3545)`.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders for sectioning. Structural boundaries must be defined solely through background color shifts.
*   *Example:* A navigation sidebar should sit on `surface-container-low`, while the main content area uses the base `surface` color.
*   *Why:* Borders create visual "noise" that exhausts the eye in complex legal workflows. Tonal shifts create a seamless, high-end feel.

### Surface Hierarchy & Nesting
Treat the UI as stacked sheets of fine, semi-transparent material. 
*   **Layer 1 (Background):** `surface-dim` (`#0c1322`).
*   **Layer 2 (Main Workspace):** `surface-container-low` (`#141b2b`).
*   **Layer 3 (Active Cards/Modals):** `surface-container-high` (`#232a3a`).

### The "Glass & Gradient" Rule
To inject "soul" into the professional interface, use Glassmorphism for floating elements (e.g., Modals, Tooltips). Use `surface_variant` at 60% opacity with a `20px` backdrop-blur. 
*   **Signature Textures:** Main CTAs should use a subtle linear gradient from `primary` to `primary_container` (135°) to provide a metallic, authoritative sheen.

---

## 3. Typography: Editorial Authority
We utilize **Inter** not as a standard font, but as a structural element. The scale is dramatic to ensure a clear information hierarchy in data-heavy legal documents.

*   **Display (Large Scale):** Used for dashboard overviews. `display-lg` (3.5rem) uses tight letter-spacing (-0.02em) to feel architectural.
*   **Headline (Sectioning):** `headline-sm` (1.5rem) provides clear entry points into complex forms.
*   **Body (Readability):** `body-lg` (1rem) is the workhorse. High line-height (1.6) is mandatory for legal text to prevent "wall of text" fatigue.
*   **Label (Metadata):** `label-md` (0.75rem) in `on-surface-variant` color for timestamps and non-interactive data.

---

## 4. Elevation & Depth: Tonal Layering
We abandon traditional "drop shadows" in favor of environmental lighting.

*   **The Layering Principle:** Depth is achieved by stacking. A `surface-container-lowest` card placed on a `surface-container-low` section creates a natural "sunken" effect, perfect for secondary data feeds.
*   **Ambient Shadows:** For "floating" components like Steppers or Action Menus, use a shadow with a `48px` blur and `4%` opacity. The shadow color must be `on-background` (tinted blue) rather than pure black to maintain color harmony.
*   **The "Ghost Border" Fallback:** If a divider is strictly necessary (e.g., in a high-density data table), use the `outline-variant` (`#444653`) at **15% opacity**. It should be felt, not seen.
*   **Glassmorphism:** Use `surface-tint` overlays on images or complex backgrounds to ensure typography remains the focal point.

---

## 5. Components: The Sovereign Toolset

### Buttons
*   **Primary:** High-gloss gradient (`primary` to `primary_container`). 8px radius (`DEFAULT`).
*   **Secondary:** No background. `Ghost Border` (15% opacity) that becomes 30% on hover.
*   **States:** On `hover`, increase the elevation by shifting to a higher `surface-container` tier.

### Forms & Inputs
*   **Fields:** Background `surface-container-highest`. No border. A bottom-aligned 2px indicator in `primary` appears only on `focus`.
*   **Validation:** Error states use `error_container` (`#93000a`) for the background—never a red border alone.

### Cards & Lists
*   **Constraint:** Forbid divider lines. Use `1.5rem (xl)` vertical spacing to separate list items.
*   **Nesting:** Nested cards must be one tonal step higher or lower than their parent.

### Steppers (The Legal Workflow)
*   **Visual Style:** Horizontal, using `primary_fixed_dim` for completed steps and `surface-container-highest` for upcoming ones. Use a "connecting pulse" animation between active steps to signify progress.

### Additional Component: The "Legal Drawer"
A sliding side-panel using `surface_bright` with a heavy backdrop blur. This is for viewing document metadata without losing context of the main SaaS application.

---

## 6. Do's and Don'ts

### Do:
*   **Do** use extreme whitespace. If a section feels "done," add 16px more padding.
*   **Do** use `inter` Medium (500) for labels to ensure legibility against dark backgrounds.
*   **Do** align all elements to a strict 8px grid, but allow "Hero" elements to break the grid slightly for visual interest.

### Don't:
*   **Don't** use pure `#000000` or `#FFFFFF`. Always use the tonal tokens (e.g., `surface_lowest` or `on_surface`).
*   **Don't** use high-contrast borders. They fracture the user's focus.
*   **Don't** use "vibrant" colors for anything other than Primary actions. Legal interfaces must remain calm and subdued.
*   **Don't** use standard Heroicons sizes without adjustment. Increase stroke-width to 2px for better presence in the "Architectural Ledger" style.