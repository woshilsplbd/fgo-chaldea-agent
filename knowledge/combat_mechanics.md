# 灵基研究室

- **Title:** 灵基研究室
- **Source:** `scienceApp/templates/science.html`
- **Authority:** `CURRENT_OFFICIAL` for the supplied high-level mechanics; named Servant records are `STRUCTURED_TOOL`
- **Currentness:** Limited to the current official evidence package supplied for Phase 15C.6A
- **Corpus status:** Phase 15C.6A curated corpus; source-preserving cleanup

> **Scope note:** This document keeps current-official high-level mechanics where the evidence package supports them. Exact Servant identity/class/rarity/skill/Noble Phantasm records belong to `STRUCTURED_TOOL`, and unsupported numeric multipliers have been removed.

## 职阶体系

### 常规七职阶

当前官方入门说明支持在编队时考虑职阶克制与被克制。以下职阶名称来自 legacy 页面，作为 archive reference 保留；本文件不提供未经核验的精确伤害倍率：

- Saber（剑士）
- Archer（弓兵）
- Lancer（枪兵）
- Rider（骑兵）
- Caster（术士）
- Assassin（暗杀者）
- Berserker（狂战士）

### 特殊职阶（Extra Class）

legacy 页面还列出以下特殊职阶（Extra Class）名称。它们的具体相性和当前适用范围不在本阶段证据包内：

- Shielder（盾兵）
- Ruler（裁定者）
- Avenger（复仇者）
- Moon Cancer（月之癌）
- Alter Ego（另类）
- Foreigner（降临者）
- Pretender（伪装者）
- Beast（兽）

特殊职阶间的克制关系较为复杂；legacy 页面曾列举若干关系，但本 curated corpus 不固化未经当前官方证据支持的精确相性表。详细当前数据应查阅官方游戏说明或后续结构化来源。

### 克制循环示意

- Saber → 克制 → Lancer → 克制 → Archer → 克制 → Saber
- Rider → 克制 → Caster → 克制 → Assassin → 克制 → Rider
- 本 legacy 示意包含 Berserker 的全职阶相性说明；具体倍率已移除，避免把未经核验的数字作为当前机制。

## 宝具类型

### 单体宝具

对敌方单体造成大量伤害；legacy 页面将其与高难本、BOSS 战联系起来。具体 Servant 示例属于 `STRUCTURED_TOOL`，不在本段固化。

### 全体宝具

对敌方全体造成伤害；legacy 页面将其与周回、清杂兵联系起来。具体 Servant 示例属于 `STRUCTURED_TOOL`，不在本段固化。

### 辅助宝具

不直接攻击而是提供 Buff / 回复 / 复活等效果。具体 Servant 示例属于 `STRUCTURED_TOOL`，不在本段固化。

### 宝具等级与强化

当前官方强化说明支持：重复获得同一从者可提升宝具性能，最多五个宝具阶段；宝具也可以通过强化内容获得性能提升。未经当前官方证据支持的“倍率大幅增加”及具体强化关卡表述不作为本基线。

## 指令卡系统

### 三种指令卡详解

当前官方战斗说明支持三种指令卡及其基本关联：Quick 与暴击星/暴击行为相关，Arts 与 NP 获取相关，Buster 与较高伤害相关。官方说明还涵盖 1st Bonus、Quick Chain、Arts Chain、Buster Chain、Brave Chain / Extra Attack 和 Mighty Chain。

#### Buster 红卡

官方说明将 Buster 与较高伤害相关联，并说明 Buster Chain；本阶段不固化“最高/最低”排名或未经批准的数值奖励。

#### Arts 蓝卡

官方说明将 Arts 与 NP 获取相关联，并说明 Arts Chain；本阶段不固化未经批准的数值奖励。

#### Quick 绿卡

官方说明将 Quick 与暴击星/暴击行为相关联，并说明 Quick Chain；本阶段不固化“最高/最低”排名或未经批准的数值奖励。

### Mighty Chain

Mighty Chain 使用一张 Quick、一张 Arts 和一张 Buster，并给予相应的第一张卡加成效果。

## 技能强化

### 技能等级

当前官方强化说明支持技能强化可以提升性能，且某些技能等级能够缩短充能时间。具体等级、素材门槛和技能升级顺序不在本阶段官方证据范围内，因此不提供统一的“优先级”建议。

### 追加技能

legacy 页面曾提到追加技能（Append Skill）及其周回建议；具体技能数量、效果和优先级属于版本敏感的 Servant/系统数据，本 curated corpus 不将其作为当前官方基线。

## 灵基再临

### 再临阶段

当前官方强化说明支持灵基再临提高从者等级上限，适用时最多可进行四个阶段。legacy 页面关于每阶段固定 +10、卡面立绘和最终阶段效果的描述未纳入当前基线。

### 消耗素材

legacy 页面还列举棋子、辉石和稀有素材等消耗及活动商店来源；这些资源细节可能随版本或活动变化，保留为 `ARCHIVE_EDITORIAL` 线索而非当前官方优先级。
