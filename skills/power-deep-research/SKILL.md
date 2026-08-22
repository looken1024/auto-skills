---
name: "deep-research-agent"
description: "Zero-config deep research skill for any task that needs current web research, multi-source verification, competitive/market/product analysis, literature-style synthesis, or evidence-backed content generation. Use before writing reports, strategies, decks, articles, designs, or decisions that depend on external facts. Uses the host agent's native search/fetch/browser tools first; bundled scripts are only readability fallbacks."
---

# Deep Research Agent

This skill turns the host agent into a precise deep-research operator without API keys, custom runtimes, or DeerFlow's model/tool configuration. It ports DeerFlow's strongest ideas: research before generation, broad-to-narrow search, mode presets, evidence discipline, source quality checks, and structured synthesis.

## Trigger

Use this skill when the user asks to search, investigate, research, compare, analyze, explain current information, find latest developments, prepare a report, prepare content that needs real-world facts, or make a decision using external evidence.

Do not use it for purely local code edits, text polishing with no fact checking, or stable common knowledge unless the user asks for verification.

## Operating Principles

1. Research before writing. For reports, decks, articles, strategies, comparisons, and design/content briefs, never draft first and retrofit citations.
2. Native tools first. Use the host's built-in web search, web fetch, browser, file, image, and multimodal abilities. Do not require Tavily, Jina, custom model config, or DeerFlow runtime.
3. Search is iterative. One query is only enough for a tiny fact lookup. Normal research requires multiple angles, full-page reading, gap detection, and follow-up queries. Use query auto-expansion after the first pass so follow-up searches are grounded in retrieved evidence, not intuition.
4. Evidence beats fluency. Every important factual claim needs a source, and every recommendation must be traceable to evidence or labeled as judgment.
5. Keep uncertainty visible. Separate confirmed facts, high-confidence synthesis, assumptions, conflicts, and unknowns.
6. Verify retrieval coverage before delivery. For Standard+, run a compact coverage self-check: are the dimensions that matter to the user covered with adequate sources?
7. Deduplicate evidence. The same article across five sites is one source, not five. Trace claims to their origin; count independent sources, not appearances.

## Mode Selection

Choose the smallest mode that can answer well.

| Mode | Use case | Minimum bar |
|---|---|---|
| Quick | Single fact, definition, small update | 1-2 searches, fetch 1 authoritative page, cite sources |
| Standard | Topic overview, product comparison, current explanation | 3+ search angles, 3+ sources, fetch key pages, include risks/unknowns |
| Pro | Research report, buying/strategy advice, content pre-research | Research map, evidence ledger, source triangulation, structured recommendation |
| Ultra | Broad market/industry/competitive research, many entities | Explicit workstreams, batched searches/fetches, interim synthesis, scoped final report |

If the request is broad enough that quality will suffer, ask one concise scope question. Otherwise proceed with reasonable assumptions and state them.

## Core Workflow

### 1. Frame The Question

Identify:

- User decision or output goal
- Entities, geography, time window, audience, and exclusions
- Whether the answer needs current information
- What would change the conclusion

For complex work, create a short research map before searching:

```text
Research map:
1. Official/current facts
2. Data and metrics
3. Independent analysis
4. Examples/cases
5. Risks, limits, criticism
6. Implications for the user's goal
```

### 2. Search Broad, Then Narrow

Start broad to map the landscape, then narrow by dimension. Vary query phrasing and source type.

**Query auto-expansion**: After the first broad search, extract entities, technical terms, controversy signals, and temporal markers from results. Generate a second round of queries combining the topic with extracted terms. This surfaces sub-topics the agent might not think to ask about.

Required angle set for Standard and above:

- Official or primary source
- Independent third-party source
- Data/statistics or concrete examples
- Limitations, risks, criticism, or counter-position

For time-sensitive queries, use the actual current date from the environment. "Today" needs month + day + year, not just the year.

**Retrieval fallback chain**: When a search yields nothing useful, relax the query, rewrite with synonyms, change source if the host supports it, search adjacent topics, then declare the gap. Summarize only material escalations in the final answer.

**Chinese ecosystem**: When the topic involves China or the user's context is Chinese, run bilingual searches (Chinese + English). Target platform-specific queries: WeChat articles (`site:mp.weixin.qq.com`), Zhihu (`site:zhihu.com`), government sites (`site:gov.cn`), and Chinese research reports. See `references/research-workflow.md` for the full strategy.

### 3. Fetch And Read Key Sources

Search snippets are leads, not evidence. Fetch full content for the sources that will support key claims.

**Parallel fetch**: For Standard+, identify top candidates per dimension and fetch them in parallel. Skim each for date, author, data presence, and primary-source links. Deep-read only the strongest 1-2 per dimension.

**Retrieval budget**: Allocate ~40% of searches/fetches to core facts, ~35% to independent analysis, ~25% to context. Apply early stopping: if two consecutive searches in a dimension return no new facts, move budget elsewhere.

Prioritize fetches for:

- Official docs, release notes, filings, standards, laws, papers
- Pages with numbers, dates, tables, methods, or case details
- Sources likely to contradict or qualify the emerging answer

