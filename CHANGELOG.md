# Changelog

## 1.1.0 — 2026-11-10
Revision after peer review. **No change to any calculation**: the only strings that differ from 1.0.0 are the label texts listed below and the version string (a statement-level diff is reproduced in Supplementary File S3).

* Applicability-screen label renamed from "sensitivity only" to "agreement only" (reviewer suggestion): the models so labelled measure agreement with the peer group, not trueness. The internal status key is unchanged.
* `index.html` added so that the GitHub Pages address opens the application directly.
* Verification scripts: `check_prec.py` no longer assumes a fixed decimal separator and uses the correct example file; `check_full.py` no longer expects fixtures at a fixed path (seeded fixture generator added). `examples/example-IQC-albumin-paper.csv` added (the IQC example embedded in the application).
* `CITATION.cff`: DOI filled in. `docs/`: Supplementary File S3 (verification report).

## 1.0.0 — 2026-10-04
First public release; the version used for the analyses in the accompanying paper.

* Nine model formulations; applicability screen with pre-specified criteria; four open conventions as settings.
* Seeded Monte Carlo coverage (point estimate of bias applied after the draw, not drawn).
* Allowable-uncertainty limit from EFLM biological variation (desirable / optimum / minimum), the EQA provider, a state-of-the-art value or a user value; limit bars in the model chart; chosen limit carried into the report.
* Bias from a certified reference material: two routes (as the reference value of a round, or as a corrected-bias component with declaration).
* Multi-analyte report set; printable PDF record stating model, conventions and arithmetic.
* Verification suite: worked examples, independent re-implementation (4662 comparisons), ANOVA estimator, u(Cref) sources, Monte Carlo properties, user-interface drive.
