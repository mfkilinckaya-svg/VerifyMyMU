Place here, to run `check_models.py`, `check_axes.py`, `run_models.py` and `run_axes.py`:

* `eqa-final.csv` — one row per EQA observation. Columns: `round, analyte, sample, own, assigned, bias_pct, z, type, ucref_pct, group, group_x, group_sem, group_sd, group_n, instr, bias_used, bias_source, excluded, ucref_used, ucref_note, ucref_mid_alt, ucref_max_alt` (`type` is `Xt` for a transferred/traceable value, `Xrob` for a robust participant consensus).
* `iqc-summary.csv` — one row per measurand-level. Columns: `test, level, n, start, end, mean, sd, u_Rw_pct, u_Rw_pooled_instr_pct, within_lot_cv_pct, lot_shift_pct, n_reagent_lots, n_instruments`.

The files of the laboratory described in the paper are available from the author on reasonable request, subject to the permissions of Labquality Oy and SERO AS.
