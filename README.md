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

Each source is isolated. A logged-out or changed site reports a source failure while other sources continue. The workflow preserves the last populated dashboard if a scheduled scrape returns no qualifying events.

The cloud workflow runs **once a week, every Sunday at 8:00 AM SGT**. It does not scrape daily. Authenticated LinkedIn and Eventbrite collection happens only when the agent is run on the local or trusted self-hosted machine that holds those sessions; those browser sessions are deliberately absent from GitHub.

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

## Weekly email summary

The scheduled Sunday run attempts to email the curated list to `jeraldine.openai@outlook.com`. Manual workflow runs do not send email. Email is safely skipped until all SMTP secrets are configured.

Use a mail provider that supports app-specific SMTP credentials. Do **not** store an ordinary mailbox password. Microsoft permanently removed Basic-auth SMTP client submission in Exchange Online in March 2026, so an Outlook/Microsoft 365 account password is not a supported sender credential. The recipient can still be the Outlook address; the sender may use any compatible SMTP provider.

In **Settings → Secrets and variables → Actions → New repository secret**, add:

| Secret | Example/purpose |
|---|---|
| `SMTP_HOST` | Provider SMTP hostname |
| `SMTP_PORT` | Usually `587` for STARTTLS or `465` for implicit TLS |
| `SMTP_SECURITY` | `starttls` or `ssl` |
| `SMTP_USERNAME` | Provider account or SMTP username |
| `SMTP_PASSWORD` | App-specific password/token, never the normal account password |
| `SMTP_FROM` | Verified sender email address |

GitHub encrypts Actions secrets and masks them from normal logs. The workflow never writes these values to `index.html`, Pages artifacts, commits, or source-status messages. Keep LinkedIn, Eventbrite, Lu.ma, and WhatsApp login sessions local unless you later choose a locked-down self-hosted runner.

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

## LinkedIn and Eventbrite sessions

Create ignored local Playwright cookie files through the interactive helper:

```bash
python -m event_agent.bootstrap cookies linkedin
python -m event_agent.bootstrap cookies eventbrite
```

For LinkedIn, a trusted local `.env` may instead contain `LINKEDIN_LI_AT`, or `LINKEDIN_COOKIES_JSON` may contain a Playwright-compatible cookie array. Eventbrite uses `EVENTBRITE_COOKIES_JSON` when supplied.

Treat all cookie values like passwords. Never commit them, paste them into chat, include them in an artifact, or copy them into a workflow file. If a site redirects to a checkpoint, sign in again manually; the agent does not automate a checkpoint or CAPTCHA.

## Lu.ma private links

`LUMA_COOKIES_JSON` accepts a Playwright-compatible array from a signed-in local Lu.ma session. `LUMA_PRIVATE_URLS` accepts comma-separated private/unlisted event links and is read in addition to the public Singapore discovery page.

An unlisted URL can function as a bearer credential. Keep it in the ignored local `.env` or in a locked-down self-hosted environment, never in code, logs, or commits.

## WhatsApp persistent login

Bootstrap the local persistent profile once:

```bash
PLAYWRIGHT_HEADLESS=false python -m event_agent.bootstrap whatsapp --profile .state/whatsapp
```

WhatsApp is excluded from the default schedule because GitHub-hosted runners are erased after each job. A self-hosted runner can opt in with an absolute `WHATSAPP_USER_DATA_DIR`. Never commit or upload the browser profile.

The exact configured chats are:

- `Codex Community - Main Chat`
- `non-RWA events, programs, initiatives`

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

## Troubleshooting

- **Empty dashboard:** inspect the run-health panel and Actions logs. Topic, Singapore, date, timing, and explicit-paid-price filters may reject listings.
- **LinkedIn skipped in Actions:** expected while credentials remain local; run locally or use a trusted self-hosted runner.
- **Eventbrite challenge:** refresh the local session; access challenges are not bypassed.
- **Lu.ma private event missing:** add its exact link locally and refresh the local cookies.
- **Email skipped:** add all six SMTP secrets and wait for the next scheduled run; manual runs intentionally do not send.
- **Dashboard returns 404:** confirm the latest Pages deployment succeeded and GitHub Actions is selected as the Pages source.
- **Site selector changed:** update the isolated adapter under `src/event_agent/sources/` and its tests.
