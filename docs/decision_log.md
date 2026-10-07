# Design decisions and implementation notes

| Decision | Reason | Trade-off |
|---|---|---|
| Limit geography to Champaign–Urbana | Local official information can be inspected and traced | The guide does not represent all U.S. healthcare systems |
| Start fracture follow-up after initial assessment | This is a concrete appointment-preparation problem | Acute injury triage remains outside the project |
| Use Python + DuckDB + standalone SQL | Extends the lab's relational approach and makes queries reviewable | A future multi-user operational service would need a different deployment design |
| Export HTML and Markdown rather than build a large app | Keeps attention on research and the complete data workflow | The user cannot change all inputs through a browser interface |
| Keep individual network evidence empty | General institutional pages do not establish a student's actual coverage | Insurance functionality currently provides verification prompts |
| Use labeled synthetic fixtures in a rollback transaction | Exercises version and conflict logic without inventing real insurance findings | Test cases cannot establish real network accuracy |
| Suppress dated instructions after review intervals expire | Avoid silently displaying old local requirements as current | Even correct unchanged information needs a new review |
| Keep original source pages out of the repository | Avoid redistributing full third-party pages and keep the repo small | A later reader cannot reconstruct the original full page from its hash |
| Use project-created Chinese translations | Supports the intended language barrier | No professional translation review has been performed |
| Disclose AI assistance and unfinished user research | Make the scope of the evidence clear | The author still needs to understand, review, and explain the implementation |

During development, a Carle location-detail page was inconsistently accessible in browsing. The usable official service page supported the location name and advertised service category, but a detailed street address was left blank. A successful later retrieval does not erase that access limitation.

General CMS preparation advice mentions that offices can have different cancellation rules. The project uses the current McKinley appointment page for the campus-specific cancellation step rather than applying a general deadline to every office.

Duplicate step applicability tags could have multiplied rows in a direct join. The query uses `EXISTS`, and evaluation checks unique step IDs. Temporary database construction avoids parent-table replacement failures when foreign keys already exist. A regression test verifies that a failed rebuild leaves the previous database unchanged.

Review date: 2026-10-07. Completed software results are generated from the code and snapshot; future usability and clinical review remain explicitly unfinished.
