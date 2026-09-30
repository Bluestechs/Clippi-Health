# Accessibility status

Accessibility is a high-priority product feature for both the Electron desktop app and the generated web dashboard. The target is **WCAG 2.2 Level AA**. **Clippi-Health does not currently claim WCAG conformance.** This is an engineering assessment with sampled regression evidence, not a completed audit or certification.

Assessment date: 2026-09-30. Scope: the repository's dashboard template, Electron renderer, and the fictional Sally Seastar demo. Real health records, external provider authentication pages, operating-system dialogs, original attachments, and generated PDF/Markdown documents were not assessed. The full import/connect/build/recovery process still requires assistive-technology testing.

Standards: [WCAG 2.2](https://www.w3.org/TR/WCAG22/) and the [WAI-ARIA tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/). An automated or static check alone cannot establish conformance across complete pages and processes.

## Assessment and fixes

| Area / relevant criteria | Finding and current evidence | Status |
|---|---|---|
| Selection state — 4.1.2 | The dashboard helper wrote empty ARIA booleans, so active filters/tests and the selected record were not styled or exposed correctly. It now emits explicit true/false values. Fictional smoke checks verify the selected topic, date range, tests, and record. | Fixed in this slice; screen-reader interpretation pending |
| Tabs and relationships — 1.3.1, 2.1.1, 4.1.2 | Both renderers now use named tab lists, named tab panels, controls/label relationships, and one tab stop with Arrow Left/Right and Home/End navigation. The theme menu supports Arrow Up/Down and Home/End, plus its existing Escape return. | Implemented; full assistive-technology verification pending |
| Input/control names — 2.4.6, 2.5.3, 3.3.2 | Record/test search, source selection, notes, event fields, and event removal have accessible names. Topic actions include the topic in their name. Table headers use column scope. | Implemented; error/recovery workflows pending |
| Bypass and focus — 2.4.1, 2.4.3, 2.4.7, 2.4.11 | Skip links, explicit focus outlines, focusable view/reader destinations, and focus return to the opened result were added. Filters reconcile a reader that no longer matches. Tab round trips preserve the reader; browser Back restores view/filter/record state. | Demo navigation checks pass; a native Tab-key check at 400% verifies visible, unobscured focus. All-platform focus audit pending |
| Status — 4.1.3 | Record result counts and desktop build/save/availability states have polite status regions. No-match searches clear the stale reader. | Implemented; announcements and import/connector errors pending |
| Text alternatives — 1.1.1, 1.3.1 | Charts have descriptive names. A timeline event list provides keyboard access to the same event details. Vitals now have expandable daily-summary tables; lab charts already offer exact value tables. | Lab orders/comments and marked events, timeline details, and dense-series averages now have expandable text equivalents. Fictional equivalence checks pass; full assistive-technology review pending |
| Dragging/keyboard chart interaction — 2.1.1, 2.5.7 | Each chart now has labeled From/To dates, Apply, Previous/Next window, Reset view, and a live range status. Paired glucose/insulin charts share one range control. Dragging remains optional. Date windows survive tabs/theme changes and browser history; choosing a coarse date preset resets the affected chart windows. Y axes use automatic scaling so date controls replace the available drag interaction. | Implemented locally; 15 fictional chart checks pass — [#7](https://github.com/bennydogg/clippi-health/issues/7) |
| Hover/focus disclosures — 1.4.13 | Lab comments/order names are ordinary table cells. Vitals tables include the same 30-day averages shown in hover. Marked events link to complete timeline detail and records. Plotly tooltip text accepts pointer interaction; Escape dismisses it until the pointer leaves the chart. A demo check verifies dismissal and tooltip pointer events. Physical-pointer persistence/hoverability and assistive-technology traversal still require manual review. | Implemented with sampled evidence; manual tooltip review pending — [#7](https://github.com/bennydogg/clippi-health/issues/7) |
| Contrast/color — 1.4.1, 1.4.3, 1.4.11 | Paper/Dark tokens were adjusted for muted text, control borders, links, and status flags. Rendered foreground/background composition is measured on visible ordinary text and selected control boundaries in all six shell panels and four dashboard views, across Paper/Dark/System themes. The measured dark flag failure (4.4:1 on a tinted row) was corrected. Checkmarks and outlines supplement selected-state washes. Forced-color system tokens and selected/focus outlines were added. | Sampled checks pass; SVG, gradients/images, all hover states, and native OS combinations remain outside this measurement — [#8](https://github.com/bennydogg/clippi-health/issues/8) |
| Resize/reflow/spacing — 1.4.4, 1.4.10, 1.4.12 | Shell minimum width is now 360px. Header/tabs/rows wrap, and short/narrow layouts release nested/sticky scrolling. Chart/table overflow stays inside its container; long topic/source labels wrap. Actual Electron zoom at 200% and 400%, 200% computed text enlargement, and the WCAG text-spacing override are exercised across six shell panels and four dashboard views. The dashboard is narrower than 320 CSS px inside the magnified shell; no whole-page horizontal overflow is allowed. | Sampled checks pass; full user workflows and Windows/Linux native conditions pending — [#8](https://github.com/bennydogg/clippi-health/issues/8) |
| Target size — 2.5.8 | Buttons have minimum width/height of 28px, with larger narrow-dashboard controls. Zoom probes reject visible enabled buttons below 24px in either dimension. Dense tables retain independent scrolling. | Sampled checks pass; native inputs/label hit areas and all spacing exceptions need manual review — [#8](https://github.com/bennydogg/clippi-health/issues/8) |
| Reduced motion | Scroll behavior respects the operating-system reduced-motion preference. | Implemented; not an AA conformance claim |
| Screen readers, keyboard traps, errors — 2.1.2, 3.3.1, 4.1.2, 4.1.3 | Source/DOM checks and synthetic UI assertions cannot establish VoiceOver/NVDA/Linux screen-reader behavior, iframe traversal, error announcements, or complete-process recovery. | Pending — [#9](https://github.com/bennydogg/clippi-health/issues/9) |

Other WCAG 2.2 A/AA criteria remain **unassessed** unless evidence above explicitly covers them. The sampled UI contains no audio/video, timed tasks, flashing content, or hosted sign-in, but imported content and provider workflows prevent a blanket product-wide “not applicable” claim. Language/title metadata exist; orientation, multiple navigation methods, content order, consistent help, error prevention for edits, redundant entry, and accessible external authentication require complete-process review. This document deliberately does not mark the whole product as passing any criterion based on one fixture.

## Verification

Run from the source checkout using only fictional fixtures:

```bash
TMPDIR=/tmp python3 -m unittest discover -s tests -p 'test_demo_data.py'
cd app
TMPDIR=/tmp npm run typecheck
TMPDIR=/tmp npm test
TMPDIR=/tmp npm run smoke
# Faster iteration on the same isolated fictional store:
TMPDIR=/tmp npm run smoke -- --smoke-accessibility-only
# Chromium forced-color emulation (assert the reported media-query state):
TMPDIR=/tmp npm run smoke -- --smoke-accessibility-only --force-high-contrast
```

The smoke runner creates a separate user profile and record store, checks return-folder restoration, uses the real builder and dashboard, and writes private screenshots into a temporary folder. Do not substitute the owner's records or upload screenshots/records to a hosted accessibility scanner.

This assessment verified:

- TypeScript type checking and all 55 Electron component tests.
- Two Python demo tests, including refusal to seed an existing personal store and a populated real build/search pipeline.
- Nineteen dashboard navigation/accessibility smoke assertions: topic context, source reset, selected states, reader reconciliation/focus, result status, record/list returns, custom topic chart selection, keyboard tabs, chart/timeline alternatives, and browser Back.
- Five 320px dashboard checks: record/list return, list focus, record/chart reflow, and visible topic context.
- Fifteen new chart checks: shared Apply/Previous/Next/Reset, invalid-date rejection, retained tab ranges, labs/timeline date controls, active range status, source-detail equivalence, averages, marked events, and tooltip dismissal/pointer events.
- Seventy-three visual condition samples per run: 20 page-zoom samples, 10 text-resize samples, 10 spacing samples, long-topic/source fixtures, one native Tab-key focus check at 400%, and 30 rendered contrast samples. Visible enabled button target dimensions and ordinary control clipping are checked with the zoom samples.
- In the ordinary-color final run, the minimum sampled text ratio was 4.76:1, with no measured text/control-border failures across 30 contrast samples. SVG plots and every possible hover/disabled state are not included in that minimum.
- Chromium forced-color emulation reports `(forced-colors: active)` as true and passes the same visual samples. This is not a Windows High Contrast or macOS Increase Contrast usability test.
- Existing paired-chart synchronization/reset, both explicit themes, desktop tab screenshots, demo privacy guards, and original-folder restoration.

Verification used the repository's isolated Electron smoke runner. It writes `accessibility-evidence.json` plus private fictional screenshots under the reported temporary output directory. Browser automation disconnected during implementation; a fresh standalone HTTP browser session and Windows/Linux native UI were not verified. Source edits do not automatically update an already-generated personal dashboard or an already-running Electron renderer. For this local review, the served dashboard HTML was refreshed from the new template with its embedded record payload preserved byte-for-byte. Refresh the web page to see it. Restart/reload the Electron renderer to load the shell changes; preserve unsaved edits before doing so.

## Remaining release-priority work

1. [#7 — implemented locally; manual hover/assistive-technology review remains](https://github.com/bennydogg/clippi-health/issues/7).
2. [#8 — local fixes and sampled regression checks complete; native-platform/full-workflow review remains](https://github.com/bennydogg/clippi-health/issues/8).
3. [#9 — assistive-technology assessment and automated WCAG regression gate](https://github.com/bennydogg/clippi-health/issues/9).

Keep this status document current as those issues close. Use synthetic fixtures in accessibility CI and report separately what was measured, what was manually verified, and what remains untested.
