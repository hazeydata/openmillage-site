# Page copy and chart sources (OM-PAGE-REDO-001)
- `copy.md`: Lindsay's final copy v2, verbatim from openmillage-meta `cycles/2026-10-23-page-redo/lindsay-copy-draft.md` @ afab3f2 (local commit). To update: replace `copy.md` with the new file and rebuild. Every section is parsed by `redo.py`; nothing is retyped.
- `../assets/charts/`: Her?'s dark charts from openmillage-meta `cycles/2026-10-23-page-redo/her/` (final history re-cut on openmillage@7c1a525): her-alachua-bar-{350,720}-dark.svg, her-county-dots-{350,720}-dark.svg, her-history-multiples-{350,720}-dark.svg. Inlined into pages by `redo.py` so they render with the self-hosted fonts.
- `../assets/fonts/`: Her?'s static TTFs (Inter 400/600/700, Space Grotesk 600), copied to docs/fonts/ and loaded with @font-face.
- History data: `data/history/fl_millage_history.csv`, pinned in data/SOURCES.lock to hazeydata/openmillage@7c1a525.
