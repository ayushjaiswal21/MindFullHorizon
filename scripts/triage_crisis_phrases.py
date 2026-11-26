"""Triage helper for the owner's manual clinician review of docs/review/generated/crisis_phrases.csv
(1,416 rows, currently un-reviewed). Read-only: never writes to crisis_phrases.csv and never labels
anything itself - it only reorders/groups a copy for faster human review.

Groups rows by their `list` column (stratum), flags exact and near-duplicate phrases so the owner
doesn't review the same wording twice, and within each group puts the most ambiguous rows (the
`cautious_pattern` list, or any row the detector itself scored as a borderline class like
friend/soft/mild) first, with near-identical phrasing kept adjacent.

Usage:
    python scripts/triage_crisis_phrases.py [input_csv] [output_html]

Defaults: docs/review/generated/crisis_phrases.csv -> docs/review/crisis_phrases_triage.html
"""
import csv
import difflib
import html
import sys
from collections import defaultdict

AMBIGUOUS_LISTS = {"cautious_pattern"}
AMBIGUOUS_CLASSES = {"friend", "soft", "mild"}


def normalize(phrase):
    return " ".join(phrase.lower().split())


def ambiguity_rank(row):
    if row["list"] in AMBIGUOUS_LISTS:
        return 0
    if row["detector_class_alone"] in AMBIGUOUS_CLASSES:
        return 1
    return 2


def annotate_duplicates(rows):
    """Within an already phrase-sorted group, flag exact dups and near-dups vs. the previous row."""
    seen_exact = {}
    for i, row in enumerate(rows):
        norm = normalize(row["phrase_normalised_form"])
        flag = ""
        if norm in seen_exact:
            flag = f"EXACT DUPLICATE of {seen_exact[norm]}"
        else:
            seen_exact[norm] = row["id"]
            if i > 0:
                prev_norm = normalize(rows[i - 1]["phrase_normalised_form"])
                ratio = difflib.SequenceMatcher(None, norm, prev_norm).ratio()
                if ratio > 0.85:
                    flag = f"near-duplicate of {rows[i - 1]['id']} ({ratio:.2f})"
        row["_flag"] = flag
    return rows


def build_groups(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["list"]].append(row)
    for list_name, group_rows in groups.items():
        group_rows.sort(key=lambda r: (ambiguity_rank(r), normalize(r["phrase_normalised_form"])))
        annotate_duplicates(group_rows)
    return groups


def render_html(groups, total):
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>Crisis phrases triage</title>",
        "<style>",
        "body{font-family:system-ui,sans-serif;margin:1.5rem;color:#1a1a1a}",
        "summary{font-size:1.1rem;font-weight:600;cursor:pointer;padding:.5rem 0}",
        "table{border-collapse:collapse;width:100%;margin-bottom:1rem}",
        "td,th{border:1px solid #ccc;padding:.3rem .5rem;text-align:left;font-size:.9rem;vertical-align:top}",
        "tr.ambiguous{background:#fff6e0}",
        "tr.dup{background:#eee;color:#777}",
        ".flag{font-weight:600;color:#a33}",
        "</style></head><body>",
        f"<h1>Crisis phrases triage</h1><p>{total} rows total, read-only prep for manual review. "
        "Does not label or change crisis_phrases.csv. Groups are the `list` column; within each group, "
        "ambiguous entries (cautious_pattern, or detector-scored friend/soft/mild) are listed first, and "
        "near-identical phrasing is kept adjacent so look-alikes can be skimmed together.</p>",
    ]
    for list_name in sorted(groups, key=lambda k: -len(groups[k])):
        group_rows = groups[list_name]
        dup_count = sum(1 for r in group_rows if r["_flag"])
        parts.append(
            f"<details><summary>{html.escape(list_name)} "
            f"({len(group_rows)} rows, {dup_count} flagged as dup/near-dup)</summary>"
        )
        parts.append(
            "<table><tr><th>id</th><th>phrase</th><th>language</th><th>category</th>"
            "<th>detector class</th><th>severity</th><th>pattern_id</th><th>flag</th></tr>"
        )
        for r in group_rows:
            row_class = "dup" if r["_flag"] else ("ambiguous" if ambiguity_rank(r) < 2 else "")
            flag_html = f"<span class='flag'>{html.escape(r['_flag'])}</span>" if r["_flag"] else ""
            parts.append(
                f"<tr class='{row_class}'><td>{html.escape(r['id'])}</td>"
                f"<td>{html.escape(r['phrase_normalised_form'])}</td>"
                f"<td>{html.escape(r['language_script'])}</td>"
                f"<td>{html.escape(r['category_auto'])}</td>"
                f"<td>{html.escape(r['detector_class_alone'])}</td>"
                f"<td>{html.escape(r['detector_severity_alone'])}</td>"
                f"<td>{html.escape(r['pattern_id'])}</td>"
                f"<td>{flag_html}</td></tr>"
            )
        parts.append("</table></details>")
    parts.append("</body></html>")
    return "\n".join(parts)


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else "docs/review/generated/crisis_phrases.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "docs/review/crisis_phrases_triage.html"

    with open(in_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    groups = build_groups(rows)

    # self-check: triage must not drop, add, or duplicate rows across groups
    assert sum(len(g) for g in groups.values()) == len(rows), "row count changed during grouping"
    assert {r["id"] for g in groups.values() for r in g} == {r["id"] for r in rows}, "row ids changed"

    out_html = render_html(groups, len(rows))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"Wrote {out_path}: {len(groups)} groups, {len(rows)} rows total.")
    for list_name, group_rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        dup_count = sum(1 for r in group_rows if r["_flag"])
        print(f"  {list_name:24s} {len(group_rows):4d} rows, {dup_count:4d} flagged dup/near-dup")


if __name__ == "__main__":
    main()
