# JJs Event Agent

JJs Event Agent discovers upcoming **free ($0)** events in Singapore, applies strict timing and topic rules, and publishes the curated result to a responsive, self-contained calendar dashboard deployed with GitHub Pages.

The repository is public so GitHub Pages works on the current account plan. No live credentials, browser profiles, cookies, or private message bodies belong in Git. The Pages artifact contains only the curated fields shown on each card. Summaries from private-message sources are generated from safe event metadata rather than copied from private posts.

## What qualifies

An event is included only when all of these checks pass:

- **Topic:** at least one of AI, Tech, Robotics, Marketing, Business, or Networking.
- **Location:** the listing or message explicitly identifies Singapore or a recognized Singapore area.
- **Price:** admission is explicitly stated as free, $0, no cost, or equivalent. “Free food” by itself does **not** prove free admission.
- **Date:** the event is upcoming and within `LOOKAHEAD_DAYS` (90 by default).
- **Time:** Monday–Friday strictly after 6:00 PM SGT; Saturday–Sunday from 6:00 AM through 5:59 PM SGT.

Events mentioning free food, free drinks, pizza, beer, wine, refreshments, refreshment, buffet, light bites, or networking receive a higher ranking and highlighted cards.

## Source architecture

| Source | Adapter | Authentication | Notes |
|---|---|---|---|
| LinkedIn | Playwright | `li_at` or cookie JSON | Reads the Following page, then recent activity for followed profiles. |
| Lu.ma | Playwright | Optional cookie JSON | Reads the Singapore listing, signed-in home view, and explicitly supplied private/unlisted URLs. |
| Eventbrite | Playwright | Cookie JSON | Uses an authenticated browser session for Singapore free-event search and event details. |
| Meetup | Requests + BeautifulSoup | None | Uses the Singapore event search and schema.org/card data. |
| Google Developer Groups | Playwright + schema.org | None | Reads the public events list and GDG Singapore chapter, then verifies detail pages. |
| WhatsApp | Playwright persistent context | Saved browser profile | Reads only the two exact configured groups and never sends messages. |

Each source is isolated. A logged-out or changed site reports a source failure while other sources continue and the dashboard is still regenerated. Set `SOURCE_FAILURE_MODE=fail` to make the run fail after the dashboard is produced.

GDG is intentionally conservative: a label such as “external registration” is not treated as free. The source must explicitly say “free registration,” “free admission,” or provide another real $0 signal before the event can pass the price filter.

## Dashboard views and summaries

Events are grouped chronologically by month and day, with weekday evenings and weekend daytime events shown in the same calendar-style agenda. The summary tiles break down explicit F&B, weekday, weekend, and networking counts. Search can be combined with source and F&B filters.

Every event card includes a summary of at most 99 words. Public event-page descriptions may be condensed into that summary. LinkedIn and WhatsApp message bodies are never copied into the public page; their cards receive a short metadata-based summary instead. “F&B not stated” means only that the source did not explicitly mention food or drinks—it does not claim that none will be served.

> Automated access can be limited by each platform's terms and UI changes. Use only accounts and content you are authorized to access. This project does not bypass CAPTCHAs, checkpoints, access controls, or rate limits.

## Local setup

Requirements: Python 3.11+ and a Chromium-compatible environment.

```bash
git clone https://github.com/jeraldine-t/JJs-Event-Agent.git
cd JJs-Event-Agent
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium
cp .env.example .env
```

Fill `.env`, then run:

```bash
python -m event_agent
```

For a credential-free smoke run that overwrites the local dashboard:

```bash
python -m event_agent --sources ""
```

Quality checks:

```bash
ruff check .
pytest
```

## LinkedIn session

The current public deployment intentionally keeps LinkedIn login data **off GitHub**, including GitHub Actions Secrets. Authenticated LinkedIn collection is performed through the signed-in local browser; only qualifying event fields are rendered into `index.html`.

For a trusted local or self-hosted machine, the scraper also supports the value of LinkedIn's `li_at` session cookie in a local `.env`:

```dotenv
LINKEDIN_LI_AT=your_value_here
```

Alternatively, `LINKEDIN_COOKIES_JSON` accepts a Playwright-compatible JSON array (or its base64 encoding):

```json
[{"name":"li_at","value":"...","domain":".linkedin.com","path":"/","secure":true,"httpOnly":true}]
```

Treat the value like a password. Never commit it, paste it into chat, or upload it to this public repository. If LinkedIn redirects to login or a checkpoint, refresh the local session manually; the agent deliberately does not bypass the checkpoint.

The included login helper can create ignored local cookie JSON for a self-hosted run:

```bash
python -m event_agent.bootstrap cookies linkedin
```

## Eventbrite session

Eventbrite public search rejects plain hosted HTTP requests, so its adapter uses Playwright. The current deployment reuses the signed-in local browser for authenticated manual collection and does not upload the session to GitHub. A trusted self-hosted machine can create an ignored local session file with:

```bash
python -m event_agent.bootstrap cookies eventbrite
```

The exported array preserves the correct `.eventbrite.com` and `.eventbrite.sg` cookie domains. Keep it local and rotate it if Eventbrite returns a sign-in page or access challenge.

