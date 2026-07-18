# JJs Event Agent

JJs Event Agent discovers upcoming **free ($0)** events in Singapore, applies strict timing and topic rules, and publishes the same curated result to two destinations on every configured run:

1. a Telegram Bot message to your personal chat; and
2. a responsive, self-contained `index.html` dashboard deployed with GitHub Pages.

The repository is public so GitHub Pages works on the current account plan. No live credentials, browser profiles, cookies, or private message bodies belong in Git. The Pages artifact contains only the curated fields shown on each card—not private source text.

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
| WhatsApp | Playwright persistent context | Saved browser profile | Reads only the two exact configured groups and never sends messages. |

Each source is isolated. A logged-out or changed site reports a source failure while other sources continue, the dashboard is still regenerated, and the Telegram output is still attempted. Set `SOURCE_FAILURE_MODE=fail` to make the run fail after both outputs are produced.

Telegram channels are not ingested. Telegram remains only as the optional Bot notification destination.

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

For a credential-free smoke run that only overwrites the local dashboard:

```bash
python -m event_agent --sources "" --skip-telegram
```

Quality checks:

```bash
ruff check .
pytest
```

## LinkedIn session

The simplest option is the value of LinkedIn's `li_at` session cookie:

```dotenv
LINKEDIN_LI_AT=your_value_here
```

Alternatively, `LINKEDIN_COOKIES_JSON` accepts a Playwright-compatible JSON array (or its base64 encoding):

```json
[{"name":"li_at","value":"...","domain":".linkedin.com","path":"/","secure":true,"httpOnly":true}]
```

Use your browser's built-in developer tools while signed in to obtain your own session cookie. Treat the value like a password. If LinkedIn redirects to login or a checkpoint, refresh the cookie manually; the agent deliberately does not bypass the checkpoint.

The included login helper can create the cookie JSON without putting a password in `.env` or chat:

```bash
python -m event_agent.bootstrap cookies linkedin
gh secret set LINKEDIN_COOKIES_JSON < .state/linkedin-cookies.json
```

## Eventbrite session

Eventbrite public search rejects plain hosted HTTP requests, so its adapter uses Playwright. Export a signed-in browser session and store it as a repository secret:

```bash
python -m event_agent.bootstrap cookies eventbrite
gh secret set EVENTBRITE_COOKIES_JSON < .state/eventbrite-cookies.json
```

The exported array preserves the correct `.eventbrite.com` and `.eventbrite.sg` cookie domains. Rotate the session if Eventbrite returns a sign-in page or access challenge.

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

## Telegram Bot output with BotFather

1. In Telegram, open the verified [@BotFather](https://t.me/BotFather) chat.
2. Send `/newbot`, choose a display name and a username ending in `bot`.
3. Copy the token into `TELEGRAM_BOT_TOKEN`. Never commit or paste it into an issue.
4. Open your new bot and press **Start** (or send `/start`). Bots cannot initiate a personal conversation until you do this.
5. With the token loaded only in your shell, get your chat ID:

   ```bash
   export TELEGRAM_BOT_TOKEN='paste-token-here'
   python -c 'import os,requests; print(requests.get(f"https://api.telegram.org/bot{os.environ[\"TELEGRAM_BOT_TOKEN\"]}/getUpdates", timeout=30).json())'
   ```

6. Find `message.chat.id` in the response and set it as `MY_TELEGRAM_CHAT_ID`.

The bot sends HTML-formatted messages in chunks below Telegram's size limit. Event names and locations are escaped before sending.

## GitHub Actions Secrets and variables

In the repository, go to **Settings → Secrets and variables → Actions**. Create these repository secrets:

| Secret | Required for |
|---|---|
| `LINKEDIN_LI_AT` or `LINKEDIN_COOKIES_JSON` | LinkedIn |
| `EVENTBRITE_COOKIES_JSON` | Authenticated Eventbrite browser session |
| `LUMA_COOKIES_JSON` | Account-visible Lu.ma events |
| `LUMA_PRIVATE_URLS` | Known private/unlisted Lu.ma links |
| `TELEGRAM_BOT_TOKEN` | Telegram output |
| `MY_TELEGRAM_CHAT_ID` | Telegram output |

Optional repository variables:

| Variable | Purpose |
|---|---|
| `SCRAPER_RUNNER` | Defaults to `ubuntu-latest`; use `self-hosted` for persistent WhatsApp. |
| `WHATSAPP_USER_DATA_DIR` | Absolute persistent profile path on the self-hosted runner. |

The workflow explicitly requests `contents: write`, `pages: write`, and `id-token: write`. If an organization policy restricts `GITHUB_TOKEN`, allow Actions read/write access under **Settings → Actions → General → Workflow permissions**, or the dashboard commit will fail.

Secrets are passed to the process as environment variables at runtime. GitHub masks exact secret values in logs, but you should still avoid debug logging and rotate any credential that is accidentally exposed.

The scheduled workflow keeps `REQUIRE_TELEGRAM_OUTPUT=false` so the dashboard can deploy before BotFather setup is complete. As soon as `TELEGRAM_BOT_TOKEN` and `MY_TELEGRAM_CHAT_ID` are present, the same run also sends the Telegram notification.

## Schedule, dashboard commit, and GitHub Pages

`.github/workflows/scraper.yml` runs at **8:00 AM every Sunday in `Asia/Singapore`**, and also supports manual runs from the Actions tab. It:

1. installs and tests the package;
2. installs Playwright Chromium;
3. runs all configured source adapters;
4. overwrites `index.html` and sends the Telegram notification;
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
- LinkedIn profile/post caps and Eventbrite/Lu.ma event caps;
- `EVENTBRITE_SEARCH_URLS` and `MEETUP_SEARCH_URLS` as pipe-separated overrides;
- `SOURCE_FAILURE_MODE=warn|fail`;
- `REQUIRE_TELEGRAM_OUTPUT=true|false`.

## Troubleshooting

- **Empty dashboard:** inspect the expandable run-health panel and Actions logs. Strict $0, Singapore, keyword, date, and time filters intentionally reject ambiguous listings.
- **LinkedIn checkpoint:** refresh your own session cookie. Do not automate checkpoint or CAPTCHA bypass.
- **Eventbrite login/challenge:** refresh `EVENTBRITE_COOKIES_JSON`; the agent does not bypass access challenges.
- **Lu.ma private event missing:** add its exact link to the secret `LUMA_PRIVATE_URLS` and refresh the cookies.
- **WhatsApp skipped in Actions:** use a self-hosted runner with the bootstrapped persistent directory.
- **Pages deployment fails:** enable GitHub Actions as the Pages source and confirm the account plan supports Pages for private repositories.
- **Site selector changed:** Playwright/BeautifulSoup adapters are isolated under `src/event_agent/sources/`; update the affected adapter and its tests without changing the filter/output pipeline.
