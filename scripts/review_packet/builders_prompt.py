"""Builder for ai_prompt_snapshot.md."""
import re

from .ast_helpers import module_strings, system_prompts
from .core import excerpt, md_header, src, write_text


def build_prompt_snapshot(out, stamp, commit, dirty, guard):
    parts = [md_header('AI prompt and refusal-rule snapshot', stamp, commit, dirty), '']
    max_chars = guard.max_reply_chars() if guard is not None and hasattr(guard, 'max_reply_chars') else None
    p = src('ai_prompts/psychologist_system.txt')
    if p:
        if max_chars is not None:
            p = p.replace('{max_reply_chars}', str(max_chars))
        else:
            p = p.replace('{max_reply_chars}', '{max_reply_chars: set by code at run time}')
        parts += ['## 1. Main system prompt for the chat companion (Anya)', '',
                  'File: `ai_prompts/psychologist_system.txt`. Sent to the model as the system instruction together with the '
                  'notes in section 2 and, when present, an internal marker line (canary) that is redacted here.', '',
                  '```text', p.rstrip(), '```', '']
    else:
        parts += ['## 1. Main system prompt', '', 'NOT EXPORTED: `ai_prompts/psychologist_system.txt` was not found.', '']
    notes = []
    if guard is not None:
        for nm in ('DATA_NOTE', 'HARDENED_NOTE'):
            if hasattr(guard, nm):
                notes.append((f'utils/llm_guard.py::{nm}', getattr(guard, nm)))
        if hasattr(guard, 'canary_line'):
            notes.append(('utils/llm_guard.py::canary_line()', re.sub(r'CNRY-[0-9a-f]+', '[CANARY REDACTED]',
                                                                        guard.canary_line().replace(getattr(guard, 'CANARY', '\0'),
                                                                                                     '[CANARY REDACTED]'))))
    else:
        env = module_strings('ai/service.py')
        if 'DATA_NOTE' in env:
            notes.append(('ai/service.py::DATA_NOTE (utils/llm_guard.py not present)', env['DATA_NOTE']))
    parts += ['## 2. Text appended to system prompts (injection hygiene)', '']
    for where, text in notes:
        parts += [f'`{where}`', '', '```text', text.strip(), '```', '']
    if not notes:
        parts += ['NOT EXPORTED: no DATA_NOTE found in code.', '']
    parts += ['## 3. Other system prompts found in `ai/service.py`', '',
              'Static strings only; `{expr}` marks a value computed at run time. These are the non-chat features '
              '(assessment insights, journal insights, progress, goals, medication adherence, voice, clinical note drafts).', '']
    sp = system_prompts('ai/service.py')
    for fn, line, text in sp:
        parts += [f'`ai/service.py:{line}` in `{fn}()`', '', '```text', text.strip(), '```', '']
    if not sp:
        parts += ['NOT EXPORTED: none found.', '']
    parts += ['## 4. Fixed replies the student can see (not model-written)', '']
    env = module_strings('ai/service.py')
    for nm in sorted(k for k in env if k.endswith('_REPLY')):
        parts += [f'`ai/service.py::{nm}`', '', '> ' + env[nm], '']
    parts += ['## 5. Output guard and refusal rules', '']
    if guard is None:
        parts += ['NOT EXPORTED: `utils/llm_guard.py` does not exist in this working tree (the output guard may not be built yet). '
                  'Only the prompt-level rules above apply. Re-run the exporter when it lands.', '']
    else:
        if hasattr(guard, 'SAFE_FALLBACK'):
            parts += ['Safe fallback shown when model output is blocked (`utils/llm_guard.py::SAFE_FALLBACK`):', '',
                      '> ' + guard.SAFE_FALLBACK, '']
        blocks = getattr(guard, '_BLOCK', {})
        parts += ['Content checks that replace a model reply with the safe fallback (regex source, case-insensitive):', '',
                  '| Check | Pattern |', '|---|---|']
        for k in sorted(blocks):
            parts.append(f"| {k} | `{blocks[k].pattern.replace('|', chr(92) + '|')}` |")
        parts += ['', f"Leak markers (reply blocked if it contains one): {', '.join(getattr(guard, '_LEAK_MARKERS', ()))}", '']
        parts += ['Other output clean-up (`clean_text`): strips HTML, code fences, markdown links and images, URLs, e-mail '
                  'addresses, phone numbers that are not our helplines, emoji, and em/en dashes. Reply length is capped at '
                  f'{max_chars} characters (env `AI_MAX_REPLY_CHARS`).', '']
    gi = src('ai/gemini_impl.py')
    model = re.search(r'GEMINI_MODEL_NAME\s*=\s*os\.environ\.get\("GEMINI_MODEL_NAME",\s*"([^"]+)"', gi)
    parts += ['## 6. Model settings read from code', '',
              f"- Default model id: `{model.group(1) if model else 'not found'}` (env `GEMINI_MODEL_NAME` overrides). "
              'The model version is not pinned by default, so behaviour can change when the provider changes the alias.',
              '- Rules are passed as the system instruction, user text as the user turn (never concatenated).',
              '- Chat call settings: ' + (excerpt('ai/service.py', r'ask_gemini_system_user\(system_prompt(?: \+|, payload)', limit=1) or ['not found'])[0]]
    write_text(out, 'ai_prompt_snapshot.md', '\n'.join(parts))