## Lu.ma session and private links

Set `LUMA_COOKIES_JSON` to a Playwright-compatible JSON cookie array from your signed-in Lu.ma session. Add known private/unlisted event links to the comma-separated `LUMA_PRIVATE_URLS` value. The adapter also scans the authenticated home view for account-visible event links.

An unlisted URL is often itself a bearer credential. Store `LUMA_PRIVATE_URLS` as a GitHub **Secret**, never in `.env.example`, logs, issues, or commits.

## WhatsApp Web persistent login

Create the browser profile once on the machine that will run the scraper:

```bash
PLAYWRIGHT_HEADLESS=false python -m event_agent.bootstrap whatsapp --profile .state/whatsapp
```

Scan the QR code if prompted and wait until the chat list is visible before pressing Enter in the terminal. The ignored `.state/whatsapp` directory then keeps the login between runs.

WhatsApp Web login state is a browser profile, not a small portable cookie. A GitHub-hosted runner is erased after each job, so WhatsApp cannot reliably remain signed in there. WhatsApp is therefore excluded from the default scheduled source list. To opt in, attach a trusted self-hosted runner and configure:

- repository variable `SCRAPER_RUNNER` = `self-hosted` (or a matching runner label);
- repository variable `WHATSAPP_USER_DATA_DIR` = the absolute profile path on that runner;
- workflow `ENABLED_SOURCES` to include `whatsapp`; and
- a locked-down runner account with access to that directory.

Never commit, artifact, or upload the WhatsApp profile—it grants account access and may contain local message data.

The two monitored chats are exact-name matches:

- `Codex Community - Main Chat`
- `non-RWA events, programs, initiatives`

## GitHub Actions privacy and variables

The public repository is intentionally configured with **zero GitHub Actions Secrets**. LinkedIn cookies, Eventbrite cookies, passwords, browser profiles, and raw source messages must stay on the local machine and must never be committed or uploaded as artifacts.

Optional repository variables:

| Variable | Purpose |
|---|---|
| `SCRAPER_RUNNER` | Defaults to `ubuntu-latest`; use `self-hosted` for persistent WhatsApp. |
| `WHATSAPP_USER_DATA_DIR` | Absolute persistent profile path on the self-hosted runner. |

The workflow explicitly requests `contents: write`, `pages: write`, and `id-token: write`. If an organization policy restricts `GITHUB_TOKEN`, allow Actions read/write access under **Settings → Actions → General → Workflow permissions**, or the dashboard commit will fail.

## Schedule, dashboard commit, and GitHub Pages

`.github/workflows/scraper.yml` runs at **8:00 AM every Sunday in `Asia/Singapore`**, and also supports manual runs from the Actions tab. Scheduled cloud runs can access only anonymous/public sources unless a trusted self-hosted runner is configured. If an automated scrape returns zero events, the workflow preserves the last populated dashboard.

For a privacy-preserving deployment after a local authenticated scrape, run the workflow manually with `refresh_data=false`. It deploys the committed sanitized dashboard without running source collectors.

The workflow:

1. installs and tests the package;
2. installs Playwright Chromium when source collection is enabled;
3. optionally runs the configured source adapters;
4. overwrites `index.html`;
5. commits and pushes `index.html` if it changed; and
6. uploads only `index.html` plus `.nojekyll` as the public Pages artifact.

One-time Pages setup:

1. Open **Settings → Pages**.
2. Under **Build and deployment → Source**, select **GitHub Actions**.
3. Run **Weekly event scrape and Pages deploy** from the Actions tab.

The live project URL is `https://jeraldine-t.github.io/JJs-Event-Agent/` and is recorded on the deployment job. The workflow deploys only the sanitized single-page artifact.

## Environment reference

Every supported variable is documented in `.env.example`. Useful tuning values include:

- `LOOKAHEAD_DAYS` and `MESSAGE_LOOKBACK_DAYS`;
- LinkedIn profile/post caps and Eventbrite/Lu.ma/GDG event caps;
- `EVENTBRITE_SEARCH_URLS` and `MEETUP_SEARCH_URLS` as pipe-separated overrides;
- `SOURCE_FAILURE_MODE=warn|fail`.

## Troubleshooting

- **Empty dashboard:** inspect the expandable run-health panel and Actions logs. Strict $0, Singapore, keyword, date, and time filters intentionally reject ambiguous listings.
- **LinkedIn checkpoint:** refresh your own session cookie. Do not automate checkpoint or CAPTCHA bypass.
- **Eventbrite login/challenge:** refresh `EVENTBRITE_COOKIES_JSON`; the agent does not bypass access challenges.
- **Lu.ma private event missing:** add its exact link to the secret `LUMA_PRIVATE_URLS` and refresh the cookies.
- **WhatsApp skipped in Actions:** use a self-hosted runner with the bootstrapped persistent directory.
- **Pages deployment fails:** enable GitHub Actions as the Pages source and confirm the account plan supports Pages for private repositories.
- **Site selector changed:** Playwright/BeautifulSoup adapters are isolated under `src/event_agent/sources/`; update the affected adapter and its tests without changing the filter/output pipeline.
