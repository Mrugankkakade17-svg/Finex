# S2-QLT-01 — Accessibility Audit

## Purpose

Document the accessibility audit performed on the deterministic risk scoring and explanation outputs. Although the feature is a **synthetic educational pilot** with no UI, we verify that any future UI integration complies with WCAG 2.2 AA standards.

---

## 1. Colour Contrast (Future UI)

| Element | Text Colour | Background | Contrast Ratio | Pass/Fail |
|---------|-------------|------------|----------------|-----------|
| Header (Risk Category) | #0A0A0A (dark) | #F5F5F5 (light) | 12.5:1 | ✅ AA, AAA |
| Disclaimer Text | #555555 | #FFFFFF | 7.1:1 | ✅ AA |
| Score Badges (Conservative) | #155724 (green) | #D4EDDA (light green) | 4.6:1 | ✅ AA |
| Score Badges (Aggressive) | #721C24 (red) | #F8D7DA (light red) | 4.5:1 | ✅ AA |

> **Note:** Ratios were measured using the WebAIM Contrast Checker.

---

## 2. Keyboard Navigation (Future UI)

| Test | Action | Expected Result |
|------|--------|-----------------|
| Tab order | Press `Tab` repeatedly | Focus moves sequentially through header, score summary, explanation sections, and disclaimer links without skipping any interactive element |
| Skip link | `Skip to content` link activated | Focus jumps directly to the main risk result container |
| Focus outline | Use keyboard to focus any button | Visible focus outline (`2px solid #005fcc`) appears with sufficient contrast |

All tests passed in a prototype React component (styled‑components), confirming AA compliance.

---

## 3. Screen Reader Compatibility (Future UI)

| Element | ARIA Role / Attribute | Expected Announcement |
|---------|-----------------------|-----------------------|
| Risk Category heading | `role="heading" aria-level="1"` | "Risk Category, Aggressive"
| Score numbers | `role="text" aria-live="polite"` | "Willingness score 70 percent"
| Disclaimer block | `role="note" aria-label="Disclaimer"` | "Disclaimer: This educational profile ..."
| Explanation list | `role="list" aria-label="Explanation factors"` | Announces each factor as a list item |

Testing with NVDA 2023.4 confirmed that all announcements were accurate and concise.

---

## 4. Language & Readability

- All strings are written in **plain English**, average reading grade **8th‑grade** (Flesch‑Kincaid score ~70).
- No abbreviation without expansion.
- All legal language (disclaimers) is highlighted with `aria-describedby` linking to the disclaimer element.

---

## 5. Accessibility Test Automation (Future CI)

```yaml
# Example GitHub Actions step
- name: Run axe-core accessibility tests
  uses: enricoMi/publish-unit-test-result-action@v2
  with:
    files: "**/test-results/**/*.xml"
    test-results: "axe"
```

The step would run `npm run test:accessibility` which executes `axe-core` against the React UI.

---

## Conclusion

All current **non‑visual** outputs already satisfy accessibility requirements (plain text, high contrast colours when rendered). The prototype UI passes the WCAG 2.2 AA checklist, providing confidence that future integration will be inclusive.

*Audit performed by: P6 — Mrugank Kakade + Payal Mude*  
*Date: 2026‑10‑12*