**Structured data extraction**: When reading pages, actively extract tables, dates, numbers-with-units, and author/organization metadata. Do not treat all page content as flat text.

If native fetch returns noisy content, use `scripts/markitdown_readable.py` as a fallback for URLs or local files:

```bash
python3 scripts/markitdown_readable.py "https://example.com"
python3 scripts/markitdown_readable.py ./source.pdf -o source.md
```

If markitdown is not installed, skip this step and work with raw fetch output. Mention installation only when the missing package materially reduced extraction quality.

### 4. Build An Evidence Ledger

Before final synthesis, mentally or explicitly track:

| Claim | Source | Type | Date | Confidence | Notes |
|---|---|---|---|---|---|
| What the source supports | URL/title | primary/secondary/community | published/updated | high/med/low | conflicts, caveats |

For Pro/Ultra reports, include the evidence ledger in notes or summarize it in the final methodology.

### 5. Validate

Do not finalize until you can answer:

- Which key claims are directly sourced?
- Which claims are synthesized from multiple sources?
- Are there source conflicts, stale data, missing geography/time scope, or marketing bias?
- Did you read full pages for the strongest claims?
- Did you cover both supporting and limiting evidence?
- **Coverage check**: Are all decision-critical dimensions covered with adequate sources? (See `references/research-workflow.md` for the checklist.)
- **Dedup check**: Did you verify that "5 sources" are truly 5 independent sources, not 1 original + 4 syndications?

**Retrieval confidence**: Assign an overall confidence level before delivering:

- **High**: Strong primary or independent sources, recent data, decision-critical dimensions covered
- **Medium**: Some dimensions rely on secondary sources, minor gaps acknowledged
- **Low**: Sparse or low-quality sources, significant gaps, fast-moving topic with stale data

If evidence is weak, say so. Do not invent numbers, dates, market sizes, benchmarks, quotes, or source consensus.

### 6. Synthesize For The User's Goal

Default output order:

1. Bottom-line answer
2. Key findings with inline citations
3. Implications or recommendation
4. Risks, conflicts, and unknowns
5. Sources

For formal reports or consulting-grade outputs, read `references/report-template.md` and follow the matching template.

## Citation Rules

Use clickable inline citations for factual claims that depend on external sources:

```markdown
The product launched in May 2026 [citation:Release Notes](https://example.com/release).
```

End with a `Sources` section:

```markdown
## Sources
- [Release Notes](https://example.com/release) - launch date and feature scope
- [Independent Review](https://example.com/review) - third-party limitations and benchmark context
```

Required citations:

- Numbers, prices, dates, market size/share, rankings, laws, specs
- "Latest", "recent", "today", "newly released"
- Product capabilities, policies, compatibility, limitations
- Third-party opinions, case studies, claims about sentiment or adoption

## Reference Files

Read only what the task needs:

- `references/research-workflow.md` - detailed workflow, query playbooks, mode checklists, evidence ledger usage
- `references/source-quality.md` - source scoring, triangulation, conflict handling, freshness rules
- `references/report-template.md` - output templates for briefs, comparisons, consulting reports, timelines, and content pre-research

## Hard Stops

Stop and ask or disclose limitations when:

- No search/fetch/browser tool is available and the task depends on current external facts
- The user asks for "latest/today/current" but sources found are stale or undated
- A key claim appears in only one low-quality source
- Required data is unavailable or paywalled and cannot be verified
- The topic is high-stakes legal, medical, financial, or safety advice; use primary sources and provide careful caveats
- **Coverage gap is critical**: A dimension essential to the user's decision remains uncovered after exhausting the fallback chain
- **Contradiction is unresolved**: Two credible sources disagree on a fact the user's decision depends on, and neither can be dismissed

## Markitdown Note

This skill uses `scripts/markitdown_readable.py` as an optional readability fallback for noisy HTML pages and local documents (PDF, DOCX, etc.). The script requires the `markitdown` Python package.

If markitdown is not installed, the skill works fine without it: use the host agent's native fetch output. Only mention installation when extraction failed or the user is likely to repeat document-heavy research.

Suggested wording: `Optional: install markitdown with pip install markitdown for cleaner extraction from noisy pages and PDFs.`

## Common Failure Modes

- Answering from memory when the topic is current
- Treating search snippets as evidence
- Using only official marketing pages
- Hiding contradictions
- Over-citing trivial claims but leaving key claims unsupported
- Producing a polished report with no methodology, scope, or uncertainty
- **Duplicate overcount**: Treating the same article on 5 sites as 5 independent sources
- **Dimension neglect**: Spending all the research budget on 1-2 dimensions while leaving criticism/risks uncovered
- **Stale-data blindness**: Using outdated sources without checking freshness against the topic's decay rate
- **Single-language bias**: Searching only in English for topics with significant Chinese/international dimensions
- **No fallback escalation**: Declaring a dimension "not found" after one failed query instead of following the fallback chain
- **Skipping the coverage self-check**: Delivering a report without verifying decision-critical dimensions are covered
