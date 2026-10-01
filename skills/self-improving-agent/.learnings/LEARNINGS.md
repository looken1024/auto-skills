# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20261001-001] best_practice

**Logged**: 2026-10-01T10:00:00Z
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
微头条流水线的 LLM 调用必须用 stream=True，否则 dots reasoning 模型返回空 content

### Details
`dots-studio/dots-3-note-preview:free` 是 reasoning 模型，正文在 `content` 字段，思考过程在 `reasoning` 字段，两者分开流式推送。之前 `wt_common.py` 的 `llm()` 用 `stream=False`，reasoning 吃满 token 配额导致 content 为空，上游返回 `{"error":"empty response content"}`。所有 17 个 free 模型都因此报 500。

### Fix
`wt_common.py` 的 `llm()` 改为 `stream=True`，同时收集 `content` 和 `reasoning`，content 为空时用 reasoning 兜底。同时给 reasoning 模型足够 token（`max(max_tokens, 2000)`），避免 reasoning 吃满。另外在 prompt 开头加"只输出 JSON，不要任何其他内容。不要思考过程"可以减少 reasoning 吞吐。

### Metadata
- Source: error
- Related Files: `~/.hermes/skills/toutiao-micro-publish/scripts/wt_common.py`
- Tags: llm, reasoning-model, stream, dots
- Pattern-Key: llm.reasoning-empty-content
- Recurrence-Count: 1

---

## [LRN-20261001-002] best_practice

**Logged**: 2026-10-01T10:00:00Z
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
lieflat-less-ai-tone 的 11 条规则已嵌入微头条流水线的写稿/复审/终审三个环节

### Details
用户安装了 `lieflat-less-ai-tone` skill（283 万字语料统计的去 AI 味白名单规则），要求微头条流水线全部三个审稿环节都带上这套规则。已在 `wt_generate.py` STYLE 常量、`review_weitoutiao.py` prompt、`ds_web_review.py` 复核清单第 7 项三处嵌入完整 11 条规则 + 不作为改写理由清单。

### Metadata
- Source: user_request
- Related Files: `wt_generate.py`, `review_weitoutiao.py`, `ds_web_review.py`
- Tags: ai-tone, lieflat, content-quality
- Pattern-Key: content.ai-tone-rules
- Recurrence-Count: 1

---