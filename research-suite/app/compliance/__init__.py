"""
The compliance engine: writing to someone else's criteria.

Three documents govern an academic submission and none of them is APA: the
assignment rubric, the course syllabus, and — for publication — the journal's
author guidelines. Each states requirements in prose, each is graded or
desk-rejected against, and each is routinely read once at the start and never
again.

This package reads those documents into a checklist, then checks the draft against
it continuously, so a missing requirement surfaces while there is still time to
write it rather than after the grade comes back.

`rubric.py` extracts requirements. `simulator.py` checks a draft against them.
`journals.py` holds submission profiles and parses new ones.
"""
