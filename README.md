# VerifyMyMU

**Nine published top-down measurement-uncertainty models for medical laboratories, in one offline HTML file.**

VerifyMyMU computes the measurement uncertainty of a clinical measurement procedure from the data a laboratory already holds — internal quality control (IQC) results and external quality assessment (EQA) reports — under nine published model formulations at once, and states which of them the laboratory's EQA scheme supports.

* ISO/TS 20914:2019 · ISO/TS 20914 with an added laboratory bias term · Nordtest TR 537 (RMS form) · Nordtest (SEM variant) · mean-bias form (SEM across rounds) · EUROLAB TR 1/2007 reading · Cofrac SH GTA 14 · Cofrac range variant (Martinello et al. 2020) · ISO 21748:2017
* The four choices the guidance leaves open are separate settings: precision source (pooled / ANOVA), coverage rule (k = 2 / Welch–Satterthwaite / seeded Monte Carlo), treatment of an uncorrected bias (RSSu, RSSU, SUMU, SUMU_MAX, Synek Ue) and source of u(Cref).
* An **applicability screen** classifies each model as applicable, conditional, sensitivity-only or not applicable from the type of assigned value of each EQA round (traceable vs participant consensus), by pre-specified criteria.
* Every printed figure comes with the arithmetic that produced it; the record is printable as a PDF.

## Running it

A two-minute narrated tour of the application is in `docs/VerifyMyMU-tour.mp4` (also submitted with the paper as Supplementary Video S1).


Open `VerifyMyMU.html` in a current browser (Chrome, Edge, Firefox, Safari). Nothing is installed, nothing is sent anywhere: the file has no network access, no server component and no external libraries at run time, so it can be used on a workstation inside a hospital network.

1. **Estimate MU** — load your IQC export (any column layout; headers are matched across languages, decimal commas and day-first dates are handled, or map the columns by hand), define the measurand and procedure, add the EQA rounds with the type of assigned value, and read all nine models side by side against an allowable-uncertainty limit (EFLM biological variation, your EQA provider's limit, or your own).
2. **MU method lab** — move the four open conventions and watch the result change.
3. **QC review** — Levey–Jennings charts; excluding a point recomputes everything.
4. **Report** — one record per analyte, or a set of analytes, with the model, the conventions and the arithmetic stated.

`examples/` holds the albumin IQC and EQA files used in the worked example of the paper; `templates/` holds an Excel data-entry template for laboratories that prefer to type summary values.

## Verification

`verification/` contains the scripts that are re-run after every change to the file. They need Python 3.10+, `numpy`, `scipy` and `playwright` (`pip install numpy scipy playwright && playwright install chromium`).

| Script | What it checks | Needs |
|---|---|---|
| `nordtest_val.py` | Reproduces the Nordtest TR 537 ed. 4 ammonium example (§3.2 / Appendix 4) to the printed digits | the HTML only |
| `check_prec.py` | Pooled and ANOVA precision estimators against an independent implementation (≤ 1e-6); the four sources of u(Cref) | `examples/` |
| `check_mc.py` | Monte Carlo coverage: seed reproducibility, agreement with an independent 400 000-draw simulation, invariance to the bias point estimate | the HTML only |
| `check_ui.py`, `check_full.py` | Drive the application as a user would (file formats, screens, decision guide, exclusions, downloads, reset) and check what each screen says | `examples/` |
| `check_models.py`, `check_axes.py` | Independent Python re-implementation of the nine models over the full grid of conventions (4662 comparisons in the paper) | the laboratory data files in `data/` (see below) |
| `run_models.py`, `run_axes.py` | Produce the result files that the two scripts above compare against | `data/` |

`data/` is not part of this release: the IQC results belong to the laboratory and the EQA data to Labquality Oy, and are available from the author on reasonable request subject to those permissions. `check_models.py` and `check_axes.py` run unchanged on any laboratory's own files in the same layout (`eqa-final.csv`, `iqc-summary.csv`).

## Citing

If you use VerifyMyMU, please cite the Zenodo record of the version you used (see `CITATION.cff`) and, once published, the accompanying paper:

> Kilinckaya MF. Nine top-down measurement uncertainty formulations on one clinical chemistry dataset: how much of a reported uncertainty depends on choices the guidance leaves open. *Scand J Clin Lab Invest* (submitted).

## Status and licence

Research software, offered as an auditable reference implementation. It is not a medical device and has not been validated as one. Released under the MIT License (see `LICENSE`). The databases embedded in the file (EFLM biological-variation limits, calibrator traceability constants) carry the terms of their respective owners.

Author: Muhammed Fevzi Kilinckaya, Helse Møre og Romsdal, Norway — ORCID 0000-0002-0815-5467.
