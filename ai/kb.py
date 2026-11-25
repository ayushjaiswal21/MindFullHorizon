"""Knowledge-base snippets for the chat router (ai/router.py). Pure local file lookup, no model call, no network.

A new entry must carry "review_status": "draft_unreviewed" and stay that way until a clinician has reviewed it.
All 16 entries shipped so far were read and approved by the owner (a licensed psychiatrist/psychologist) on
2026-11-25 and now carry "clinician_reviewed" (see docs/review/signoff/2026-11-25-clinician-approvals.md and
docs/research/ai/decisions/chat-router-draft.md); CHAT_ROUTER_ENABLED defaults to 1 in production for that reason.

Content rule: every snippet is either (a) adapted from text that already exists and has some basis in this
repo (ai_prompts/psychologist_system.txt, docs/SAFETY_RESEARCH.md, the fixed FRIEND_REPLY/SOFT_REPLY/
DEFAULT_REPLY/off_reply() text, or the FAQ answers in routes/pages.py) or (b) plain psychoeducation that only
points at one of the app's own existing features (breathing guide, journal, etc.), never an invented coping
technique. Each JSON file's "source" field says which.
"""
import json
import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kb_data')


def _load():
    entries = {}
    if os.path.isdir(_DIR):
        for fname in sorted(os.listdir(_DIR)):
            if not fname.endswith('.json'):
                continue
            with open(os.path.join(_DIR, fname), 'r', encoding='utf-8') as f:
                entry = json.load(f)
            if 'intent' in entry:
                entries[entry['intent']] = entry
    return entries


_ENTRIES = _load()


def get_snippet(intent_id):
    """The draft answer text for an intent, or None."""
    entry = _ENTRIES.get(intent_id)
    return entry.get('snippet') if entry else None


def all_entries():
    """Every KB entry (for clinician/admin review only - never shown on a student-facing page as-is)."""
    return [dict(e) for e in _ENTRIES.values()]


def reload():
    """Re-read ai/kb_data from disk (tests only; the process otherwise loads once at import)."""
    global _ENTRIES
    _ENTRIES = _load()


def init_kb_cli(app):
    """`flask list-kb-drafts`: the one place a human can see every draft snippet and its review status."""
    import click

    @app.cli.command('list-kb-drafts')
    def list_kb_drafts():
        """List every chat-router knowledge-base entry and its review status (clinician review checklist)."""
        entries = all_entries()
        if not entries:
            click.echo('No knowledge-base entries found in ai/kb_data/.')
            return
        for e in sorted(entries, key=lambda x: x.get('intent', '')):
            click.echo(f"[{e.get('review_status', 'UNKNOWN')}] {e.get('intent')}: {e.get('source', '(no source noted)')}")
        unreviewed = sum(1 for e in entries if e.get('review_status') == 'draft_unreviewed')
        click.echo(f"\n{unreviewed} of {len(entries)} entries are draft_unreviewed.")
