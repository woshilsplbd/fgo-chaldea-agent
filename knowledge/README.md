# Initial FGO RAG corpus

- **Title:** Chaldea Archive authored FGO knowledge corpus
- **Source:** Five repository-authored Django templates listed below
- **Corpus status:** Phase 15C.6A curated authoritative-scope corpus; manual review still required before Dify ingestion
- **Corpus version:** `15C.6A-v1`

This corpus is a provenance-aware, source-preserving curation of the existing authored pages. It removes presentation markup, labels legacy material, and limits current-mechanics wording to the supplied official-evidence package. It does not add external FGO facts or silently rewrite the legacy source. The original frozen snapshot remains preserved in Git history at `de78204 docs: freeze initial FGO RAG corpus`.

## Authority matrix

| Document | Authority | Currentness | Intended Use |
| --- | --- | --- | --- |
| `world_setting.md` | `ARCHIVE_HISTORICAL` | Earlier project-authored story/world snapshot; not a complete 2026 story state | Historical/provenance-aware world-setting retrieval |
| `chaldea_facilities.md` | `ARCHIVE_HISTORICAL` | Earlier project-authored organization and character snapshot | Archive context, never a definitive current organization chart |
| `gameplay_basics.md` | `CURRENT_OFFICIAL` for verified basics; `ARCHIVE_EDITORIAL` for retained legacy notes | Current flow/strengthening concepts only where supplied official evidence supports them | High-level onboarding; no unsupported rates or universal targets |
| `strategy_guide.md` | `ARCHIVE_EDITORIAL` | Legacy project-authored advice; potentially version-sensitive | Clearly labeled archive strategy notes, not official/current meta |
| `combat_mechanics.md` | `CURRENT_OFFICIAL` for verified high-level mechanics; `STRUCTURED_TOOL` for exact Servant records | Current mechanics limited to the supplied official package | Concept retrieval for mechanics; deterministic Servant lookup via Tool Calling |

`CURRENT_OFFICIAL` means current mechanics supported by the supplied official Fate/Grand Order documentation. `ARCHIVE_HISTORICAL` means useful legacy story or organization material that must not be mistaken for current 2026 status. `ARCHIVE_EDITORIAL` means project-authored strategy or explanation that is neither official nor guaranteed-current. `STRUCTURED_TOOL` reserves exact Servant fields for the existing servants service/API and future Atlas-backed Tool Calling.

Unstable exact numbers, absolute progression goals, and current-meta recommendations were removed or downgraded because the supplied evidence package did not verify them for current use. They remain recoverable through the prior frozen commit and source files.

## Source register

The corpus origin is the five legacy Django templates mapped below. Current-mechanics verification for this curation used the supplied current official Fate/Grand Order evidence package, including:

- Official Starter Guide — gameplay flow
- Official Starter Guide — formation
- Official Starter Guide — battle / Command Cards
- Official Starter Guide / Servant strengthening documentation
- Official Fate/Grand Order 2026 announcements confirming the 11th Anniversary and current story-era progression

The archive and strategy sources below are project-authored material; they are not represented as official documentation.

## Source → document mapping

| Legacy source | Knowledge document |
| --- | --- |
| `aboutApp/templates/survey.html` | `world_setting.md` |
| `aboutApp/templates/honor.html` | `chaldea_facilities.md` |
| `serviceApp/templates/download.html` | `gameplay_basics.md` |
| `serviceApp/templates/platform.html` | `strategy_guide.md` |
| `scienceApp/templates/science.html` | `combat_mechanics.md` |

## Evaluation coverage

The frozen `v2/evals/rag_cases.json` references all five corpus sources. Every `knowledge_hit`, `retrieval_discrimination`, and `follow_up` case has a cited section below.

