# Source Quality

Use this file whenever a result depends on external evidence.

## Source Hierarchy

| Level | Examples | Best use |
|---|---|---|
| Primary | Official docs, release notes, filings, laws, standards, papers, datasets, GitHub repos | Facts, dates, specs, legal/policy text, methods |
| Expert secondary | Research firms, reputable media, academic surveys, analyst reports, specialist blogs | Context, interpretation, market framing |
| Practitioner | Engineering blogs, case studies, implementation notes, conference talks | Real-world use, tradeoffs, failure modes |
| Community | Reddit, Hacker News, forums, social posts, reviews | Sentiment and leads, not standalone proof |
| Aggregator/SEO | Listicles, scraped summaries, AI-generated pages | Discovery only; trace claims upstream |

For key facts, prefer primary sources. For judgments, combine primary facts with independent interpretation.

## Domain Authority Pre-Judgment

Before deep-reading a page, use its domain as a rapid authority signal. This is a heuristic, not a final judgment — but it saves time by prioritizing likely-strong sources.

### Authority Tiers

| Tier | Domain signals | Default stance | Examples |
|---|---|---|---|
| **Tier 1 — Trusted** | `.gov`, `.edu`, official product domains, established research orgs, known primary sources | **Trust but verify** | `nist.gov`, `arxiv.org`, `github.com/<project>`, `who.int` |
| **Tier 2 — Neutral** | Established media, specialist publications, known analyst firms, engineering blogs from recognized companies | **Evaluate on content** | `techcrunch.com`, `stripe.com/blog`, `gartner.com` |
| **Tier 3 — Caution** | Generic blog platforms, forums, user-generated content, unknown domains, aggregator sites | **Verify before relying** | `medium.com/<unknown>`, `reddit.com`, forum posts, listicles |
| **Tier 4 — Avoid** | Known content farms, AI-generated spam sites, scraper/aggregator sites with no original content, affiliate-only pages | **Do not cite; use only for lead discovery** | SEO spam, auto-translated scrapers, "best-<product>-2026.com" |

### Domain Cross-Check

For a Tier 2 or Tier 3 source making a key claim:

1. Search `"<claim>" site:<source-domain>` when needed to verify the claim appears on the original domain
2. Search `<author name> <organization>` to verify author credentials
3. Check if the domain is the *origin* of the claim or merely restating it
4. If the claim traces back to a Tier 1 source, cite the Tier 1 source instead

## Freshness Rules

Currentness matters for:

- Product features, pricing, model capabilities, APIs
- Laws, regulations, policies, standards
- Market size, share, funding, financials
- Rankings, benchmarks, security status
- "Latest", "today", "recent", "new"

Use the actual current date. For "today" and "just released", search with month + day + year and fetch dated pages. If only older sources are available, disclose that.

Older sources can be acceptable for:

- Historical background
- Stable definitions
- Foundational academic concepts
- Long-term methodology

### Freshness Decay Model

Different topic types have different freshness half-lives. Apply the appropriate threshold when evaluating whether a source is "current enough":

| Topic type | Half-life | Max acceptable age (without flagging) | Examples |
|---|---|---|---|
| **Fast-moving** | 3 months | 6 months | AI model capabilities, SaaS pricing, crypto/Web3, startup funding, security vulnerabilities |
| **Current** | 6 months | 12 months | Product features, market share data, regulatory changes, industry rankings |
| **Moderate** | 1 year | 2 years | Enterprise software capabilities, business strategy, adoption trends, methodology |
| **Slow-moving** | 2 years | 4 years | Programming language features, hardware specs, academic curriculum, industry definitions |
| **Stable** | 5+ years | 10+ years | Mathematical concepts, physics, established laws, foundational theory |

**Decision rule**:
- If source age < half-life → use without freshness caveat
- If half-life ≤ source age < max acceptable → use but note the date
- If source age > max acceptable → flag as potentially stale; search for an update; if none exists, use with explicit staleness warning

**When the freshest available source is still stale**, state it clearly:
```markdown
The most recent source found is from 2023. For a fast-moving topic like LLM pricing, this is likely outdated. The findings below reflect the state as of 2023 and should be verified against current sources before acting.
```

## Scoring

Score sources mentally before relying on them.

| Signal | Strong | Weak |
|---|---|---|
| Authorship | Named organization/author with authority | Anonymous or unclear |
| Date | Published/updated and context fits | Undated or stale |
| Evidence | Links, data, methods, documents | Assertions only |
| Independence | Not financially tied to claim | Vendor marketing or affiliate |
| Specificity | Concrete numbers, scope, conditions | Vague superlatives |
| Corroboration | Confirmed elsewhere | Single isolated claim |

