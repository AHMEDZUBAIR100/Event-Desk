# Frontend Design System Proposal — Day 2, Prompt 6

**Status**: `PROPOSED`
**Scope**: Visual foundation for the EventDesk Next.js frontend. This is a design proposal only; no implementation or dependency changes are included.

## 1. Design direction

Build a quiet, professional interface using black, white, and neutral grays. Keep the layout minimal and content-led: event names, dates, venues, and prices should carry the visual hierarchy. Use whitespace and alignment to organize pages instead of decorative panels, heavy shadows, gradients, or repeated boxed sections.

The event catalogue can use a responsive card grid, but cards should feel like lightweight entries rather than dashboard tiles. Favor a simple border or subtle divider, modest rounding, and clear typography. Keep interface copy short and specific.

## 2. Color palette

Use a neutral palette in both themes. The single accent is monochrome black/white, applied to primary actions and focus states.

| Token | Light theme | Dark theme | Use |
| :--- | :--- | :--- | :--- |
| Background | `#FFFFFF` | `#111111` | Main page canvas |
| Foreground | `#171717` | `#F5F5F5` | Primary text and icons |
| Surface | `#FAFAFA` | `#1A1A1A` | Occasional raised or inset surface |
| Muted text | `#737373` | `#A3A3A3` | Supporting copy and metadata |
| Border | `#E5E5E5` | `#333333` | Card outlines, inputs, separators |
| Accent | `#171717` | `#F5F5F5` | Primary buttons and selected controls |
| Accent foreground | `#FFFFFF` | `#171717` | Text on accent surfaces |

Check text and control contrast in both themes. Do not introduce colorful status badges; use text, neutral fills, and icons to communicate state.

## 3. Typography

Use **Inter** as the interface sans-serif, with a system sans-serif fallback. Use regular weight for body text and medium or semibold for labels and headings. Avoid oversized display typography and excessive bolding.

| Role | Size | Weight | Use |
| :--- | :--- | :--- | :--- |
| Page title | 30–32 px | 600 | Main page heading |
| Section heading | 20–22 px | 600 | Page sections |
| Event title | 16–18 px | 500–600 | Catalogue and detail title |
| Body | 14–16 px | 400 | Descriptions and form content |
| Metadata | 12–13 px | 400–500 | Date, venue, ticket details |

Use sentence case and concise labels. Keep line lengths comfortable for event descriptions and forms.

## 4. Spacing and layout

Use a 4 px spacing base. Common gaps are 8, 16, 24, and 32 px; reserve larger spacing for section separation and page margins. Maintain a readable content width and consistent alignment across catalogue, detail, and account pages.

On event cards, group date and venue as compact metadata, then distinguish price or availability without adding extra panels. On narrow screens, collapse the grid and filters cleanly while keeping key event information visible.

## 5. Cards and controls

### Event cards

- White or near-black theme surface with a thin neutral border.
- Modest corner radius; no default shadow.
- Comfortable internal spacing, clear title, compact metadata, and an easy-to-find price.
- Use separators and whitespace sparingly; avoid nested cards and decorative category blocks.
- If event imagery is unavailable, keep the layout typographic rather than adding generated gradients.

### Buttons

- **Primary:** monochrome filled button with contrasting text, reserved for the main action on a view.
- **Secondary:** transparent or surface-colored button with a thin neutral border.
- **Quiet:** text button for low-priority actions.
- Use consistent control height and modest rounding. Provide visible hover, keyboard focus, disabled, and loading states.

Inputs, selects, and checkboxes should follow the same restrained border and focus treatment. Keep labels visible and errors concise.

## 6. Dark mode

Support light and dark themes with `next-themes`. Use a near-black canvas rather than pure black, off-white text, dark neutral borders, and the same hierarchy in both themes. Theme switching should not change spacing or component structure. Verify readable contrast, focus rings, disabled states, and overlays in each theme.

## 7. shadcn/ui components

Use only the components needed by the Day 2 foundation and planned screens; add more as actual UI work requires.

- **Structure and navigation:** `Button`, `DropdownMenu`, `Sheet`, `Separator`
- **Catalogue and filters:** `Card`, `Badge`, `Input`, `Select`, `Checkbox`, `Popover`, `Calendar`
- **Forms and feedback:** `Form`, `Label`, `Alert`, `Dialog`, `Sonner`
- **Loading:** `Skeleton`

Use badges sparingly for event category or state, not as decoration. Avoid using cards as a default wrapper for every page section.

## 8. Implementation notes

- This proposal sets visual direction; it does not add endpoints, payload fields, or database schema.
- Frontend API integration must continue to use generated OpenAPI types and the documented API contract.
- No third-party dependencies are proposed here. The Day 2 foundation prompt separately lists its intended frontend dependencies.
- Review the design in catalogue, event detail, authentication, and mobile navigation views when implementing the frontend foundation.
