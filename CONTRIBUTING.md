# Contributing to Siamsil

Siamsil is a community-centered Zomi language project. Contributions to software, documentation, and language resources are welcome, subject to review and applicable data rights.

## Setup and tests

Follow [README.md](README.md) to build the language database and start Docker, FastAPI, and Next.js. For backend and web checks:

```bash
python3 -m pip install -r backend/requirements-dev.txt -r ml_pipeline/requirements.txt
python3 -m unittest discover -s backend/tests -p "test_*.py"
cd frontend
npm run api:check
npm run lint
npm run typecheck
npm run build
```

If API schemas change, run `npm run api:generate` and commit the generated contracts when required.

## Language content and review

- Label machine-generated translations and candidate dictionary entries as **unverified**.
- Do not automatically publish, approve, or represent generated entries as human-reviewed.
- Follow [data rights](docs/DATA_RIGHTS.md), [generator review](docs/GENERATOR_REVIEW.md), and [evaluation guidance](docs/EVALUATION_SET.md).
- Keep raw source materials and provenance intact. Do not commit copyrighted or personally sensitive content without permission.
- Separate reviewed lexical entries from candidate output in data and UI.

## Pull requests

Submit a narrowly scoped change with a summary, tests, data provenance (if applicable), and screenshots for UI changes. Identify any changes to content quality, consent, authentication, accessibility, or API compatibility.

Report vulnerabilities privately according to [SECURITY.md](SECURITY.md).
