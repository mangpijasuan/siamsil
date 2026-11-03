# Siamsil vision

Updated: 2026-10-27
Source: "Siamsil Universal Literacy Platform — Master Architecture v2.0" (project owner), reviewed and adopted in part.

This document is the long-term direction. It is **not** the engineering plan: current work follows [ROADMAP.md](ROADMAP.md) and the release order in [PRODUCTION_MASTER_BUILD_PROMPT.md](PRODUCTION_MASTER_BUILD_PROMPT.md). Where they differ, the roadmap wins until this document is promoted into it.

## Direction

Siamsil grows from the digital home for the Zomi language into a literacy platform: one place where a person can learn, practice, and master what education, work, technology, money, and civic life require.

**North star.** Every feature should help answer: *What does this person need to know next to move closer to the life they want?* Features that do not improve access, learning, understanding, mastery, application, or opportunity are not core priorities.

**Our edge is the language and the community.** Free, large platforms already teach English, math, digital skills, and personal finance. None teach them *in Zomi, for Zomi people*. So Siamsil Language is the foundation of the learning platform, not a later add-on: learning in Zomi depends on dictionary, terminology, and translation quality first.

## Adopted principles

1. **Skills, not courses, are the foundation.** Knowledge is organized as a skill graph (domain → competency → skill, with prerequisite and related-to links). Courses and pathways are views over reusable skills.
2. **Mastery needs evidence.** Every mastery claim records the attempts, practice, or reviewed work behind it. Mastery decays over time and triggers review (spaced repetition).
3. **No false precision.** Learner-facing scores (percentages, levels, readiness, passports) appear only after the underlying assessments are calibrated. Until then, show progress in plain terms ("practiced", "needs review").
4. **Provenance and human review for all content.** Every lesson, question, and translation records who created it, whether AI was involved and which model, who reviewed it, its license, and its version. High-impact content moves `draft → reviewed → approved → published`. This is the same rule the language data follows.
5. **Licensed sources only.** Lessons and open educational resources are tracked in a license registry, like `data/rights.json`, preferring public domain, CC0, and CC BY.
6. **Multilingual by design.** Content is stored so it can be shown in Zomi, English, or both, with technical terms available in English.
7. **Mobile-first, low-bandwidth, offline-capable.** Many learners have a phone, limited data, and no computer.
8. **Accessible by design.** Screen readers, keyboard use, captions, transcripts, text resizing, audio, and simplified language.
9. **Education, not advice.** Health and legal topics are general education, clearly distinguished from personal medical or legal advice.
10. **Measure outcomes, not completions.** Skill mastery, retention, and goal achievement (jobs, citizenship, college), not courses finished.
11. **One account, one platform.** Learning, dictionary, and translation share the existing Siamsil identity. Literacy domains live inside one learning product, not separate apps.
12. **One tutor, grounded in approved content.** The AI tutor answers from approved lessons and sources, in Zomi and English, and says when it does not know. It runs behind a provider-neutral model interface.

## Architecture decisions

- **Keep the current stack**: Next.js frontend, FastAPI backend, PostgreSQL with Alembic, and the existing identity and roles. The learning platform is new modules in this modular monolith, not a rewrite and not separate services.
- **Restructure the repository gradually**, toward the workspace in [MOBILE_AI_ARCHITECTURE.md](MOBILE_AI_ARCHITECTURE.md); [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) tracks it under later work.
- **Add infrastructure when measurements require it**: Redis, vector search, analytics stores, additional subdomains.

## Siamsil products

Siamsil is one platform with several products, all on one Siamsil account (principle 11). Products are named "Siamsil" and a plain word, written as two words: Siamsil AI, Siamsil Library, Siamsil Docs. Each serves the language or the people who write and learn in it.

| Product | What it is | Status |
|---|---|---|
| Siamsil Dictionary, Translate, AI | The language core | Release 1 |
| Siamsil Library | Books, scripture, and cultural archives | Live; grows with Siamsil Docs |
| Siamsil Learn | Learning in Zomi | Release 2 |
| Siamsil Sign | Signatures for Siamsil's own agreements: recording consent, author agreements, permission letters | Planned; internal first |
| Siamsil Docs | Writers submit articles and books; after review they are published, free first and later for sale | Planned |
| Siamsil Keyboard | Zomi word completion and next-word suggestions on the phone | Planned; grows from predictive text |
| Siamsil Voice | Zomi speech to text and text to speech | Planned; grows from the Speech Data Lab |

Rules every product follows:

- **Rights first.** Each work or recording records who owns it and what Siamsil may do with it, as `data/rights.json` does for language data.
- **Training is a separate, opt-in choice.** Publishing, selling, or signing never makes anything training data by default. An author or speaker who agrees adds data Siamsil may learn from.
- **Reviewed before published**, as with lessons and language data (principle 4).
- **The language comes first.** A product starts only after the release before it ships; [ROADMAP.md](ROADMAP.md) sets the order and what each needs first.

Siamsil Sign is built for Siamsil's own needs. A public signature service is a different business, with legal rules on valid signatures, tamper-evident records, and established competitors; it is revisited only if the community asks for it.

## Deferred, not rejected

These stay in the vision and are revisited once the first pathway works:

| Item | Revisit when |
|---|---|
| More literacy domains (science, data, AI, business, media, environment, and others) | Learners in the first pathway ask for them and reviewers can keep up |
| GED / high-school equivalency preparation | Original, accurate prep content can be produced and reviewed; "GED" is a trademark, so materials must be Siamsil's own |
| Specialized AI agents (coach, assessor, course creator, career coach) | The single tutor is reliable and evaluated |
| AI course generator in a Studio | Human review capacity exceeds generation; nothing publishes unreviewed |
| Credentials and verification | Assessments are calibrated and partners will recognize them |
| Literacy profile, readiness index, passport | Assessments are calibrated (principle 3) |
| Learners under 18 and parent dashboards | Child-privacy obligations (such as COPPA) are designed and reviewed |
| Institutional platform beyond simple cohorts | Partner organizations need it |
| Siamsil Sign as a public service | The community asks for it, and valid-signature rules and tamper-evident records are designed and reviewed |
| Premium tiers, enterprise, billing | Free core learning is established. Sales of authors' work in Siamsil Docs are a separate decision, made at its second step (see ROADMAP.md) |

## The cost to plan around

The limit is **content and review**, not architecture. Every skill needs lessons, questions, and explanations, written or adapted and then checked in Zomi. Plan scope by reviewer capacity.
