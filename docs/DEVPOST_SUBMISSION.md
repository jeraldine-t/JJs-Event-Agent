# OpenAI Build Week submission draft

Official challenge page: https://openai.devpost.com/

Deadline: **Tuesday, 21 July 2026 at 5:00 PM PDT**, which is **Wednesday, 22 July 2026 at 8:00 AM SGT**.

## Submission fields

### Project name

JJs Event Agent

### Tagline

A date-first agent that turns scattered Singapore event listings into one schedule-aware social calendar.

### Category

**Apps for your life**

This is the closest fit because the product helps an individual plan everyday learning, networking, and social time. It is a consumer scheduling and discovery experience rather than a developer tool or an internal team workflow.

### Repository URL

https://github.com/jeraldine-t/JJs-Event-Agent

The repository is public and licensed under MIT.

### Working demo URL

https://jeraldine-t.github.io/JJs-Event-Agent/

No account, test user, API key, or rebuild is required. For a screen-recording view that hides third-party source labels, use:

https://jeraldine-t.github.io/JJs-Event-Agent/?presentation=1

### Demonstration video URL

`TODO: Paste the public YouTube URL here.`

### Codex Session ID

`TODO: Run /feedback in the Codex task where the majority of the core functionality was built, then paste the returned Session ID here and into Devpost.`

Do not substitute a repository commit, task title, or guessed UUID. Devpost specifically requests the ID returned by `/feedback`.

## Project description

Finding worthwhile professional events in Singapore means repeatedly checking event platforms, community pages, and social feeds—then manually comparing dates against a personal calendar. JJs Event Agent turns that fragmented workflow into a single date-first dashboard.

The Python agent collects upcoming listings from public discovery pages including Lu.ma Singapore, Eventbrite, Meetup, and Google Developer Groups, with optional locally authenticated LinkedIn, Eventbrite, Lu.ma, and WhatsApp collection. It normalizes everything to Singapore Time, deduplicates listings, and filters for AI, technology, robotics, marketing, business, and networking events that fit after-work weekday or daytime weekend windows. Explicitly paid events are excluded, while listings with unstated admission remain eligible.

The dashboard opens as a real month grid so users can inspect dates before reading event details. Each event exposes organizer-provided description text only, detected food-and-beverage types, signup or seat availability when published, source, location, and registration link. A Hot Pick signal highlights strong demand or low availability. Filters make it easy to isolate Lu.ma, a particular F&B type, or any matching phrase.

GitHub Actions runs the pipeline every Sunday at 8:00 AM SGT, refreshes the dashboard, preserves the last populated result if a scrape is empty, deploys GitHub Pages, and can email the same curated list once SMTP secrets are configured. Login sessions and private message bodies stay local and never enter the public repository or Pages artifact.

## How Codex and GPT-5.6 were used

Codex with GPT-5.6 acted as the engineering collaborator across the entire product lifecycle. It helped translate evolving product requirements into a common event model, isolated source adapters, conservative filtering rules, a responsive month-grid UI, automated tests, a weekly Actions workflow, and a deployable public demo. Codex also performed browser-based responsive QA and audited the complete Git history and deployed page for credential leakage.

Jeraldine made the key product decisions: Singapore-only scope, schedule windows, source priorities, admission behavior, Telegram removal, F&B taxonomy, Hot Pick criteria, the public-dashboard/private-session boundary, and the final request for a real calendar with strictly description-derived summaries. Codex accelerated coordinated implementation and verification while these requirements changed.

## Suggested Devpost answers

### Inspiration

The project came from a practical problem: high-value Singapore events are scattered across many communities and platforms, while the decision to attend usually starts with a simple question—“Am I free on that date?” Existing event lists optimize for browsing; JJs Event Agent optimizes for fitting opportunities into real life.

### What it does

It collects, normalizes, filters, ranks, and publishes relevant Singapore events in a calendar-first dashboard. Users can navigate months, jump from a date to event details, filter by source or F&B type, and see demand signals such as people going, seats left, or waitlist status.

### How it was built

The backend is Python 3.11+ with Playwright, Requests, BeautifulSoup, Jinja2, and date parsing utilities. Each source emits a shared raw-event model; the curation layer handles Singapore location, timing, explicit-paid admission, keyword, perk, deduplication, and popularity rules. Jinja2 produces one self-contained HTML dashboard. Pytest and Ruff verify behavior, while GitHub Actions schedules collection and deploys GitHub Pages.

### Challenges

The biggest challenges were inconsistent event markup, authenticated sources that must not leak sessions, incomplete price/F&B/capacity fields, changing website UIs, and keeping summaries faithful to source descriptions. The solution isolates failures per source, keeps authentication local, treats missing data honestly, and backs each normalization rule with focused tests.

### Accomplishments

- Working multi-source event pipeline and public demo.
- A real responsive month calendar plus detailed agenda.
- Description-only summaries with private-source protection.
- F&B taxonomy, source filters, and Hot Pick capacity signals.
- Weekly SGT-aware automation and GitHub Pages deployment.
- Full Git-history and deployed-artifact credential audit.

### What was learned

Useful event automation depends less on collecting the largest possible feed and more on honest normalization: time zones, missing fields, privacy boundaries, and transparent confidence signals. A date-first interface also changes discovery from passive scrolling into an actionable scheduling decision.

### What's next

- Add an explicit “Add to calendar” `.ics` action.
- Move authenticated collection to a locked-down self-hosted runner.
- Add user-controlled notification preferences and source health alerts.
- Improve public description extraction and cross-source deduplication.

## Final compliance checklist

- [x] Working project built with Codex and a public demo.
- [x] Category selected: Apps for your life.
- [x] Project description and suggested Devpost answers prepared.
- [x] Public code repository with MIT license.
- [x] README setup, supported platforms, judge quickstart, and Codex collaboration narrative.
- [x] Demo instance that judges can test without rebuilding.
- [x] Demo script designed to stay below three minutes.
- [ ] Record the demo with clear spoken audio covering the product, Codex, and GPT-5.6.
- [ ] Use original narration only; do not add copyrighted music.
- [ ] Use the `?presentation=1` demo URL, avoid opening third-party registration pages, and ensure no unlicensed third-party logos or marks appear in the final edit.
- [ ] Upload the video to YouTube with **Public** visibility and paste its URL into Devpost.
- [ ] Run `/feedback` in the core Codex task and paste the returned Session ID into Devpost.
- [ ] Recheck every submitted link in a logged-out browser before the deadline.
