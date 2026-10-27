# Teacher guidance in Topic Card enrichment

Newly generated activities include:

- `expected_answer`: a substantive answer guide for the teacher; open tasks may list acceptable alternatives or required ideas.
- `assessment_criteria`: a non-empty list of observable, task-specific checks. A grading scale is not implied.

Generation rejects missing, null, blank answers, empty criteria lists and blank criteria. The existing text-quality check also covers these fields. The prompt requires concrete examples and evidence-backed answer guides, with wording appropriate to the grade and level.

These checks enforce structure, not historical accuracy or pedagogical quality. Before applying a candidate, a teacher still checks that the evidence supports its facts, the answer actually addresses the task, the criteria match it and the task can be completed with available materials. A listed source is not by itself proof of every generated claim.

## Existing candidates

The fields are optional when loading stored artifacts. Serialization omits fields that were absent from a legacy activity, preserving the exact payload and candidate hash. Existing candidates are not rewritten or upgraded automatically. Their lack of teacher guidance must still be considered during review.

The candidate schema version remains 2. Generate/save/inspect/apply stays separate; generated content remains pending_review. This change does not call the provider, apply a candidate or modify the catalog. To obtain guidance for an existing candidate, generate a new candidate, review its content and apply its own ID separately.

## Live validation (2026-10-26)

Two real generations used the configured HTTP provider and gpt-6-luna on
"Первобытное общество" (grade 5). Both passed structural validation and saved
candidates without applying changes to the catalogue.

- Initial candidate: a70489b8757a009401fa259c7cd73f6c7c441073a83ad96f2264410c3e4d60cf.
- Refined-prompt candidate: f89c2d01eef145ce121a5294b5fa94c820afcd44696ea5af6d9a6c4d3411f3cb.

Manual review found that the first draft included a criterion beyond the task
and omitted a requested example. The refined draft reduced generic examples,
but its first answer still omitted an example of a subsistence activity despite
asking pupils for one. Neither draft is approved for application.

Retrieval supplied three short curriculum excerpts, mainly lists of topics,
not detailed textbook explanations. Chunk references do not establish support
for every generated claim. Broader source coverage and manual review remain
necessary; structural validation is not semantic certification.

Validation: 122 tests passed, with one existing Pydantic serialization warning
in test_generation.py; git diff --check passed. A pre-existing saved candidate
also loaded successfully with its original hash unchanged.

## Semantic review and expanded retrieval (2026-10-27)

New enrichment generation searches the topic title and up to three distinct
key concepts within the SAME linked-source, subject, grade and level scope.
It requests 2400-character excerpts instead of the default 520; other search
callers retain the default. Requests are bounded to four searches of eight
hits each, duplicates are removed, and the existing relevance filter still
selects at most six excerpts. This improves access to existing explanations;
it does not add books or prove that the stored corpus contains them.

After structural validation, a separate structured model call reviews source
sufficiency, factual grounding, completeness of every expected answer and
alignment of its criteria. Every activity must be reviewed exactly once.
Any issue, negative verdict, missing review capability or malformed report
blocks the new candidate. No automatic repair loop or database apply occurs.
A model review is fallible and is not expert certification: accepted candidates
still require manual review. Generation now costs one additional model call.

Existing saved candidates and their hashes are unchanged. Applying a legacy
candidate does not retroactively run this gate; review it before explicitly
applying it. This gate protects newly generated enrichment candidates only.

Live check: the topic "Первобытное общество" has only one linked source,
the federal history programme (236 stored chunks). Expanded search returned
17 unique hits; six selected excerpts contained 1858–2302 characters each.
The new real draft was blocked for insufficient evidence and an extra
criterion not requested by the task. Reviewing the saved f89c2d01... draft
also detected the missing example for subsistence economy in activity 0.
Neither check applied catalogue changes. Add suitable explanatory source
material before expecting this topic to pass the grounding gate.

Validation: 137 tests passed; one pre-existing Pydantic warning remains.
