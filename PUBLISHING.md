# Publishing VerifyMyMU 1.0.0 on GitHub and Zenodo (one-time, ~20 minutes)

Two things have to be true before the paper is submitted: the file has a DOI, and the DOI points to exactly the version used for the paper. The GitHub → Zenodo integration gives both, and every later release gets its own DOI under one "concept DOI".

## A. GitHub
1. Sign in to github.com and create a new **public** repository named `VerifyMyMU` (no README, no licence — the folder already has them).
2. Upload the contents of this folder (`VerifyMyMU.html`, `README.md`, `LICENSE`, `CITATION.cff`, `.zenodo.json`, `CHANGELOG.md`, `verification/`, `examples/`, `templates/`, `data/README.md`). Drag-and-drop in the browser works; or from a terminal:
   ```
   git init && git add -A && git commit -m "VerifyMyMU 1.0.0"
   git branch -M main
   git remote add origin https://github.com/mfkilinckaya-svg/VerifyMyMU.git
   git push -u origin main
   ```
3. `CITATION.cff` already carries the user name; the `doi:` line is filled in step C.

## B. Connect Zenodo
1. Sign in to zenodo.org **with GitHub** (Log in → GitHub). Use your ORCID-linked account if you have one.
2. Zenodo → your name (top right) → **GitHub** → find `VerifyMyMU` in the list → switch it **ON**.
3. Nothing is archived yet; Zenodo waits for a GitHub *release*.

## C. Make the release
1. GitHub → repository → **Releases** → **Draft a new release**.
2. Tag: `v1.0.0`. Title: `VerifyMyMU 1.0.0`. Description: paste the 1.0.0 block from `CHANGELOG.md`.
3. **Publish release.** Within a minute Zenodo creates a record from `.zenodo.json` (title, your ORCID, licence, keywords are already in it) and mints two DOIs: one for v1.0.0 and a concept DOI that always resolves to the latest version.
4. Copy the **version DOI** (10.5281/zenodo.NNNNNNN). Put it in `CITATION.cff` (`doi:` line) and in the README badge if you like, commit — this does **not** need a new release.

## D. Paper
Replace the two `[repository or DOI]` placeholders in the manuscript with:
`https://github.com/mfkilinckaya-svg/VerifyMyMU (version 1.0.0, doi:10.5281/zenodo.NNNNNNN)`.
Use the **version** DOI in the paper, not the concept DOI, so a reader gets the file the paper was computed with.

## Notes
* Zenodo reads `.zenodo.json` at release time; if you prefer the record to say "Helse Møre og Romsdal HF" or add a second affiliation, edit that file before step C.
* If you would rather not use GitHub: Zenodo → **New upload**, drag the whole folder as a zip, type = Software, fill the same fields by hand, **Publish**. You still get a DOI; you lose the automatic per-version archiving.
* The data files (`data/`) stay out of the release until the SERO AS permission is in writing; the README already says how they can be requested.
