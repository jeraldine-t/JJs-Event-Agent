# Demo video script — target 2:35

Use the presentation-safe dashboard URL:

https://jeraldine-t.github.io/JJs-Event-Agent/?presentation=1

Record at 1080p with clear original narration. Do not add music. Stay on the dashboard and repository pages; do not open third-party registration sites. Review the final recording for third-party logos or copyrighted material before uploading it to YouTube with **Public** visibility.

## Shot list and narration

### 0:00–0:18 — The problem

**On screen:** Open the dashboard at the top of the month calendar.

**Say:**

“Professional events in Singapore are scattered across community pages, event platforms, and social feeds. But my first question is usually much simpler: which dates actually fit my schedule? I built JJ's Event Agent to turn those scattered listings into one actionable calendar.”

### 0:18–0:52 — Calendar-first experience

**On screen:** Point to the current month, use the next-month arrow, then return. Click a calendar event to jump to its detail card.

**Say:**

“The dashboard now opens as a real month grid. I can move backward or forward through any month, see event times directly on each date, and jump from any calendar entry to the full details. Every time is normalized to Singapore Time, with weekday after-work and weekend daytime events prioritized.”

### 0:52–1:22 — Useful decision signals

**On screen:** Show one detailed card. Point to its organizer-overview summary, F&B status, date, location, signup interest, and Hot Pick badge if present. Use the F&B filter.

**Say:**

“Each card keeps the information I need to decide: a summary from the organizer’s event overview, date, venue, food and beverage type, registration link, and demand signals such as people going, seats left, or waitlist status. Hot Pick highlights strong demand or limited availability. Missing information is left unstated rather than guessed.”

### 1:22–1:50 — Agent pipeline and privacy

**On screen:** Show the README architecture table and the GitHub Actions workflow section.

**Say:**

“The Python agent collects public Singapore listings from multiple sources through isolated Playwright and BeautifulSoup adapters. It visits the event detail pages, normalizes, deduplicates, filters, and ranks events, then renders this self-contained page. GitHub Actions refreshes and deploys it daily at eight AM Singapore Time, while the email remains weekly. Authenticated browser sessions stay local and never enter the public repository or dashboard.”

### 1:50–2:25 — Codex and GPT-5.6 collaboration

**On screen:** Show the README ‘Built with Codex and GPT-5.6’ section, then briefly show the tests directory and workflow.

**Say:**

“I built this collaboratively with Codex and GPT-5.6. Codex accelerated the architecture, source adapters, filtering rules, calendar UI, tests, responsive browser QA, security audits, and deployment workflow. I made the key product calls—including the Singapore timing windows, privacy boundary, F&B taxonomy, Hot Pick logic, and the decision to make summaries strictly event-overview-derived. Codex helped keep every layer consistent as those requirements evolved.”

### 2:25–2:35 — Close

**On screen:** Return to the calendar overview.

**Say:**

“JJ's Event Agent turns event discovery into a schedule decision—so the right opportunity is easier to find, evaluate, and actually attend.”

## Before uploading

- Keep the final runtime below 3:00; target 2:35–2:45.
- Confirm narration clearly mentions both Codex and GPT-5.6.
- Use no copyrighted music or third-party footage.
- Check every frame for unlicensed third-party logos or trademarks.
- Upload to YouTube as **Public**, not Private or Unlisted.
- Add the public YouTube URL to `docs/DEVPOST_SUBMISSION.md` and the Devpost form.
