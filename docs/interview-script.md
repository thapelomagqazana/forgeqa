# ForgeQA - Discovery Interview Script

> **Project Status: Pre-alpha**
> **Version**: 0.1.0
> **Last Updated**: 2026-10-27
> **Owner**: Solo Developer
> **Estimated Duration**: 20–30 minutes

---

## 1. Consent Request (Read Aloud)

> *"Thank you for taking the time to speak with me. I'm researching how QA engineers set up and maintain test automation. This is product research, not a sales pitch.*
> *The conversation should take about 20–30 minutes. I'd like to take notes to remember your insights accurately. I will not record audio or video unless you explicitly agree. Your name will not appear in any public documentation — I'll use an anonymised ID like 'U-001'. You can ask me to stop or delete your data at any time.*
> *Do you consent to participate and have me take notes for product research purposes?"*

**Consent Checklist** (Tick before proceeding):

- [ ] Participant has verbally consented to participate.
- [ ] Participant has consented to note-taking.
- [ ] Participant has consented to audio recording (if applicable).
- [ ] Participant has been informed they can withdraw at any time.

---

## 2. Interview Sections

### Section A: Context (5–7 minutes)

> **Goal**: Understand the participant's role, team, and current workflow. No product mention.

| # | Question | Open-Ended Check |
| :--- | :--- | :--- |
| A1 | Tell me about your current role and what a typical week looks like for you. | ✅ Open |
| A2 | What does your team's testing stack look like today? (Languages, frameworks, CI tools) | ✅ Open |
| A3 | Walk me through how you set up a new automation project from scratch. What are the first steps? | ✅ Open |
| A4 | Who else is involved in maintaining the test suite, and how do you collaborate? | ✅ Open |

### Section B: Pain (10–12 minutes)

> **Goal**: Uncover real, recent pain points. Ask for concrete examples. Avoid leading questions.

| # | Question | Open-Ended Check |
| :--- | :--- | :--- |
| B1 | Tell me about the last time a test failed in CI and you had to investigate. What happened? | ✅ Open |
| B2 | How did you determine whether the failure came from the product, the test, the environment, or the test data? | ✅ Open |
| B3 | What parts of your automation setup feel repetitive when you start a new project? | ✅ Open |
| B4 | What takes the most time to maintain in your current test suite? | ✅ Open |
| B5 | If you could remove one recurring task from your workflow, what would it be and why? | ✅ Open |
| B6 | Have you tried to solve any of these problems with existing tools or templates? What worked and what didn't? | ✅ Open |

### Section C: Adoption (5–7 minutes)

> **Goal**: Understand switching barriers and willingness to adopt new approaches. No selling.

| # | Question | Open-Ended Check |
| :--- | :--- | :--- |
| C1a | What would make you unwilling to adopt a new testing framework or tool? | ✅ Open |
| C1b | And what would make you *willing* to try one? | ✅ Open |
| C2 | What would need to be true for you to try a new approach on a real project? | ✅ Open |
| C3 | Would you be willing to try a small prototype on a separate application? What would it need to do first? | ✅ Open |

### Section D: Wrap-Up (2–3 minutes)

| # | Question | Purpose |
| :--- | :--- | :--- |
| D1 | Is there anything else you'd like to share about your automation experience that I haven't asked? | Open-ended |
| D2 | Would you be interested in being contacted again for a follow-up or to try a prototype? | Recruitment for Design Partners |
| D3 | Do you have any questions for me? | Reciprocity |

---

## 3. Interview Timing Guide

| Section | Target Time | Cumulative |
| :--- | :--- | :--- |
| Consent & Introduction | 2 mins | 2 mins |
| Section A: Context | 5–7 mins | 7–9 mins |
| Section B: Pain | 10–12 mins | 17–21 mins |
| Section C: Adoption | 5–7 mins | 22–28 mins |
| Section D: Wrap-Up | 2–3 mins | 24–31 mins |
| **Total** | **20–30 mins** | **~25 mins avg** |

> **Rule**: If the interview runs over 30 minutes, prioritise Section B (Pain) and skip C3 if necessary. The pain points are the most critical data.

---

## 4. Interviewer Guidelines

| Principle | Action |
| :--- | :--- |
| **Ask for recent examples** | "Tell me about the last time..." not "Do you usually..." |
| **Avoid leading questions** | Never say "Don't you think X is a problem?" Instead: "How do you handle X today?" |
| **Probe for specifics** | "Can you give me an example?" "What happened next?" "How long did that take?" |
| **Stay neutral** | Do not defend or promote any solution. Nod, take notes, and ask follow-up questions. |
| **Silence is okay** | After asking a question, wait 5 seconds before prompting. The participant may add more. |
| **Record verbatim quotes** | When you hear a strong statement, write it down exactly (e.g., "We spend more time investigating than writing tests"). |

---

## 5. Pilot Log

> **Instructions**: Before using the script on real participants, pilot it with a peer or record yourself. Note the timing and any questions that felt confusing or leading.

| Pilot Date | Pilot Participant (Role) | Duration | Issues Identified | Changes Made |
| :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | Peer (e.g., Senior Developer) | XX mins | (e.g., "B3 felt slightly leading") | (e.g., "Rephrased B3 to 'What parts feel repetitive?'") |
| YYYY-MM-DD | Self-recorded | XX mins | (e.g., "C1 felt negative") | (e.g., "Added C1b: 'And what would make you willing?'") |

---

## 6. Post-Interview Checklist

After each interview:

- [ ] Fill out the Interview Evidence Template in `docs/user-discovery.md` (U-XXX).
- [ ] Update the candidate's status in the Notion pipeline (0.2.3).
- [ ] Assign the next `Interview ID` (e.g., U-002).
- [ ] Record any new hypotheses or risks in `docs/risks.md`.
- [ ] Note any follow-up actions (e.g., "Send prototype link in 4 weeks").

---

## 7. Document History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| 0.1.0 | 2026-10-27 | Solo Dev | Initial script created from Project Brief (Section 3.3). |
