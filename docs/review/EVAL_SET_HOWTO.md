# How to fill the independent crisis evaluation set (solo, owner as clinician)

This is the first real accuracy measurement the crisis floor will ever have. `tests/test_safety.py`'s 169 cases
were written next to the regexes they test (100% match by construction); this set is independent of that code.

**Owner note (2026-11-25):** you are doing this solo, as a licensed psychiatrist/psychologist, without the 2-4
independent non-clinician writers `SYNTHESIS.md` section 2 originally called for. That is a known, accepted
trade-off (faster, but the "never seen the code" independence is weaker since you are closer to the project than
an outside writer would be) — still a real improvement over the circular 169-case set, not a full substitute for
the original multi-author design. Do this at your own pace; nothing else is blocked waiting for it.

## 1. Open the template

`docs/review/eval_set_template.csv` has 600 blank rows, already split into the 8 strata the research called for
(counts fixed, do not change them): 50 English must-trigger, 70 correctly-spelled Hinglish must-trigger, 30
misspelled Hinglish must-trigger, 50 Devanagari must-trigger, 100 negated/passive/soft, 60 third-party, 160 hard
negatives, 80 obfuscated/injection-style. Open it in Excel, Google Sheets, or any text editor.

## 2. Write fictional items only

Every item must be invented, never a real patient's words, never copied from the internet or a real forum post
(copied real text brings consent and re-identification problems even when anonymised). Write what a realistic
item in that stratum would plausibly sound like, drawing on your own clinical knowledge of how distress,
ideation, deflection, and third-party worry are actually expressed, including in Hinglish and mixed script. The
`instructions_delete_before_scoring` column on each row repeats the stratum's brief; delete that column before
scoring, it is a prompt for you, not data.

## 3. Label each item

Fill `your_label_none_concern_checkin_crisis` with one of exactly: `none`, `concern`, `checkin`, `crisis` — your
own clinical judgement of what the item actually expresses, independent of what you expect the detector to do.
For `third_party` rows, label the underlying concern level of the person being described (the scorer treats that
stratum specially, see step 4).

## 4. Score it

Save your filled sheet as a CSV (keep the exact column names) and run:

```
python scripts/score_eval_set.py path/to/your_filled.csv
```

It prints recall per stratum and per language with a 95% confidence interval, the false-alert rate on the
hard-negative strata, and whether each pass bar from `SYNTHESIS.md` section 2 is met: overall recall >= 0.90
(CI lower bound >= 0.85), every language slice >= 0.80, false-alert rate <= 2%. You do not need all 600 rows
filled before a first run — the script scores whatever rows have both a `text` and a label, so you can check
progress incrementally (though confidence intervals are wide on small counts).

## 5. What a result means

- **Pass bar met:** the floor's real-world recall finally has a number. Record it in `docs/TRACKER.md` and
  consider the a1 gate (`SYNTHESIS.md` section 2) satisfied for the fuzzy layer and the router, which were both
  already clinician-approved on content grounds separately (`docs/review/signoff/2026-11-25-clinician-approvals.md`).
- **Pass bar not met, especially a specific stratum or language:** that is useful, actionable information, not a
  failure of this exercise — it tells us exactly where the deterministic rules in `ai/severity.py` and the
  vocabulary in `ai/fuzzy_crisis.py` need more entries. Bring the missed items back to a follow-up session and
  we will extend the rules to cover them, then re-score.

## 6. Keep this file out of git with real content

Fill the CSV in a copy outside the repository, or keep it in `docs/review/` but never commit real distressing
content casually reviewed by others — the fictional items themselves are fine to keep, but treat the file as
sensitive working material (same handling as anything else in `docs/review/signoff/`).
