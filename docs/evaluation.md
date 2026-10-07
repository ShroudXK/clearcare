# Evaluation results

Snapshot date: **2026-10-07**. All **30 predefined software scenarios passed**. The separate regression suite contains **24 test methods**, including one that reruns these scenarios. These counts overlap.

The dataset audit found **0 issues across 9 content/graph checks**. Primary and foreign keys are also enforced during ingestion. This is not a count of independently verified medical facts.

## Expected and actual behavior

| Case | Expected | Actual | Result |
|---|---|---|---|
| Campus: fee distinction included | `True` | `True` | PASS |
| Campus: official booking included | `True` | `True` | PASS |
| Community: no campus fee assumption | `False` | `False` | PASS |
| Community: network questions included | `True` | `True` | PASS |
| Follow-up: no clinical timetable assigned | `True` | `True` | PASS |
| Interpreter requested | `True` | `True` | PASS |
| No interpreter requested | `False` | `False` | PASS |
| Missing insurance card | `True` | `True` | PASS |
| Insurance card present | `False` | `False` | PASS |
| Prior records available | `True` | `True` | PASS |
| Prior records unavailable | `True` | `True` | PASS |
| Record paths mutually exclusive | `False` | `False` | PASS |
| McKinley referral condition true | `True` | `True` | PASS |
| McKinley referral condition false | `False` | `False` | PASS |
| Plan identity before network questions | `True` | `True` | PASS |
| No duplicated preparation steps | `15` | `15` | PASS |
| Emergency skips preparation workflow | `0` | `0` | PASS |
| Emergency skips insurance questions | `False` | `False` | PASS |
| Coverage is never confirmed | `False` | `False` | PASS |
| Expired sources replace asserted instructions | `True` | `True` | PASS |
| No evidence before the review date | `True` | `True` | PASS |
| No network observation stays unknown | `unknown` | `unknown` | PASS |
| Synthetic observations excluded by default | `unknown` | `unknown` | PASS |
| Latest demo observation selected | `observed_in_network` | `observed_in_network` | PASS |
| Demo result explicitly labeled synthetic | `True` | `True` | PASS |
| Observed network does not prove coverage | `False` | `False` | PASS |
| Expired demo observations stay unknown | `unknown` | `unknown` | PASS |
| Provider mismatch stays unknown | `unknown` | `unknown` | PASS |
| Facility mismatch stays unknown | `unknown` | `unknown` | PASS |
| Disagreeing sources flagged | `conflicting` | `conflicting` | PASS |

## Dataset and evidence counts

| Measure | Count |
|---|---|
| `sources` | 16 |
| `facilities` | 4 |
| `services` | 4 |
| `facility_services` | 6 |
| `resources` | 8 |
| `prep_steps` | 22 |
| `step_applicability` | 27 |
| `step_sources` | 26 |
| `step_dependencies` | 7 |
| `plan_versions` | 0 |
| `network_observations` | 0 |

## What these results support

The workflow produces consistent fixed-date guides, follows configured conditions and dependencies, protects the previous database when a build fails, and handles the predefined uncertainty cases. The published examples can be regenerated and compared byte-for-byte.

## What remains untested

No human usability study, clinical review, bilingual professional review, real insurance integration, or appointment completion has been measured. Passing these cases does not demonstrate improved health outcomes, fewer bills, comprehensive healthcare accuracy, or suitability for every user.

Initial source retrieval succeeded for 16/16 sources with matching anchors; this is documented separately from the software evaluation. Retrieval success alone is not semantic validation.

Machine-readable reports: [evaluation.json](results/evaluation.json) and [data_quality.json](results/data_quality.json). Run commands and troubleshooting: [workflow.md](workflow.md).