## Triangulation Rules

A key claim should have at least one of:

- One strong primary source
- Two independent reliable sources
- Primary source plus secondary source explaining implications

Continue checking when:

- Only one blog says it
- Search snippets are the only evidence
- Source is old and the topic changes quickly
- Numbers or dates differ
- The claim is very convenient for a vendor or agenda

## Conflict Handling

When sources disagree:

1. Identify the exact difference: number, date, definition, geography, product edition, methodology.
2. Compare source type and publication/update dates.
3. Prefer the source closest to the original event or dataset for direct facts.
4. If both are plausible, present both and explain why.

Use wording like:

```markdown
Sources differ because they use different scopes: Source A counts global revenue, while Source B counts U.S. unit sales. I would not compare those numbers directly.
```

### Contradiction Detection Heuristics

Actively scan for contradictions rather than passively noticing them. Common conflict patterns:

| Pattern | Signal | Action |
|---|---|---|
| **Number mismatch** | Same metric, different values (e.g., "$10B vs $15B market size") | Check scope, year, methodology; report both with explanation |
| **Date mismatch** | Same event, different dates | Prefer primary source (official announcement > news report) |
| **Version/edition drift** | Source A describes v2, Source B describes v3 | Pin the version each source references |
| **Geography gap** | Source A: "available in US"; Source B: "not available in EU" | Both may be true; state the geography scope |
| **Capability contradiction** | "Supports X" vs "Does not support X" | Check dates (feature may have been added); check editions (enterprise vs free) |
| **Attribution chain break** | Source B cites Source A, but Source A doesn't say what B claims | Flag as misattributed; cite Source A directly |

**Contradiction severity levels**:

- **Minor**: Scope/edition difference explains the discrepancy; note and move on
- **Material**: Genuine disagreement between credible sources; present both and explain your weighting
- **Critical**: Key user decision depends on resolving this; flag as unresolved and recommend direct verification

### When To Escalate

Stop and flag for the user when:
- A critical contradiction cannot be resolved from available sources
- The contradiction directly affects the user's stated decision
- All sources on one side are low-quality while the other side has only one source

## Bias And Risk Signals

Treat these as caution flags:

- No date, author, or source trail
- Marketing-heavy language with no details
- Affiliate comparison pages
- AI-generated pages with generic claims
- Statistics without methodology
- Reposted press releases presented as journalism
- Benchmark charts with missing setup
- Community posts used as proof of broad adoption

## Content Deduplication

Search results often return the same article republished across multiple domains (syndication, translation, scraping). Counting the same content as multiple sources inflates perceived evidence strength.

### Dedup Rules

Before adding a source to the evidence ledger, check:

1. **Exact match**: Same title + same author? → Same source.
2. **Near-match**: Same core content, different site? → Trace to the original; cite only the original.
3. **Translation**: Same article in a different language? → Note it exists but cite the original; the translation confirms reach, not additional evidence.
4. **Press release echo**: Multiple news sites repeating the same press release? → Cite the press release directly; news rewrites add no new facts.
5. **Syndication**: Same byline on multiple properties (e.g., a reporter's article appears on both TechCrunch and Yahoo News)? → Cite the canonical/original publication.

### Dedup Workflow

```text
For each candidate source:
  1. Extract: title, author, first 200 chars, publication date
  2. Compare against already-accepted sources
  3. If duplicate → note the repetition, do not count as independent evidence
  4. If the "duplicate" adds new data/angle → treat as a partial duplicate, cite only the unique portion
```

### Evidence Weight Correction

When synthesizing, avoid "5 sources agree on X" when those 5 sources are actually:
- 1 original research report
- 4 news articles summarizing the same report

Correct phrasing: "One research report [citation] states X; the finding was widely covered [citations for context, not evidence]."

## Citation Discipline

Inline citations should sit near the claim they support:

```markdown
The API is still in beta according to the vendor's documentation [citation:API Docs](https://example.com/docs).
```

Citations are mandatory for:

- Numbers and dates
- Prices and plans
- Feature availability and compatibility
- Legal, regulatory, medical, financial, or safety claims
- "Best", "leading", "fastest", "most popular" style claims
- Third-party opinions or sentiment summaries

## Claim Labels

Use these labels or equivalent wording when useful:

- Confirmed: directly supported by cited sources
- Likely: supported by multiple signals but not directly stated
- Unclear: evidence is insufficient, stale, unavailable, or conflicting
- Assumption: used to make a recommendation but not verified

Never convert likely/unclear/assumption into a fact for rhetorical smoothness.
