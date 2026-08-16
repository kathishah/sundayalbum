# Journal Index

Development log for Sunday Album. Entries fall into two categories:
- **Build log** — phase-by-phase summaries of what was built
- **Fixes & decisions** — post-phase algorithm changes, bug fixes, and decision records

---

## Build Log (phases)

| Date | File | Summary |
|------|------|---------|
| 2026-02-10 | [phase-1-project-setup](2026-02-10-phase-1-project-setup.md) | Project scaffold, HEIC/DNG loading, CLI skeleton, EXIF orientation |
| 2026-02-15 | [phase-2-page-detection](2026-02-15-phase-2-page-detection.md) | GrabCut page boundary detection, perspective correction |
| 2026-02-15 | [phase-3-glare-detection](2026-02-15-phase-3-glare-detection.md) | HSV-based glare detection, severity map, sleeve vs print classification |
| 2026-02-15 | [phase-4-glare-removal](2026-02-15-phase-4-glare-removal.md) | Single-shot OpenCV inpainting (intensity correction + TELEA/NS + contextual fill) |
| _(Phase 5 deferred)_ | — | Multi-shot glare compositing — requires multi-angle test images, not yet implemented |
| 2026-02-16 | [phase-6-photo-detection](2026-02-16-phase-6-photo-detection.md) | Contour-based photo detection, decoration filter, pipeline reorder (detect before glare) |
| 2026-02-16 | [phase-7-geometry-correction](2026-02-16-phase-7-geometry-correction.md) | Keystone, rotation detection, dewarp implementation |
| 2026-02-16 | [phase-8-color-restoration](2026-02-16-phase-8-color-restoration.md) | White balance, deyellowing, CLAHE-based fade restoration, sharpening |
| 2026-02-16 | [phase-9-pipeline-integration](2026-02-16-phase-9-pipeline-integration.md) | End-to-end pipeline wiring, AI quality check, output naming |

---

## Fixes & Decisions

| Date | File | Summary |
|------|------|---------|
| 2026-02-16 | [single-print-fix](2026-02-16-single-print-fix.md) | Fix: single-print false splits — adaptive max-area threshold + Canny edge fallback |
| 2026-02-17 | [multi-photo-detection-fix](2026-02-17-multi-photo-detection-fix.md) | Fix: three_pics detection — removed `_is_isolated_print` bypass, added projection-profile fallback |
| 2026-02-18 | [openai-glare-and-orientation](2026-02-18-openai-glare-and-orientation.md) | Feature: switched glare removal to OpenAI gpt-image-1 + added Claude AI orientation step |
| 2026-02-19 | [rotation-fix](2026-02-19-rotation-fix.md) | Fix: disabled Hough-line rotation (fires on content); clarified AI direction prompt |
| 2026-02-20 | [color-restoration-fix](2026-02-20-color-restoration-fix.md) | Fix: gray-world white balance tuning, conservative deyellowing |
| 2026-03-04 | [photo-boundary-detection-fix](2026-03-04-photo-boundary-detection-fix-and-background-stripping.md) | Fix: spine-separated album pages; background stripping improvements |
| 2026-04-09 | [color-restore-rethink](2026-04-09-color-restore-rethink.md) | Rework: replaced CLAHE with adaptive brightness lift + vibrance saturation |
| 2026-04-09 | [dev-branch-strategy](2026-04-09-dev-branch-strategy.md) | Decision: feature → dev → main branch model, dev as staging environment |
| 2026-04-10 | [public-website-plan](2026-04-10-public-website-plan.md) | Plan: www.sundayalbum.com public site — page structure, pricing, video script, DNS |
| 2026-04-10 | [public-website](2026-04-10-public-website.md) | Implementation: (public) route group, 5 marketing pages, pipeline page with real images, BeforeAfterSlider, re-run integration |
| 2026-04-11 | [ses-email-deliverability](2026-04-11-ses-email-deliverability.md) | SES/Gmail via amazonses diagnosis; AWS CLI snapshot; DNS; plan: domain verify, DKIM/SPF/DMARC, production access |
| 2026-04-12 | [photo-boundary-override](2026-04-12-photo-boundary-override.md) | Plan: user-editable photo detection regions + reprocess from photo_split; fixes photo_split re-detection bug |
| 2026-04-12 | [reprocess-ui-gaps](2026-04-12-reprocess-ui-gaps.md) | Plan: fill reprocess gaps — 3 unwired macOS step views, web saturation_boost naming mismatch, new CLI flags |
| 2026-04-13 | [step-function-routing](2026-04-13-step-function-routing.md) | Plan: move skip routing into Step Functions Choice states; handlers become position-agnostic |
| 2026-08-15 | [monorepo-layout](2026-08-15-monorepo-layout.md) | Spec: rearrange repo into apps/ packages/ services/; keep `src` import names |
| 2026-08-15 | [monorepo-implementation-plan](2026-08-15-monorepo-implementation-plan.md) | Plan: 5 commits (git-mv → pyproject/conftest → Docker/CDK/CI → macOS PYTHONPATH → docs) |
