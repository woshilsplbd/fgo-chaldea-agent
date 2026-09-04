# Initial FGO RAG corpus

- **Title:** Chaldea Archive authored FGO knowledge corpus
- **Source:** Five repository-authored Django templates listed below
- **Corpus status:** Phase 15C frozen initial corpus; manual review required before Dify ingestion
- **Corpus version:** `15C-initial`

This corpus is a source-preserving Markdown cleanup of the existing authored pages. It removes presentation markup but does not add external FGO facts or silently correct the source. Structured servant records remain outside this corpus and belong to the future Tool Calling boundary.

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

The following statements are retained because they are present in the authored pages, but should be reviewed before ingestion as canon, editorial, or absolute claims:

- `world_setting.md` preserves the altitude of 6000 meters, the 2015/2017 observation timeline, named plot events, the pruning-world interpretation, and the closing statement about Fate's “eternal theme”. These are presented as project-authored world-setting exposition.
- `chaldea_facilities.md` preserves institutional process and technology descriptions, character biographies, claims about hidden identities, and the “灵长类杀手” description. These are project-authored interpretations rather than independently verified records.
- `gameplay_basics.md` preserves “最多六名”, “七个章节”, the five-star 1% statement, the pool distinction, and the absolute-sounding “最终养成目标” sentence.
- `strategy_guide.md` preserves named team archetypes, the 3T goal, material-exchange priority, recommended roles, and the newcomer composition. These are advice/editorial claims, not universal guarantees.
- `combat_mechanics.md` preserves class relationships, examples, and recommendations exactly as authored, including claims whose scope may depend on game version.

## Version-sensitive claims found

The source pages contain numerical, formula-like, or current-meta claims that require explicit review rather than external correction: five-star summon probability `1%`; level `120` and skill `10/10/10` targets; three-turn farming; “highest/lowest” command-card roles; Berserker `1.5`/`2` multipliers; command-card Chain bonuses `+20%` and `+10`; skill level and material thresholds; four Ascension stages and `+10` level caps; named farming systems and exchange ordering; and specific team archetypes or class-counter statements.

## Presentation-only content excluded

The Markdown documents intentionally exclude Django template inheritance and `{% static %}` tags, hero images and image-only alt labels, Bootstrap containers/rows/columns, CSS classes and inline styles, decorative card/tag markup, navigation links, and other layout wrappers. No source paragraph, meaningful list, warning, heading, or terminology was excluded for content reasons.

## Corpus statistics

Character counts below are UTF-8 text character counts including Markdown metadata and headings. “Sections” counts level-2 and level-3 headings in each document. Duplicate findings are based on exact paragraph/list text across the five source-derived documents.

| File | Characters | Sections |
| --- | ---: | ---: |
| `world_setting.md` | 1024 | 5 |
| `chaldea_facilities.md` | 1171 | 12 |
| `gameplay_basics.md` | 735 | 5 |
| `strategy_guide.md` | 960 | 5 |
| `combat_mechanics.md` | 1944 | 17 |
| `README.md` | 5253 | 6 |
| **Total** | **11087** | **50** |

No exact duplicate knowledge paragraphs were found across the five source-derived documents. Repeated game terms (for example, class names and “从者”) are intentional terminology, not duplicated source passages.
