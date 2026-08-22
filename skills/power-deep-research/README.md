# Deep Research Agent Skill

Zero-config deep research skill for agent hosts such as Codex, Claude Code, Trae, OpenCode, and WorkBuddy.

It brings a DeerFlow-inspired research workflow into a pure native-agent skill: no custom runtime, no model configuration, no Tavily/Jina API keys required. The host agent uses its own search, fetch, browser, file, and multimodal tools; this skill supplies the research operating system.

## What It Does

- Plans research before writing
- Searches broad-to-narrow across multiple angles with **query auto-expansion** and **retrieval fallback chains**
- Fetches and reads key sources in **parallel** with **retrieval budget management**
- Extracts structured data (tables, dates, numbers, authors) from pages
- **Deduplicates content** — the same article on five sites counts as one source
- Builds an evidence ledger for important claims
- Scores source quality with **domain authority tiers** and **freshness decay models**
- Detects and escalates contradictions between sources
- Handles conflicts, stale sources, missing data, and uncertainty
- Runs a **retrieval coverage self-check** before delivering
- Produces cited briefs, comparisons, full reports, consulting-style reports, and content pre-research packages
- Supports **bilingual (Chinese + English) search** with platform-specific query strategies

## When To Use

Use this skill for tasks such as:

- "Research the latest developments in ..."
- "Compare A and B and recommend one"
- "Create a market / product / competitor / industry report"
- "Find current pricing, features, risks, or regulations"
- "Prepare evidence-backed content for a deck, article, script, or design brief"
- "Investigate a topic from multiple sources"

Do not use it for purely local code edits, text polishing with no fact checking, or stable common knowledge unless the user asks for verification.

## Research Modes

| Mode | Best for | Minimum standard |
|---|---|---|
| Quick | Single facts, definitions, small updates | 1-2 searches, 1 authoritative fetched source, citations. If source quality is low, suggest upgrading to Standard. |
| Standard | Topic overviews, product comparisons, current explanations | 3+ search angles with query auto-expansion, 3+ sources with parallel fetch, risks/unknowns, coverage self-check before delivery |
| Pro | Reports, buying advice, strategy, content pre-research | Research map, evidence ledger with dedup, source quality + freshness scoring, contradiction detection, gap escalation log, structured recommendation |
| Ultra | Broad market/industry/competitive research | Workstreams with budget allocation, batched searches/fetches, early stopping, interim synthesis, full reproducibility log, scope and confidence reporting |

See `references/research-workflow.md` for detailed checklists per mode.

## Repository Structure

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── research-workflow.md
│   ├── source-quality.md
│   └── report-template.md
└── scripts/
    └── markitdown_readable.py
```

## Files

- `SKILL.md` - main trigger, workflow, mode selection, citation rules, hard stops, and markitdown usage guidance
- `agents/openai.yaml` - UI metadata for skill lists and default invocation prompt
- `references/research-workflow.md` - detailed phases (contract → explore → map → deep dive → evidence → validate → synthesize), query auto-expansion, retrieval fallback chains, parallel fetch strategy, budget management, structured data extraction, coverage self-check, reproducibility log, and Chinese ecosystem search strategy
- `references/source-quality.md` - source hierarchy, domain authority tiers, freshness decay model, content deduplication rules, contradiction detection heuristics, conflict handling, bias signals, and claim labels
- `references/report-template.md` - output templates for briefs, comparisons, full reports, consulting reports, content pre-research, plus the Retrieval Quality Appendix (coverage assessment, evidence strength, gaps, reproducibility)
- `scripts/markitdown_readable.py` - optional readability fallback for URLs and local files

## Installation

Copy or symlink this folder into your agent host's skills directory. The exact path depends on the host:

```bash
# Codex
cp -R /path/to/DeepResearch ~/.codex/skills/deep-research-agent

# Claude Code
cp -R /path/to/DeepResearch ~/.claude/skills/deep-research-agent

# WorkBuddy / OpenCode — consult the host's skill directory convention
```

No API keys are required by the skill itself. Search and fetch capability come from the host agent.

## Optional Readability Fallback

The bundled script uses `markitdown` to convert noisy pages or local documents into clean Markdown.

```bash
python3 scripts/markitdown_readable.py "https://example.com"
python3 scripts/markitdown_readable.py ./source.pdf -o source.md
```

Install `markitdown` only if your environment does not already provide it:

```bash
pip install markitdown
```

**The script is a fallback, not required.** The skill works fully with the host agent's native fetch output. Use markitdown when pages are heavy with navigation, ads, or non-text content that native fetch struggles to clean up. If markitdown is not installed, skip it — the agent still handles interpretation, comparison, and synthesis.

## Citation Format

Inline citations:

```markdown
The product launched in May 2026 [citation:Release Notes](https://example.com/release).
```

Sources section:

```markdown
## Sources
- [Release Notes](https://example.com/release) - launch date and feature scope
- [Independent Review](https://example.com/review) - third-party limitations and benchmark context
```

## Design Principles

- Research first, generate second
- Native agent tools first, bundled scripts only as fallbacks
- Full-page evidence over search snippets
- Primary sources for direct facts
- Multiple independent sources for major judgments
- Explicit uncertainty instead of invented precision
- **Query mechanically, don't guess**: Use auto-expansion and fallback chains instead of relying on agent intuition for what to search next
- **Coverage before polish**: Run the self-check before delivering; an uncovered dimension is worse than a rough sentence
- **One source, counted once**: Deduplicate syndication, translation, and press-release echo

## Relationship To DeerFlow

This project borrows DeerFlow's strongest research ideas: mode presets, multi-step investigation, broad-to-narrow search, source validation, and structured synthesis.

It intentionally does not port DeerFlow's runtime, model provider layer, Tavily/Jina configuration, subagent executor, or sandbox system. The goal is a lightweight skill that works inside existing agent hosts with zero setup.

## Validation

The skill structure follows the standard skill directory layout used by Codex, Claude Code, and other agent hosts:

```text
.
├── SKILL.md
├── agents/
├── references/
└── scripts/
```

To validate the structure with the Codex skill creator validator:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py /path/to/DeepResearch
```

Expected result:

```text
Skill is valid!
```
