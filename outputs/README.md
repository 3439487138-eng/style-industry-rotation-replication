# Replication outputs

A successful current execution writes:

- `report.json`: auditable run evidence and report payload;
- `report.html`: standalone HTML with embedded figures.

The full strategy also writes performance, monthly return, NAV, positions, signal and factor-effectiveness CSV files, a Markdown report and three figures. No file is pre-populated because authorized production data is currently missing. Test fixtures are written only to temporary test directories and must never be copied here.
