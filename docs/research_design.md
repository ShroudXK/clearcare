# Research design

## Problem and scope

An international student may know that care is needed but be unfamiliar with U.S. appointment entry points, referral language, insurance networks, and documents. ClearCare studies how to organize these navigation tasks into a source-linked preparation guide.

The first population is UIUC international students in Champaign–Urbana. The main demonstration concerns follow-up after a fracture has already been assessed. The guide starts from the treating clinician's instructions. It does not classify symptoms, decide whether an injury is a fracture, or choose a treatment timetable.

Three questions guide the design:

1. Which official information is needed before contacting an office or insurer?
2. Which requirements can be stated from a public source, and which must remain confirmation questions?
3. Can a relational database generate different preparation paths while preserving source links and uncertainty?

## Source selection

Sources were identified through searches of official institutional and government domains, then opened for inspection. Included sources provide local appointment entries, advertised services, fee rules, record/referral processes, general insurance concepts, or visit-preparation guidance. The complete set contains 16 sources.

Excluded materials include social-media advice, search snippets used without opening the source, old student-insurance brochures, commercial ranking pages, and individual coverage conclusions. No nationwide provider dataset was added simply to increase the row count: it would not establish current appointment availability or a student's actual network.

The research is a bounded desk review, not a systematic literature review. It did not establish the prevalence of these barriers or compare healthcare outcomes. The small sample prioritizes traceable local information over broad coverage.

## Collection and coding procedure

1. Identify a relevant primary source and inspect the appropriate section.
2. Retrieve its HTML or PDF; record the final URL, response status, byte hash, and extraction checks.
3. Summarize only information supported by that source. Keep the relevant section or PDF page locator.
4. Classify each preparation item as **education**, **action**, or **question**. A question requests confirmation; it is not a claimed institutional requirement.
5. Add scenario applicability and preparation conditions. Keep source links in a separate relation so an item can use more than one source.
6. Translate the English summary into concise Chinese while preserving terms such as referral, deductible, and prior authorization.
7. Check the typed tables, relationships, guide order, and uncertainty cases before exporting results.

Review dates represent this project's source inspection, not confirmation by providers, insurers, or clinicians. SHA-256 hashes and short text anchors provide retrieval evidence but cannot establish semantic accuracy. Full pages were retained locally during development and excluded from publication; the public repository contains summaries, URLs, and metadata.

## Key findings used in the design

| Finding | Design response | Primary source |
|---|---|---|
| McKinley's fee-funded care and outside-care insurance are different mechanisms | Explain the distinction in the campus path; do not assign an insurance network to McKinley from the fee page | [Health Service Fee](https://mckinley.illinois.edu/fees/health-service-fee) |
| Provider network information requires checking a particular plan and provider | Generate directory and phone-confirmation steps; retain `unknown` when no observation exists | [Finding a provider](https://www.healthcare.gov/using-marketplace-coverage/getting-medical-care/) |
| Preauthorization is not a guarantee of payment | Keep service coverage unconfirmed even if a network observation exists | [Preauthorization](https://www.healthcare.gov/glossary/preauthorization/) |
| Local walk-in options differ in advertised diagnostics | Store location–service relationships with scope notes; avoid guaranteeing a specific test | [Carle walk-in services](https://carle.org/services/convenient-care-and-convenient-care-plus) |
| Existing records and a clear list of questions help preparation | Add conditional record-transfer steps and visit question prompts | [CMS preparation, PDF pp. 4–7](https://www.cms.gov/marketplace/outreach-and-education/downloads/c2c-prepare-for-your-visit.pdf) |
| Language support should be discussed with the office in advance | Include an interpreter question only when requested; do not assume availability | [NLM visit preparation](https://medlineplus.gov/talkingwithyourdoctor.html) |

## What was evaluated

Completed evaluation covers predefined software behavior, relational integrity, input checksums, repeatable guide text, source age, conditional paths, synthetic-data isolation, and parameter binding. The expected behavior was defined explicitly in `clearcare/evaluate.py`, with additional regression tests in `tests/`.

These checks show that the implementation behaves as specified for those cases. They do not establish that the healthcare content is clinically adequate, that every possible case is handled, or that students can use it successfully.

## Future user-study protocol — not yet conducted

Recruit 5–8 adult international students through a voluntary invitation. Use fictional appointment scenarios and do not collect medical records or insurance member IDs. Ask participants to:

1. Locate an official appointment entry for a specified visit.
2. Identify what to ask the insurer about a provider and location.
3. Assemble a preparation checklist for an already-assessed fracture follow-up.
4. Explain which information remains unconfirmed.

Record task completion, time, mistakes, misunderstood terms, and whether participants incorrectly believe coverage has been guaranteed. Compare ordinary browsing with the guide using counterbalanced task order; interpret a small sample descriptively. Ask permission before recording and consult applicable university research requirements before recruitment.

Review the English and Chinese wording with a qualified healthcare professional and bilingual users. No participant responses, usability numbers, or professional approvals are included in this repository because that work has not occurred.
