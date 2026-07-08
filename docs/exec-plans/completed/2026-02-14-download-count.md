# Plan: Download Count Fix

## Scope
- Track download URL generations as "total downloads" in the API.
- Expose `total_downloads` via `/files/stats` and display it in the dashboard.
- Update docs for dashboard stats output.
- Add backend tests for download count increment.

## Steps
1. Add a download counter in the service layer and include it in stats output.
2. Update types in API and shared package for `total_downloads`.
3. Wire UI stats card to show the new value.
4. Update dashboard feature doc to remove placeholder language.
5. Add tests for `/files/stats` and `/files/{key}/download` increment behavior.

