# Task: Split-Screen Loading Animation (Paper 1706.03762 Only)

## Summary

Implement a **split-screen loading view** on the ArXivisual paper page. The **left panel** shows the paper (with a highlighted section header); the **right panel** shows the corresponding ArXivisual video/summary for that section. As the loading animation progresses, the highlight moves through section headers and the right side updates to show the matching explanation. This behavior is **only for the paper at `https://www.arxivisual.org/abs/1706.03762`** and is **fully hardcoded** — no dynamic data fetching or conditional logic for other papers is required.

---

## Scope

| Item | Value |
|------|--------|
| **Page** | `https://www.arxivisual.org/abs/1706.03762` only (route: `/abs/1706.03762`) |
| **Paper** | "Attention Is All You Need" (arXiv ID: `1706.03762`) |
| **Implementation** | Hardcoded only. No API calls, no generic logic for other papers. |
| **Where to implement** | Frontend: `frontend/app/abs/[...id]/` (and/or components used only when `id` is `1706.03762`) |

---

## Requirements

### 1. Split-screen layout

- **Left side (~50%)**: Represents the **paper**. Show a static or simplified representation of the paper (e.g. a fixed list of section headers that match the real paper structure, or a mock “paper” strip).
- **Right side (~50%)**: Represents the **ArXivisual output**. Show the current section’s visualization: video player and/or text summary for the highlighted section.

### 2. Section-based animation

- Define a **fixed, ordered list of sections** for 1706.03762. Use the actual section titles from the demo paper, for example:
  1. **The Transformer Architecture**
  2. **Scaled Dot-Product Attention**
  3. **Multi-Head Attention**
  4. **Positional Encoding**
  5. **Why Self-Attention**

- **Left panel:** At each step of the loading animation, **highlight exactly one section header** (e.g. background, border, or typographic emphasis) to indicate “this is the section we are explaining.”
- **Right panel:** For that same step, show the **corresponding ArXivisual content** for that section:
  - Use the **hardcoded** video URLs and summaries already defined for 1706.03762 (e.g. in `frontend/lib/mock-data.ts`: `MOCK_PAPER.sections` with `video_url` and `content`/title).
  - Display the video (or a placeholder frame) and/or a short text summary.

### 3. “Real-time” progression

- The loading experience should **animate through the sections in order** (e.g. every N seconds, or tied to a single progress timeline).
- For each step:
  - Update the **left** highlight to the next section header.
  - Update the **right** content to the next section’s video/summary.
- Optionally, a single global “loading” progress (e.g. 0% → 100%) can drive which section is active; the exact timing can be hardcoded (e.g. 5 sections over ~5–10 seconds).

### 4. When this view is shown

- Show this split-screen loading view **only when**:
  - The user is on `/abs/1706.03762` (i.e. `arxivId === "1706.03762"`), and
  - The page is in its **loading** or **processing** state (before the full paper + scrollytelling view is shown).
- For any other paper ID or after loading is complete, do **not** show this split-screen; keep existing loading/processing UI for others.

### 5. Hardcoding rules

- **Section list:** Hardcode the 5 section titles (and optionally IDs) for 1706.03762. Do not derive them from API or from route beyond checking `arxivId === "1706.03762"`.
- **Videos and text:** Use existing hardcoded demo data (e.g. `getDemoPaper("1706.03762")` or direct references to `MOCK_PAPER.sections`) for video URLs and summaries. No fetching of section content from the backend for this view.
- **Timing:** Hardcode durations (e.g. time per section, or total loading duration and number of steps). No configuration or env-based timing is required.
- **No reuse for other papers:** Do not build a generic “split-screen loading for any paper.” Only 1706.03762 should get this experience.

---

## Acceptance Criteria

- [ ] On `https://www.arxivisual.org/abs/1706.03762`, during loading/processing, a split-screen is visible: paper on the left, ArXivisual content on the right.
- [ ] The left side shows section headers for "Attention Is All You Need"; exactly one header is highlighted at a time.
- [ ] The right side shows the video and/or summary that corresponds to the currently highlighted section (Transformer Architecture → Scaled Dot-Product → Multi-Head Attention → Positional Encoding → Why Self-Attention).
- [ ] The highlight and right-side content advance in sync (e.g. every N seconds or along a single progress bar).
- [ ] All section titles, video URLs, and copy are hardcoded for 1706.03762; no dynamic API data is used for this view.
- [ ] For any other paper (e.g. `/abs/2005.14165`) or when not in loading/processing, the existing loading/processing UI is unchanged.

---

## Suggested implementation notes

- **Route check:** In `frontend/app/abs/[...id]/page.tsx`, when rendering loading/processing state, conditionally render this split-screen component only if `arxivId === "1706.03762"`.
- **Data source:** Import and use `getDemoPaper("1706.03762")` or `MOCK_PAPER` from `@/lib/mock-data` to get the 5 sections with `title`, `video_url`, and `content` (or reuse the same structure in a local constant in the component).
- **Component:** Consider a dedicated component, e.g. `SplitScreenLoading1706` or `DemoPaperLoadingView`, that encapsulates the left panel (paper + section list + highlight) and right panel (video + summary), and a simple timer or `setInterval`/`requestAnimationFrame` to advance the active section index.
- **Styling:** Reuse existing design system (e.g. Tailwind, `GlassCard`, dark theme) so the split-screen fits the rest of the app.

---

## Out of scope

- Changing behavior for papers other than 1706.03762.
- Fetching section list or videos from the API for this loading view.
- Making section list or timing configurable (env, CMS, or feature flags).
- Changing the final “ready” state of the paper page (scrollytelling, etc.); only the loading/processing phase is in scope.
