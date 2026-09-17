# Align application colors with the approved entry design

The saved Instance primary color is already `blue`. The older temporary body tokens overrode it with teal accents and green-tinted dark surfaces. This follow-up changes only the temporary stylesheet and its existing browser verification expectation.

| Before | After |
| --- | --- |
| Separate light palettes for application and landing. | Body and entry share the exact approved landing-card palette: pale blue surfaces, navy text/actions, blue links and selections. The duplicated entry token definitions are removed. |
| Teal/cyan application accents and green-tinted dark surfaces. | Deep blue application surfaces with readable lighter blue links/focus in dark mode. Primary actions retain the landing's navy/white treatment; dark-mode actions gain a visible inset outline. |
| Independent application and entry status colors. | Shared light status colors, while dark application status colors stay readable; entry continues to use its own light tokens under either theme. |

The landing's resolved colors, layout, background, imagery and copy remain unchanged. The side-panel scope fix remains intact. Saved settings, backend behavior and the generic build are unaffected; the WLC build flag still gates the entire stylesheet.

Verify exact before/after entry screenshots, palette parity for task/admin/chat screens, both themes, primary button text/border and link contrast, mobile 320px, keyboard focus, existing frontend tests and production build. The existing `verify-browser-v2.mjs` expects the updated deep-blue dark surface.

Rollback: revert the primary-action edge follow-up first, then the palette commit `8e5a2ce`, to restore the prior application palette. The operator record lists the exact final source revision and retained image. Operational rollback retains the previous frontend image and recreates only `frontend`, preserving all backend/Sage containers and stored settings. Deployment records are in workspace `docs/releases/wlc-color-alignment/` outside the repository.

Deployed application revision: `b8f1625`. Verification completed: 493 tests, production build, palette/contrast/keyboard/mobile checks, seven live public browser checks and 61 matching public files. All four entry screenshot comparisons were pixel-identical. Current image identities, tested complete removal and operational commands are in [the rollback runbook](ROLLBACK.md).
