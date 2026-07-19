# JJ's Event Agent

JJ's Event Agent discovers relevant upcoming Singapore events, applies topic and timing rules, and creates a responsive calendar dashboard plus a weekly email summary.

The dashboard is public at `https://jeraldine-t.github.io/JJs-Event-Agent/`. The repository contains code, tests, and the sanitized `index.html` only. Login cookies, `.env`, browser profiles, private links, and raw private-message bodies must never be committed or uploaded.

## What qualifies

An event is included only when all of these checks pass:

- **Topic:** AI, Tech, Robotics, Marketing, Business, or Networking.
- **Location:** Singapore or a recognized Singapore area.
- **Admission:** listings with no displayed price or explicit free admission are accepted; an explicit paid ticket price is rejected. Admission labels are intentionally omitted from the dashboard.
- **Date:** upcoming and within `LOOKAHEAD_DAYS` (90 by default).
- **Time:** weekdays strictly after 6:00 PM SGT, or weekends from 6:00 AM through 5:59 PM SGT.

Events mentioning free food, free drinks, pizza, beer, wine, refreshments, buffet, light bites, or networking receive a higher ranking. The dashboard F&B filter lists every detected type and includes “Not stated.”

## Sources and update coverage

| Source | Adapter | Scheduled GitHub-hosted run | Authenticated/local run |
|---|---|---|---|
| Eventbrite | Playwright | Public Singapore search | Same search with optional account cookies |
| Lu.ma | Playwright | Public `https://luma.com/singapore` discovery | Also account-visible and supplied private/unlisted links |
| Meetup | Requests + BeautifulSoup | Public Singapore search | Same public search |
| Google Developer Groups | Playwright + schema.org | Public events and Singapore chapter | Same public search |

> Automated access can be limited by each platform's terms and UI changes. Use only accounts and content you are authorized to access. The project does not bypass CAPTCHAs, checkpoints, access controls, or rate limits.

## Dashboard

Events are grouped chronologically by month and day. Summary tiles show F&B, weekday-evening, weekend-daytime, and networking counts. Cards include:

- event name, SGT date/time, location, source, and registration link;
- a summary of at most 99 words;
- the specific F&B types explicitly mentioned, or “Not stated”; and
- number going, seats remaining, waitlist, or registration status when the source publishes it.

A **Hot pick** badge appears for at least 50 people going, ten or fewer seats left, or a waitlist/full event. No attendee identities are collected.

Private-source message bodies are not copied into the dashboard or email. LinkedIn and WhatsApp entries use safe metadata-based summaries.

## Public dashboard access

The live dashboard is:

`https://jeraldine-t.github.io/JJs-Event-Agent/`

The Pages deployment contains only the generated `index.html` and `.nojekyll`. It does not contain `.env`, browser state, Playwright cookies, source code, raw messages, or SMTP credentials.

For deployment history, use:

`https://github.com/jeraldine-t/JJs-Event-Agent/actions/workflows/scraper.yml`

## Local setup

Requirements: Python 3.11+ and Chromium.

```bash
git clone https://github.com/jeraldine-t/JJs-Event-Agent.git
cd JJs-Event-Agent
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium
cp .env.example .env
```

Fill only the local values you need in `.env`, then run:

```bash
python -m event_agent
```

Run selected public sources:

```bash
python -m event_agent --sources luma,eventbrite,meetup,gdg
```

Quality checks:

```bash
ruff check .
pytest
```

## Lu.ma private links

`LUMA_COOKIES_JSON` accepts a Playwright-compatible array from a signed-in local Lu.ma session. `LUMA_PRIVATE_URLS` accepts comma-separated private/unlisted event links and is read in addition to the public Singapore discovery page.

An unlisted URL can function as a bearer credential. Keep it in the ignored local `.env` or in a locked-down self-hosted environment, never in code, logs, or commits.

## WhatsApp persistent login

Bootstrap the local persistent profile once:

```bash
PLAYWRIGHT_HEADLESS=false python -m event_agent.bootstrap whatsapp --profile .state/whatsapp
```

## GitHub Actions workflow

`.github/workflows/scraper.yml` runs at Sunday 8:00 AM in `Asia/Singapore` and supports manual runs. It:

1. installs the package and Chromium;
2. runs Ruff and pytest;
3. collects enabled sources and overwrites `index.html`;
4. preserves the previous populated dashboard after an empty scrape;
5. commits and pushes a changed dashboard;
6. sends the scheduled email when SMTP secrets are configured; and
7. uploads only `index.html` plus `.nojekyll` and deploys the public GitHub Pages site.

The workflow requests `contents: write`, `pages: write`, and `id-token: write`. If repository policy restricts `GITHUB_TOKEN`, allow Actions read/write access under **Settings → Actions → General → Workflow permissions** so the dashboard commit and Pages deployment can succeed.

## Environment reference

Every supported variable is listed in `.env.example`. Common tuning values include:

- `LOOKAHEAD_DAYS` and `MESSAGE_LOOKBACK_DAYS`;
- LinkedIn profile/post caps and Eventbrite/Lu.ma/GDG event caps;
- `EVENTBRITE_SEARCH_URLS` and `MEETUP_SEARCH_URLS` as pipe-separated overrides;
- `SOURCE_FAILURE_MODE=warn|fail`; and
- `EMAIL_ENABLED`, recipient, and SMTP transport settings.
