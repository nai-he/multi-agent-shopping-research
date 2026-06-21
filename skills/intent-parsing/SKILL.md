---
name: intent-parsing
description: Use when a user describes what they want to buy in natural language, before any product search. Extracts structured shopping intent including category, sub-category, brand, budget range, condition, specifications, preferences, exclusions, and generates optimized search keywords. Handles ambiguous queries like "苹果" (fruit vs iPhone) with explicit disambiguation notes.
metadata:
  agent: IntentParserAgent
  priority: 1
---

# Intent Parsing Skill

## Purpose

Convert unstructured natural language shopping requests into structured, machine-readable search parameters. This skill is the entry point for all shopping research — it must run before any scraping or analysis.

## When to Trigger

- User describes what they want to buy ("我想买个...", "帮我找...", "有没有...")
- User specifies ANY of: budget, brand, category, condition, specifications
- User's query is ambiguous and needs disambiguation ("苹果", "小米")
- Previous search results were irrelevant — re-parse intent with more detail

## Workflow

### Step 1: Parse Core Intent

Extract these fields from user input:
- **category**: Map to standard categories (手机/电脑/耳机/相机/鞋/自行车/服装/家具/家电/美妆/食品/图书/母婴/其他)
- **sub_category**: Narrower type (跑鞋/篮球鞋/公路车/山地车)
- **brand**: Normalize brand names (Apple→iPhone, 华为→Huawei, 小米→Xiaomi)
- **product_line**: Model/series (iPhone 15 Pro, MacBook Air M3)
- **condition**: 全新/二手/不限

### Step 2: Parse Budget

Handle ALL Chinese price expressions:
| Expression | Meaning |
|-----------|---------|
| 100以内/不超过200/200以下 | budget_max only |
| 100以上/至少150 | budget_min only |
| 100到200/一百到两百/100-200 | budget_min + budget_max |
| 两三百 | budget_min=200, budget_max=300 |
| 几百块/几百 | budget_min=100, budget_max=999 |
| 千元机/千元左右 | budget_min=800, budget_max=1500 |
| 一两千 | budget_min=1000, budget_max=2000 |
| 小几百 | budget_min=100, budget_max=400 |
| 大几百 | budget_min=600, budget_max=999 |

### Step 3: Extract Specifications

Anything the user mentions about the product:
- Size: 尺码/大小/尺寸/容量/存储 (42码, 256G, 15寸)
- Color: 颜色 (蓝色, 深空灰)
- Material: 材质 (碳纤维, 全金属)
- Features: 特性 (防水, 降噪, 快充)

### Step 4: Infer Implicit Requirements

Read between the lines:
- "冬天穿的" → preferences: ["保暖", "加厚"]
- "送女朋友" → preferences: ["高颜值", "包装好"], exclude: ["二手"]
- "学生用" → preferences: ["性价比高"]
- "办公用" → preferences: ["续航好", "轻便"]
- "打游戏" → preferences: ["高性能", "高刷"]
- "自用" + low budget → condition: "二手"

### Step 5: Detect Exclusions

Everything the user explicitly or implicitly wants to avoid:
- "不要/排除/避开/别给我推" → exclude list
- "不要山寨" "别推卡贴机" "避开拆修过的"

### Step 6: Generate Search Keywords

Produce 5-10 varied search phrases:
1. Most specific first (brand + model + spec)
2. Then broader (category + spec)
3. Include alternate phrasings (全称/简称/昵称/英文)
4. Cover different platforms' common search patterns

### Step 7: Handle Ambiguity

For ambiguous queries:
- Set `ambiguity_note` explaining the ambiguity and your resolution
- Set lower `confidence` score
- Add explicit exclude terms for the wrong interpretation
- Example: "苹果" → ambiguity_note explains assuming phone not fruit, exclude: ["水果", "食品"]

### Step 8: Output Confidence

- 0.9+: All fields clearly specified, no ambiguity
- 0.7-0.9: Most fields clear, some inference needed
- 0.5-0.7: Significant inference or ambiguity
- <0.5: Very vague input, needs user clarification

## Output Format

Always output valid JSON matching the intent schema. Never include markdown code fences or extra text — raw JSON only.

## Anti-Patterns (DO NOT DO)

- Do NOT assume "苹果" is always a phone — note the ambiguity
- Do NOT skip search_keyword generation — this is the most valuable output
- Do NOT return budget when user didn't mention price
- Do NOT guess brand if user didn't hint at one
