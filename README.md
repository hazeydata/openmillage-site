# OpenMillage site
Static GitHub Pages site built by `python3 build.py` from ../ptax/data into docs/. Serve docs/ via Pages (branch main, /docs).

## Ballot measure 3 baseline page (OM-FL-AMEND3-BASELINE-001)
`python3 amend3.py` (run after `build.py`) writes the page at the slug in `amend3_config.json` (one value; it is currently `fl/amendment-3`), a CSV/JSON of exactly the rows shown, a sitemap entry and an llms.txt line. The heading is `title` from the fact-verified ballot file, and `ballot_number` is shown only as a label. If the ballot file is missing, if `title` or `ballot_number` is absent, or if the title is a label such as "Ballot Number: 3", the build fails closed. The build also fails if any number lacks an adjacent source link, or if forecast or advocacy terms appear outside the quoted official text. Tests: `python3 tests/test_amend3.py`. It is not wired into the CI workflow yet: going live needs the owner's publish approval.
