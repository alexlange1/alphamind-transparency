# Contributing

- Use Python 3.11+
- Create venv: `python3.11 -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r subnet/requirements.txt`
- Run tests: `pytest -q`
- Lint: `ruff check .`

## PR Guidelines
- Small, focused PRs (<300 LOC diff)
- Include tests and docs updates
- Keep behavior behind env flags if stricter in prod
