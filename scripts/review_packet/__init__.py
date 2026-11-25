"""Implementation package for scripts/export_review_packet.py, split by concern.

core: shared state (NOTES, CHECKS, file-text cache) and the generic read/write/hash helpers.
ast_helpers: static-value extraction from Python source (strings, numbers, system prompts).
phrase_expand: regex-to-phrase enumeration for the crisis detector's patterns.
test_cases: AST extraction of detector test sentences from tests/*.py.
builders_crisis / builders_assessment / builders_prompt / builders_flow / builders_manifest:
    one function per output file, in the same shape as the original monolithic script.

All shared state lives in `core` as module globals (NOTES, CHECKS, _SRC); other modules only
touch it through core's functions (note(), check(), src(), ...) or by importing the same list
objects, never by redefining them, so mutations are visible everywhere.
"""
