# Contributing

Thanks for your interest in Aperture. A couple of ground rules keep the code
honest about the token story and easy to review.

## Local setup

```bash
git clone https://github.com/Tabarak-Cheema/Aperture.git
cd Aperture
./scripts/start.sh        # or start.bat on Windows
```

Everything runs on your machine. The only external calls go to whichever LLM
provider you configure in the Settings page — Ollama (local) by default.

## Branching

`main` is always green. Feature work happens on short-lived branches named by
intent:

| Prefix        | For                                  |
|---------------|--------------------------------------|
| `feat/`       | new user-visible capability          |
| `fix/`        | bugfix                               |
| `refactor/`   | internal restructure, no behaviour   |
| `ci/`         | pipeline / tooling                   |
| `chore/`      | docs, housekeeping                   |

Every branch lands via a PR with the PR template filled in. No direct pushes
to `main`.

## Commit messages

Conventional-commits style: `feat(compile): add T2 analytic grammar`.

Subject line ≤ 72 chars, imperative mood ("add", not "added"). Explain *why*
in the body when the reason isn't obvious from the diff.

## Reviews

* One approval required.
* `CI` + `budget` + `isolation` workflows must be green.
* Changes to the compile cascade or the LLM prompt builder need an additional
  review from a code-owner of `packages/llm_gateway/`.

## Local checks before pushing

```bash
ruff check .
pytest -q
cd apps/web && npm run build
```

## The render-path rule

Don't import `llm_gateway` from `services/query`, `services/insight` or
`apps/web`. The isolation test will fail the build if you do. If you think
you need to, you don't — add the capability to the compile path and let it
surface the output through the normal plan.
