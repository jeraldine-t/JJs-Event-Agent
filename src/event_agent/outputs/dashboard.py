from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, PackageLoader

from event_agent.models import Event, FilterReport, SourceStatus


def render_dashboard(
    events: list[Event],
    statuses: list[SourceStatus],
    report: FilterReport,
    *,
    generated_at: datetime,
    output_path: Path,
) -> None:
    environment = Environment(
        loader=PackageLoader("event_agent", "templates"),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template("index.html.j2")
    event_rows = []
    for event in events:
        row = event.to_dict()
        row["date_label"] = event.start_at.strftime("%a, %d %b %Y")
        row["time_label"] = event.start_at.strftime("%-I:%M %p SGT")
        row["keywords"] = [
            keyword for keyword in event.keywords if keyword not in event.perks
        ]
        event_rows.append(row)
    rendered = template.render(
        events=event_rows,
        statuses=[status.to_dict() for status in statuses],
        report=report,
        generated_at=generated_at.strftime("%d %b %Y, %-I:%M %p SGT"),
        source_names=sorted({event.source for event in events}),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(output_path)
