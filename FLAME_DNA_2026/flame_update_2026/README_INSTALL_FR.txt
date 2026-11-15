FLAME DNA — Scientific & Catalog Update (15 Nov 2026)
======================================================

WHAT CHANGES
- NASA Online Search: 5 publications per page + Previous/Next.
- Scientific Library: 5 publications per page (60 => 12 pages).
- Data Explorer: S1, S2, Saffire-II if available, experimental table;
  'Index' is visible only as FIRST column of the preview, never in charts.
- Scientific Analysis: S1, S2 and experimental table, line curves,
  statistics and correlations without Index; availability I/II only.
- Space Mission Fire Safety: adds S1 experimental row and test table.
- Overview: NASA dataset status updated; old content retained.
- All newly added dashboard labels are English.

BEFORE INSTALLATION
- Close the Streamlit terminal using Ctrl+C.
- KEEP backups of your current project. This package does not contain your
  actual app.py, NASA datasets, or SQLite publications.
- The new catalogue UI uses NASA NTRS live search. The original file
  modules/research_catalog/catalog_ui.py remains unmodified. The original catalog management/synchronization UI remains accessible under
  Sources & Synchronization > Original Catalog Management Tools. It retains
  its prior pagination, while the TWO NEW BROWSING tabs display 5/page.

INSTALL IN WINDOWS POWERSHELL (from FLAME_DNA_2026 directory)
1. Copy modules/flame_catalog_v2.py into your modules/ folder.
2. Copy modules/flame_workspace_v2.py into your modules/ folder.
3. Copy tools/apply_flame_updates.py into your tools/ folder (create tools/ if needed).
4. Install needed dependencies, only if missing:
       python -m pip install requests openpyxl
   Ensure requirements.txt includes: streamlit, pandas, plotly, requests, openpyxl.
5. Check patch compatibility without modifying app.py:
       python .\tools\apply_flame_updates.py
6. Only when it reports DRY RUN OK:
       python .\tools\apply_flame_updates.py --apply
7. Test syntax:
       python -m py_compile .\app.py .\modules\flame_catalog_v2.py .\modules\flame_workspace_v2.py
8. Start Streamlit:
       streamlit run .\app.py

NASA DATA / S1
Official NASA PSI-98: https://psi.nasa.gov/physci/repo/data/investigations/PSI-98
DOI: 10.60555/0t15-1z43 (CC0-1.0)
Data files must be downloaded from the official NASA record (Raw Data section),
validated, and placed in:
  data/research_catalog/experiments/saffire_1/
Expected S1 file: saffire_s1_telemetry_clean.csv (or original NASA S1 sensor workbook).
Current S2 file: saffire_s2_telemetry_clean.csv.
Experimental conditions: experimental_table.csv.
No S1 telemetry CSV is included in this patch; the system explicitly reports
'not integrated' until authentic S1 measurements are supplied.
SAFFIRE-II telemetry optional at data/research_catalog/experiments/saffire_2/
  saffire_ii_telemetry_clean.csv
If source units/calibration are unknown, plots do not invent them.

STREAMLIT CLOUD
- Confirm nasa_catalog.db and needed CSV files are tracked/accessible in repo.
- Do not commit private tokens or huge, unneeded Excel files.
- Run Streamlit and review all 7 pages and alerts before sharing with jury.
- This patch does not change Real-Time Monitoring, safety-agent or alerts modules.

ROLLBACK
Replace app.py with the backup in backups/app_before_v2_*.py.
The newly copied modules may remain unused safely.

OPTIONAL NASA S1 WORKBOOK CONVERSION (after authentic NASA workbook download)
- Copy the original NASA SAFFIRE-I S1 sensor .xlsx into saffire_1 folder.
- Inspect: python .\tools\prepare_s1_csv.py
- Verify the sheet, time column and sample identification.
- Save: python .\tools\prepare_s1_csv.py --write
- A CSV and a provenance sidecar JSON will be created. The conversion does NOT
  validate units or prove combustion results.
