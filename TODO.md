# Roadmap & Tasks

All tasks and planned features have been formally migrated to [GitHub Issues](https://github.com/Thomo1318/gitCommitGenerator/issues).

Please use the issue tracker to view, claim, discuss, and track features, bugs, and enhancements.

- [ ] Change the agents prompt depending on the main code language identified in the diff

This should assist with early steering of the LLM.

---

- [ ] Opik Telemetry Pipeline for Model Training and Prompt Engineering

Look at obtaining the test data from opik, we may look at further developing the opik integration, further we can start using the data to train our own model. Additionally, we can run prompt improvements on the data via opiks prompt engineering tools.

---

- [ ] Add code examples to the documentation.

---

- [ ] Add snyk and codecov as hk hooks to scan code

```
snyk code test --org=fcd71871-87fc-4f54-b77a-74fc83e0531c
```

[Codecov](https://docs.codecov.com/docs/about-code-coverage)

---

- [ ] Look at using [axolotl](https://github.com/axolotl-ai-cloud/axolotl) to train the agent

---

- [ ] Investigate LLM Inference Runtimes for On-Device ML

Compare:

- MTPLX
- oMLX
- [lightning-mlx](https://github.com/samuelfaj/lightning-mlx),
- Rapid-MLX
- [apfel](https://github.com/Arthur-Ficial/apfel)
- [uzu](https://github.com/trymirai/uzu)
- [Miri SDK](https://platform.trymirai.com/new)
- [Miri Inference](https://trymirai.com/inference-runtime)
- [MetalRT](https://github.com/RunanywhereAI/metalrt-binaries)
- [MetalRT HF](https://huggingface.co/blog/runanywhere/metalrt-fastest-inference-apple-silicon)

---

- [ ] Dashboard for MTPLX

- Install and use [hipdash](https://github.com/daniel-farina/hipdash) a dashboard for MTPLX

---

- [ ] Determine if we should be updating the MTPLX model regularly

[MTPLX_Updates](https://huggingface.co/Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed/tree/main)

---

- [ ] Determine if tools from

[mlxetend](https://rasbt.github.io/mlxtend/USER_GUIDE_INDEX/) determine if can be of assistance.

---

- [ ] Alter the badges to be added to the README.md doc.

<div align="center">

[![GitGuardian](https://img.shields.io/github/actions/workflow/status/Thomo1318/jjConfig/ggshield.yml?label=Security&logo=gitguardian)](https://github.com/Thomo1318/jjConfig/actions/workflows/ggshield.yml)
[![Docs](https://img.shields.io/github/actions/workflow/status/Thomo1318/jjConfig/ci-docs.yml?label=Docs&logo=materialformkdocs)](https://github.com/Thomo1318/jjConfig/actions/workflows/ci-docs.yml)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
![CodeRabbit Badge](https://img.shields.io/badge/CodeRabbit-FF570A?logo=coderabbit&logoColor=fff&style=flat)

[![Jujutsu](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Thomo1318/e766526dd2d577b808dc24e114e1cd0b/raw/jj.json)](https://github.com/jj-vcs/jj)
[![Shell Script](https://img.shields.io/badge/shell_script-%23121011.svg?logo=gnu-bash&logoColor=white)]()
![TOML Badge](https://img.shields.io/badge/TOML-9C4121?logo=toml&logoColor=fff&style=flat)
![JSON Badge](https://img.shields.io/badge/JSON-000?logo=json&logoColor=fff&style=flat)

[![Version](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Thomo1318/e766526dd2d577b808dc24e114e1cd0b/raw/version.json)](https://github.com/Thomo1318/jjConfig/releases)
[![Last Commit](https://img.shields.io/github/last-commit/Thomo1318/jjConfig?color=red)](https://github.com/Thomo1318/jjConfig/commits)
[![Repo Size](https://img.shields.io/github/repo-size/Thomo1318/jjConfig)](https://github.com/Thomo1318/jjConfig)

[![repomix](https://img.shields.io/npm/v/repomix?style=flat&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cGF0aCBkPSJNMTIgMkw0IDZWMThMMTIgMjJMMjAgMThWNkwxMiAyWiIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWpvaW49InJvdW5kIiBmaWxsPSJub25lIi8+CiAgPHBhdGggZD0iTTEyIDJWMTJNMTIgMTJMMjAgNk0xMiAxMkw0IDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4=&label=repomix&color=D97D54)](https://www.npmjs.com/package/repomix)
[![DeepWiki](https://img.shields.io/badge/DeepWiki-Thomo1318%2FjjConfig-blue.svg?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAyCAYAAAAnWDnqAAAAAXNSR0IArs4c6QAAA05JREFUaEPtmUtyEzEQhtWTQyQLHNak2AB7ZnyXZMEjXMGeK/AIi+QuHrMnbChYY7MIh8g01fJoopFb0uhhEqqcbWTp06/uv1saEDv4O3n3dV60RfP947Mm9/SQc0ICFQgzfc4CYZoTPAswgSJCCUJUnAAoRHOAUOcATwbmVLWdGoH//PB8mnKqScAhsD0kYP3j/Yt5LPQe2KvcXmGvRHcDnpxfL2zOYJ1mFwrryWTz0advv1Ut4CJgf5uhDuDj5eUcAUoahrdY/56ebRWeraTjMt/00Sh3UDtjgHtQNHwcRGOC98BJEAEymycmYcWwOprTgcB6VZ5JK5TAJ+fXGLBm3FDAmn6oPPjR4rKCAoJCal2eAiQp2x0vxTPB3ALO2CRkwmDy5WohzBDwSEFKRwPbknEggCPB/imwrycgxX2NzoMCHhPkDwqYMr9tRcP5qNrMZHkVnOjRMWwLCcr8ohBVb1OMjxLwGCvjTikrsBOiA6fNyCrm8V1rP93iVPpwaE+gO0SsWmPiXB+jikdf6SizrT5qKasx5j8ABbHpFTx+vFXp9EnYQmLx02h1QTTrl6eDqxLnGjporxl3NL3agEvXdT0WmEost648sQOYAeJS9Q7bfUVoMGnjo4AZdUMQku50McDcMWcBPvr0SzbTAFDfvJqwLzgxwATnCgnp4wDl6Aa+Ax283gghmj+vj7feE2KBBRMW3FzOpLOADl0Isb5587h/U4gGvkt5v60Z1VLG8BhYjbzRwyQZemwAd6cCR5/XFWLYZRIMpX39AR0tjaGGiGzLVyhse5C9RKC6ai42ppWPKiBagOvaYk8lO7DajerabOZP46Lby5wKjw1HCRx7p9sVMOWGzb/vA1hwiWc6jm3MvQDTogQkiqIhJV0nBQBTU+3okKCFDy9WwferkHjtxib7t3xIUQtHxnIwtx4mpg26/HfwVNVDb4oI9RHmx5WGelRVlrtiw43zboCLaxv46AZeB3IlTkwouebTr1y2NjSpHz68WNFjHvupy3q8TFn3Hos2IAk4Ju5dCo8B3wP7VPr/FGaKiG+T+v+TQqIrOqMTL1VdWV1DdmcbO8KXBz6esmYWYKPwDL5b5FA1a0hwapHiom0r/cKaoqr+27/XcrS5UwSMbQAAAABJRU5ErkJggg==)](https://deepwiki.com/Thomo1318/jjConfig)
[![GitMCP](https://img.shields.io/badge/Git-MCP-blue?logo=git)](https://gitmcp.io/Thomo1318/jjConfig)

</div>

---

- [ ] Zensical Documentation Overhaul

- Remove obsolete pages such as "Agent Handoff" and "Walkthrough".
- Ensure the content of the documentation site reflects recent PRs, Issues, and architectural changes (e.g. `git-cg` tool, guided regeneration, new SOP loading logic).
- Ensure documentation formatting aligns with `git-cg` standard formatting.
- Add `CHANGELOG.md` to the top-level navigation.

---

- [ ] Configure Package Publishing

- Although the package `gitcommitgenerator` is built with `hatchling` (CLI tool `git-cg`), there is currently no pipeline for publishing to PyPI or Homebrew.
- Investigate and set up a GitHub Action workflow to automatically publish releases to PyPI upon tagging.
- Ensure the package metadata and entry points in `pyproject.toml` are correctly configured for public consumption.

---

## New Issue: ...
