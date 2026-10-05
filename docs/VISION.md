# Siamsil vision

Updated: 2026-10-05
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
- **Restructure the repository gradually**, as [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) already plans.
- **Add infrastructure when measurements require it**: Redis, vector search, analytics stores, additional subdomains.

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
| Premium tiers, enterprise, billing | Free core learning is established |

## The cost to plan around

The limit is **content and review**, not architecture. Every skill needs lessons, questions, and explanations, written or adapted and then checked in Zomi. Plan scope by reviewer capacity.
