# Highway Pharmacy Website

Bilingual static HTML/CSS/JavaScript website for Farmacias Aliadas Highway Pharmacy.

## Project Type

- Framework: none
- Build step: none
- Cloudflare Pages build command: leave empty / none
  - If the Cloudflare UI requires a command, use `exit 0`
- Cloudflare Pages build output directory: `.`
- Environment variables: none

The deployment root must contain `index.html`, `en/`, `es/`, `styles.css`, `app.js`, `_redirects`, and `assets/`.

## Cloudflare Pages Routing

`_redirects` sends `/` to the Spanish homepage and applies language-specific SPA fallbacks:

- `/en/*` -> `/en/index.html`
- `/es/*` -> `/es/index.html`

This keeps root assets such as `/assets/...`, `/styles.css`, and `/app.js` outside the wildcard fallback rules.

The committed `en/index.html` and `es/index.html` documents provide language-correct metadata before JavaScript runs. JavaScript updates canonical URLs, Open Graph URLs, and hreflang links for the current localized route.

## Validation

Run the deployment validator before publishing:

```bash
python3 scripts/validate_site.py
```

## Cloudflare-Compatible Local Preview

Use Wrangler to preview Pages routing and `_redirects` behavior:

```bash
npx wrangler pages dev .
```

Then test routes such as:

- `http://localhost:8788/es/`
- `http://localhost:8788/en/`
- `http://localhost:8788/es/servicios`
- `http://localhost:8788/en/services`

A plain `python3 -m http.server` preview can display the root document, but it does not process Cloudflare Pages `_redirects` and is not route-accurate.

## Deployment

1. Connect the repository to Cloudflare Pages.
2. Select no framework preset.
3. Leave the build command empty, or use `exit 0` if required.
4. Set the build output directory to `.`.
5. Deploy and validate the generated `*.pages.dev` preview URL before attaching `highwaypharmacypr.com`.

Official references:

- [Cloudflare Pages redirects](https://developers.cloudflare.com/pages/configuration/redirects/)
- [Cloudflare Pages local development](https://developers.cloudflare.com/pages/functions/local-development/)

## Contributing — branch protection

Direct pushes to `main`/`master` are blocked; use a feature branch + PR.

- **Claude Code hook**: `.claude/hooks/block-push-to-main.py` (+ `.claude/settings.json`), scoped to this repo (needs `python3`).
- **git pre-push hook**: `.githooks/pre-push`. Enable per clone: `git config core.hooksPath .githooks`. Override: `ALLOW_PUSH_TO_MAIN=1 git push …` or `git push --no-verify`.

CI (`.github/workflows/ci.yml`) runs the static-site checks (site validator if present, `node --check`, HTML parse) on every PR and push to `main`.
