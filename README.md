# JJ's Event Agent

JJ's Event Agent discovers relevant upcoming Singapore events, applies topic and timing rules, and creates a responsive live calendar dashboard plus a weekly email summary.

The dashboard is public at `https://jeraldine-t.github.io/JJs-Event-Agent/`. The repository contains code, tests, and the sanitized `index.html` only. Login cookies, `.env`, browser profiles, private links, and raw private-message bodies must never be committed or uploaded.

## Judge quickstart

- **Live demo:** https://jeraldine-t.github.io/JJs-Event-Agent/
- **Presentation-safe demo:** https://jeraldine-t.github.io/JJs-Event-Agent/?presentation=1
- **Repository:** https://github.com/jeraldine-t/JJs-Event-Agent
- **License:** MIT
- **Recommended OpenAI Build Week category:** **Apps for your life**

The live demo requires no account, API key, rebuild, or test data. Use the month arrows, click a compact calendar event to jump to its detail card, and try the source and F&B filters. The presentation-safe URL hides source-brand labels for screen recording; the normal dashboard retains the complete source filter, including **Lu.ma · Singapore**.

## What qualifies

An event is included only when all of these checks pass:

- **Topic:** AI, data, technology, robotics, product, design, marketing, business, or networking. Related developer tooling, cloud, open-source, cybersecurity, fintech, analytics, and startup topics are included even when a listing does not use the exact category name.
- **Location:** Singapore or a recognized Singapore area.
- **Admission:** listings with no displayed price or explicit free admission are accepted; an explicit paid ticket price is rejected. Admission labels are intentionally omitted from the dashboard.
- **Date:** upcoming and within `LOOKAHEAD_DAYS` (90 by default).
- **Time:** weekdays after 6:00 PM SGT, or weekends from 6:00 AM through 5:59 PM SGT. A 6:00 PM weekday start is accepted for preferred central work hubs such as Mapletree Business City, Downtown, and Orchard.

Events around Mapletree Business City, Downtown, Orchard, and nearby central work hubs receive a ranking boost. Events mentioning free food, free drinks, pizza, beer, wine, refreshments, buffet, light bites, dinner, or networking receive a higher ranking. The dashboard F&B filter lists every detected type and includes “Not stated.”

## Sources and update coverage

| Source | Adapter | Scheduled GitHub-hosted run | Authenticated/local run |
|---|---|---|---|
| Eventbrite | Playwright | Public Singapore search | Same search with optional account cookies |
| Lu.ma | Requests + schema.org | Public `https://luma.com/singapore` discovery plus every event overview page | Cookie-authenticated supplied private/unlisted links |
| Meetup | Requests + BeautifulSoup | Public Singapore search | Same public search |
| Google Developer Groups | Playwright + schema.org | Public events and Singapore chapter | Same public search |

> Automated access can be limited by each platform's terms and UI changes. Use only accounts and content you are authorized to access. The project does not bypass CAPTCHAs, checkpoints, access controls, or rate limits.

## Dashboard

The dashboard opens with a full Monday-to-Sunday month grid so dates can be compared against a personal schedule before reading details. Month arrows navigate backward or forward without an artificial end month, and compact calendar events jump to the chronological agenda. Cards include:

Previously published events remain available in their original calendar months as a permanent archive. Scheduled scrapes refresh matching event details and add newly discovered events without deleting past entries.

- event name, SGT date/time, location, source, and registration link;
- a summary of at most 99 words, derived only from the organizer's event overview on the detail page;
- the specific F&B types explicitly mentioned, or “Not stated”; and
- number going, seats remaining, waitlist, or registration status when the source publishes it.

A **Hot pick** badge appears for at least 50 people going, ten or fewer seats left, or a waitlist/full event. No attendee identities are collected.

No title-, topic-, location-, admission-, listing-card-, or private-message text is used to invent a summary. An event without a verified detail-page overview is excluded. Private-source message bodies are never copied into the dashboard or email.

## Public dashboard access

The live dashboard is:

`https://jeraldine-t.github.io/JJs-Event-Agent/`

The Pages deployment contains only the generated `index.html` and `.nojekyll`. It does not contain `.env`, browser state, Playwright cookies, source code, raw messages, or SMTP credentials.

For deployment history, use:

`https://github.com/jeraldine-t/JJs-Event-Agent/actions/workflows/scraper.yml`

## Local setup

Requirements: Python 3.11+ and Chromium. The generated dashboard supports current desktop and mobile browsers. The scraper is tested on GitHub-hosted Ubuntu and can run on macOS, Linux, or Windows anywhere Python and Playwright Chromium are supported.

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

## Built with Codex and GPT-5.6

This project was developed collaboratively in Codex during OpenAI Build Week. GPT-5.6 in Codex accelerated the work from a rough automation brief into a tested, deployed product:

- **Architecture:** Codex helped split each source into an isolated adapter, build a common event model, normalize SGT dates, and design fail-soft collection so one blocked site does not stop the dashboard.
- **Implementation:** Codex produced and iterated on the Playwright/BeautifulSoup ingestion, deduplication, timing and admission filters, F&B detection, signup-capacity signals, responsive calendar, email renderer, and GitHub Actions deployment.
- **Verification:** Codex added focused pytest coverage, Ruff checks, credential-history audits, live browser QA at desktop and mobile widths, and deployment verification against GitHub Pages.
- **Security:** Codex helped keep `.env`, browser profiles, LinkedIn/Eventbrite sessions, private links, and raw private messages outside Git and outside the public Pages artifact.

The human product decisions remained explicit throughout. Jeraldine chose the Singapore-only scope, topic and timing windows, acceptance of price-unstated listings, removal of Telegram, F&B and Hot Pick signals, public-dashboard/private-session boundary, open-ended month-grid interaction, and detail-page-overview summary policy. Codex proposed implementation options and tradeoffs; Jeraldine decided what the product should do and authenticated source accounts manually when required.

The collaboration was especially valuable when requirements changed mid-build: Codex updated the shared data model, source adapters, tests, dashboard, workflow, security posture, and documentation together instead of treating each request as an isolated patch.

## GitHub Actions workflow

`.github/workflows/scraper.yml` refreshes the dashboard daily at 8:00 AM in `Asia/Singapore` and supports manual runs. The email is sent only by the Sunday 8:00 AM run. It:

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
- LinkedIn profile/post caps and Eventbrite/Lu.ma/Meetup/GDG event caps;
- `EVENTBRITE_SEARCH_URLS` and `MEETUP_SEARCH_URLS` as pipe-separated overrides;
- `SOURCE_FAILURE_MODE=warn|fail`; and
- `EMAIL_ENABLED`, recipient, and SMTP transport settings.
