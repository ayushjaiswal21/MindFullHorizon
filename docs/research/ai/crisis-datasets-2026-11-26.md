# Crisis/suicide-risk dataset survey (2026-11-26)

Research only. Does not move or clear the a4 gate in `docs/research/ai/SYNTHESIS.md` section 2 — that gate
still needs the clinician-labelled 600-item eval set (item a1), 4+ weeks of shadow-mode testing at ≥15-point
recall improvement over the floor at ≤1% false-flag rate, and clinician sign-off. Nothing below changes that.

Honesty note: every dataset below is checked for whether it is *actually* usable right now, not just whether
it exists in the literature. "Exists" and "we can use it this week" are different claims; this doc keeps them
separate.

## 1. "ICON 2021 Hindi-English code-mixed suicidal ideation corpus"

Not a shared task — a main-conference paper: Agarwal & Dhingra, *Deep Learning Based Approach For Detecting
Suicidal Ideation in Hindi-English Code-Mixed Text: Baseline and Corpus*, ICON 2021
(https://aclanthology.org/2021.icon-main.14). 6,533 Hinglish samples (3,098 suicidal / 3,435 non-suicidal),
built from scraped Reddit English posts then **machine-converted** to code-mixed Hindi-English — not
naturally written Hinglish. The paper has no data-availability statement, no GitHub/Zenodo link, no stated
license, and no public repo surfaced in search. A 2025 IEEE CICN paper reuses the same resource with the same
caveats.

- **Access right now:** unconfirmed/likely not — would need emailing the authors, no guarantee of a reply or
  a license permitting this use.
- **Language:** Hindi-English code-mixed, but machine-converted from English, not organically written.
- **Size:** 6,533 items.
- **Labels:** binary (suicidal / not), no severity gradient.
- **Transfer to this app:** weak. Machine-converted code-mixing does not sound like how a student actually
  types Hinglish; adult Reddit-post register; binary label loses the none/concern/checkin/crisis gradient
  this project needs.

## 2. CLPsych shared tasks (2019/2021/2022/2024/2025)

Real, clinically well-curated, English-only — but every vintage gates behind a real agreement, not a quick
download. 2021 used Twitter data via a secure data enclave (Qntfy/NORC data-use agreements). 2022 partly used
eRisk data under its own DUA. 2024/2025 required a signed Data User Agreement per team member, sometimes with
IRB approval (UMD protocol 1642625, Warwick ethics committee), before release of a password-protected dataset.
(aclanthology.org/events/clpsych-2021/, aclanthology.org/2024.clpsych-1.22.pdf, arxiv.org/pdf/2504.14066)

- **Access right now:** no — application + agreement, realistically weeks.
- **Language:** English only.
- **Transfer to this app:** even if obtained, Twitter/Reddit clinical-research register, not Indian college
  student check-in/journal/chat text.

## 3. UMD Reddit Suicidality Dataset

Real and formally governed. Requests go through Philip Resnik (UMIACS) via a two-part application reviewed
by a 5-member committee set up with the American Association of Suicidology; UMD IRB classified it Exempt
Category 4; a confidentiality agreement is signed before release.
(users.umiacs.umd.edu/~resnik/umd_reddit_suicidality_dataset.html)

- **Access right now:** no — committee review, not fast.
- **Size:** ~11,129 r/SuicideWatch posters plus matched controls, longitudinal, with an expert-annotated
  subset.
- **Language:** English only.
- **Transfer to this app:** real mismatch — long autobiographical adult Reddit posts, not short check-in
  entries from Indian college students.

## 4. English datasets that ARE quickly downloadable (but weaker fit)

- **Kaggle "Suicide and Depression Detection"** (nikhileswarkomati/suicide-watch): r/SuicideWatch +
  r/depression vs r/teenagers. Free account, genuinely fast. Label = subreddit of origin, not expert
  judgment — weak ground truth, no severity gradient, Reddit-post register.
- **Dreaddit** (Turcan & McKeown, LOUHI 2019): stress, not suicide. ~3.5K MTurk-labelled segments from 190K
  Reddit posts. Fast access (zip or HF mirror), but tangential domain (stress, not crisis) and MTurk crowd
  labels, not clinician labels.
- **CEASE** (IIT Patna, Ghosh et al., LREC 2020): English suicide *notes* with 15 fine-grained emotion labels
  (aclanthology.org/2020.lrec-1.201). **CARES** extends it with emotion-cause spans and 837 non-English
  (Hindi/Bangla/Telugu) sentences, but explicitly gated behind "filling and signing a data compliance form" —
  not instant. **CoMCEASE-v2.0** is the actual Hindi-English code-mixed suicide-note corpus; no public access
  instructions found, likely another email-the-authors case.
- **Transfer to this app:** suicide notes are a fundamentally different register from live check-in text —
  final, retrospective, often formal — and labels like "perceived burdensomeness"/"thwarted belongingness"
  don't map cleanly onto a none/concern/checkin/crisis scale.

## 5. Other Hindi/Hinglish mental-health datasets

No other real, checkable Hindi/Hinglish suicide-risk/depression dataset surfaced across HASOC/Dravidian-
CodeMix-style shared tasks in two search rounds. This is not exhaustive — something obscure could still exist
— but nothing concrete turned up.

## Bottom line

No dataset found is simultaneously (a) obtainable today without a weeks-long application/DUA/IRB process,
(b) Hindi/Hinglish-covering, and (c) a good domain match for a student check-in/journal/chat app. The fast
English options (Kaggle, Dreaddit) have weak or off-target labels and Reddit-post register mismatch; the
clinically stronger options (CLPsych, UMD, CEASE/CARES) all require real agreements; the one Hindi-English
corpus found (ICON 2021) has unconfirmed access and machine-converted, not organically written, text.

**This survey does not change the a4 gate.** It does not identify a dataset this project can license and use
this week, and it is not a substitute for the clinician-labelled 600-item eval set the owner is building.

Not verified: whether the Columbia-hosted Dreaddit zip is currently live; non-English code-mixed shared tasks
beyond what two search rounds surfaced; the Kaggle dataset's exact current license text.

Sources: aclanthology.org/2021.icon-main.14 · aclanthology.org/events/clpsych-2021/ ·
aclanthology.org/2024.clpsych-1.22.pdf · arxiv.org/pdf/2504.14066 ·
users.umiacs.umd.edu/~resnik/umd_reddit_suicidality_dataset.html · aclanthology.org/2020.lrec-1.201 ·
DOI 10.1007/978-3-030-99739-7_15 (CARES) · arxiv.org/abs/2206.06141 (CoMCEASE) ·
huggingface.co/datasets/andreagasparini/dreaddit
