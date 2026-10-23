"""Turns raw bullet points into an executive summary.

PLACEHOLDER: this is where the LLM call will go. The function signature is the
contract the rest of the app relies on; swap the body when the prompt and
provider details are decided.
"""
from datetime import date


def summarize(project_name: str, week_start: date, raw_text: str) -> str:
    lines = [ln.strip().lstrip("-*• ").strip() for ln in raw_text.splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        return ""
    header = "{} — week of {}".format(project_name, week_start.isoformat())
    body = "\n".join("• {}".format(ln[0].upper() + ln[1:] if ln else ln) for ln in lines)
    return "{}\n\n{}\n\n[placeholder summary — LLM not connected yet]".format(header, body)
