# Professional lesson artifact v2

## Purpose

The lesson artifact is a ready-to-teach professional teacher document, not a
short administrative outline. It must remain grounded in the selected Topic
Card and retrieval manifest and must never invent source pages, quotations,
curriculum codes, or claims of formal regulatory approval.

## Methodical basis

The runtime contract follows these official current reference points:

- Federal working programmes publish subject content, planned results, and
  types of student activity: https://edsoo.ru/rabochie-programmy/
- The federal programme registry contains current revisions of federal
  educational programmes: https://fgosreestr.edsoo.ru/educational-programs
- The EDSOO methodological collection includes current guidance for history
  and social studies, assessment, differentiation, and variability:
  https://edsoo.ru/metodicheskie-dokumenty/
- The official federal secondary-general-education programme was approved by
  Ministry of Education order No. 371:
  https://publication.pravo.gov.ru/document/0001202307130017

The generated `fgos_alignment` is therefore operational: it links a verified
planned result to student activity and observable assessment evidence. It is
not a substitute for the school's approved programme and must not invent
regulatory identifiers.

## Required document sections

Every new lesson must include:

1. Passport, problem question, measurable subject outcomes, and concepts.
2. Operational alignment of subject, meta-subject, and personal results with
   student activity and assessment evidence.
3. Materials and preparation.
4. An exact minute-by-minute baseline scenario.
5. At least three detailed teacher-narrative blocks with ready-to-use subject
   explanations, transitions, prompts, board/slide notes, and attention points.
6. A concise, meaningful notebook record.
7. At least three realistic student questions with short and expanded answers
   and a teaching note.
8. Typical misconceptions with a diagnostic question, correction strategy,
   and example or counterexample.
9. Three complete delivery variants leading to the same result:
   teacher explanation, independent textbook work, and group work.
10. Differentiation, individual formative assessment, reflection, time-saving
    guidance, reserve task, and methodical notes.

## Automated acceptance gate

A lesson cannot be exported as ready when any of these conditions fail:

- timeline minutes do not equal the requested duration;
- planned results, activity, and assessment evidence are not linked;
- teacher narrative contains fewer than three blocks or fewer than 1,200
  characters of usable content;
- fewer than three student questions have complete answers;
- misconception support is absent;
- any of the three delivery variants is absent or incomplete;
- notebook notes contain fewer than two meaningful points;
- retrieval source identity, pages, or quote permissions do not match the
  backend-controlled source manifest.

This gate validates structure and evidence. The teacher remains the final
editor responsible for factual and classroom suitability review.