| Case ID | Knowledge document | Relevant section heading |
| --- | --- | --- |
| `rag-001` | `world_setting.md` | `人理续存保障机构 · 迦勒底` |
| `rag-002` | `world_setting.md` | `特异点 · 人理奠基` |
| `rag-003` | `chaldea_facilities.md` | `灵子转移室` |
| `rag-004` | `chaldea_facilities.md` | `机构组成` |
| `rag-005` | `gameplay_basics.md` | `游戏基础` |
| `rag-007` | `gameplay_basics.md` | `从者养成` |
| `rag-008` | `strategy_guide.md` | `周回攻略` |
| `rag-009` | `strategy_guide.md` | `高难攻略` |
| `rag-010` | `strategy_guide.md` | `编队策略` |
| `rag-011` | `combat_mechanics.md` | `三种指令卡详解` |
| `rag-012` | `combat_mechanics.md` | `宝具类型` |
| `rag-013` | `combat_mechanics.md` + `strategy_guide.md` | `灵基再临` + `周回攻略` |
| `rag-014` | `world_setting.md` | `人理修复之旅`; structured servant lookup is outside this corpus |
| `rag-015` | `strategy_guide.md` | `编队策略` |
| `rag-016` | `strategy_guide.md` | `编队策略` |

`rag-017` is intentionally out of scope for this initial RAG corpus. It requests structured servant fields and maps to the future Tool Calling boundary rather than to a knowledge document.

## Editorial review required

The following archive statements remain because they are present in the authored pages, but should be reviewed before ingestion as canon, editorial, or current claims:

- `world_setting.md` preserves the altitude of 6000 meters, the 2015/2017 observation timeline, named plot events, the pruning-world interpretation, and the closing statement about Fate's “eternal theme”. These are presented as project-authored world-setting exposition.
- `chaldea_facilities.md` preserves institutional process and technology descriptions, character biographies, claims about hidden identities, and the “灵长类杀手” description. These are project-authored interpretations rather than independently verified records.
- `gameplay_basics.md` retains a brief legacy note about summon categories, while removing the 1% rate, pool-exclusion wording, fixed party/chapter quantities, and universal final-goal sentence from the current baseline.
- `strategy_guide.md` retains named team archetypes, the 3T goal, material-exchange priority, recommended roles, and the newcomer composition as explicitly non-guaranteed archive advice.
- `combat_mechanics.md` retains high-level card/class/strengthening explanations supported by the supplied official package, while removing unsupported numeric multipliers and routing named Servant examples to `STRUCTURED_TOOL`.

## Version-sensitive claims found

The legacy source pages contained numerical, formula-like, or current-meta claims. The curation removed or downgraded the unsupported items (including the `1%` summon rate, level `120`/`10/10/10` target, “highest/lowest” card rankings, Berserker `1.5`/`2` multipliers, Chain bonuses, fixed skill thresholds, and `+10` Ascension increments). Remaining archive strategy, resource-ordering, class, and named-example material still requires review before current use.

## Presentation-only content excluded

The Markdown documents intentionally exclude Django template inheritance and `{% static %}` tags, hero images and image-only alt labels, Bootstrap containers/rows/columns, CSS classes and inline styles, decorative card/tag markup, navigation links, and other layout wrappers. Unsupported or overly absolute claims were also removed or downgraded as described above; the original wording remains recoverable from the legacy sources and the prior frozen commit.

## Corpus statistics

Character counts below are UTF-8 text character counts including Markdown metadata and headings. “Sections” counts level-2 and level-3 headings in each document. Duplicate findings are based on exact paragraph/list text across the five source-derived documents.

| File | Characters | Sections |
| --- | ---: | ---: |
| `world_setting.md` | 1469 | 5 |
| `chaldea_facilities.md` | 1488 | 12 |
| `gameplay_basics.md` | 1373 | 5 |
| `strategy_guide.md` | 1449 | 5 |
| `combat_mechanics.md` | 2607 | 18 |
| `README.md` | 8135 | 8 |
| **Total** | **16521** | **53** |

No exact duplicate knowledge paragraphs were found across the five source-derived documents. Repeated game terms (for example, class names and “从者”) are intentional terminology, not duplicated source passages.
