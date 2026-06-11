# Artvee Gallery · Daily Inspiration Digest

> P3B 目标：从每天新增的 Artvee 作品里挑出精选，生成一份可阅读的"灵感
> 日报"——同时产出 Markdown 和静态 HTML，方便本地浏览与未来发布。

---

## 1. 什么是 Daily Digest

每跑一次 `build_artvee_daily_digest.py` 会产出：

```
digests/
├── artvee-digest-YYYY-MM-DD.md      ← Markdown 文本，可粘到 Obsidian / Notion
└── artvee-digest-YYYY-MM-DD.html    ← 静态 HTML，浏览器直接打开
web/data/digests.json                ← 滚动索引，按 date 倒序，dedupe 同日
```

内容结构：

1. **今日概览** —— 候选数 / 精选数 / 涉及分类 / 涉及艺术家 / 策略
2. **今日精选**（默认 5 张）—— 每张含：
 - 标题、艺术家、分类、source URL（链回 artvee.com）
 - 512 缩略图（相对路径）
 - 视觉分析：构图（横向/纵向/方形）+ dominant palette（Pillow 提取）
 - 用途建议（按 category 给出的海报/书籍封面/动画参考等）
 - Prompt seed：`<category> vintage artvee illustration, <title>, public domain print`
3. **今日风格总结** —— 构图分布 / 主色 / 类别分布
4. **可用于哪些项目** —— 用途计数
5. **数据来源与边界** —— 明确未触发下载、未发布公网、deterministic

## 2. 为什么先做 deterministic 本地版

| 决策 | 理由 |
|---|---|
| 不调用在线 LLM / 视觉模型 | (a) P3B 阶段目标是"骨架"，先把管道稳定下来；(b) deterministic 输出保证可重现、可测试；(c) 不引入 API 配额与延迟；(d) nightly batch 已经够复杂，不增加外部依赖 |
| Pillow 可选 | 当 Pillow 可用时提取 dominant palette（5 色）；不可用时 fallback 到 category 规则分析（提供 orientation 提示 + use cases） |
| 仅基于本地 P1 输出 | `web/data/artworks.json` + `metadata/*.json` + `thumbs/512/`，所有输入已存在；digest 只是派生 |
| 与 P3A 净化同思路 | P3A 净化 metadata_path，P3B 不复制原图、不嵌入 base64、不输出绝对路径 |

后续接入 AI 模型的方向（不在 P3B）：
- 用本地 LLM（Ollama / vLLM）扩展"prompt seed → 完整 prompt 模板"
- 用 BLIP-2 / LLaVA 给出"图像内容一句话描述"
- 用 CLIP 对作品做 embedding，再做主题聚类

## 3. 手动生成 digest

```bash
cd <project-root>

# 默认：今天日期，diverse 策略，5 张精选，候选池 20
python3 scripts/build_artvee_daily_digest.py

# 指定日期 + recent 策略
python3 scripts/build_artvee_daily_digest.py \
    --date 2026-06-11 --strategy recent

# 自定义精选数和候选池
python3 scripts/build_artvee_daily_digest.py \
    --select 8 --candidate-limit 30

# 试跑（不写文件）
python3 scripts/build_artvee_daily_digest.py --dry-run

# 自定义输出目录
python3 scripts/build_artvee_daily_digest.py --out-dir /tmp/artvee-digest
```

### 参数一览

| 参数 | 默认 | 含义 |
|---|---|---|
| `--date YYYY-MM-DD` | 今天 | 目标日期 |
| `--select N` | 5 | 精选张数 |
| `--candidate-limit N` | 20 | 候选池大小 |
| `--strategy recent\|diverse` | diverse | 选择策略 |
| `--mode local\|public` | local | 模式提示（当前仅影响 log/footer 文字） |
| `--out-dir PATH` | `digests/` | 输出目录 |
| `--base-url URL` | `.` | 为未来 public deploy 预留 |
| `--dry-run` | — | 只打印选择，不写文件 |

### 策略语义

- `recent` —— 按 `downloaded_at` 倒序取前 N 条
- `diverse` —— 按 category 轮转，每桶内按 `downloaded_at` 倒序，且尽量避免连续两张同一艺术家

### 日期 fallback 逻辑

1. 优先用 `downloaded_at` 字段精确匹配 `--date`
2. 匹配 0 张 → fallback 到"按 `downloaded_at` 倒序的前 `--candidate-limit` 张"
3. fallback 时 Markdown / HTML 顶部会显示 `⚠️ no artworks matched YYYY-MM-DD; fallback to newest-by-downloaded_at`

## 4. nightly 后自动生成

`scripts/artvee_nightly_wrapper.sh` 在 batch 模式、退出码 = 0 时会：

1. 调用 `build_artvee_gallery.py --mode local`（P1 builder）
2. **新增**：调用 `build_artvee_daily_digest.py --strategy diverse --select 5 --candidate-limit 20`

任何 digest 失败都用 `|| true` 隔离，**不会**让 wrapper 失败。 Telegram 消息会追加一行：

```
灵感: digest generated, selected=5, path=digests/artvee-digest-2026-06-11.md
```

失败时：

```
灵感: digest failed, see log (rc=...)
```

## 5. Markdown / HTML / digests.json 的关系

```
            ┌─ daily digest md/html ─┐
            │                       │
            │   digests/*.md        │  ← 人类可读，按 YYYY-MM-DD 命名
            │   digests/*.html      │  ← 静态网页，复用 web/style.css
            │                       │
web/data/digests.json ───────────────┘   ← 滚动索引 (JSON 数组)
   │
   └─ 每条 entry:
        {
          "date": "2026-06-11",
          "title": "...",
          "markdown_path": "digests/artvee-digest-2026-06-11.md",
          "html_path": "digests/artvee-digest-2026-06-11.html",
          "selected_count": 5,
          "categories": [...],
          "artists": [...],
          "strategy": "diverse",
          "created_at": "..."
        }
```

`digests.json` 是幂等更新的：
- 同日期 entry 会被替换（dedupe）
- 列表按 date 倒序，永远 newest 在最前

## 6. 如何避免发布原图和本地路径

P3B digest 在设计层面就排除了泄露：

| 防护点 | 实现 |
|---|---|
| 不复制原图 | `image_path` 字段从未被读取；只读 `thumb_256/512` |
| 不嵌入 base64 | Markdown 用 `![preview](../thumbs/512/...)`，HTML 用 `<img src="../thumbs/512/...">` |
| 不输出绝对 home 路径 | 所有路径手工构造为相对 `digests/` / `web/`；脚本内 `_safe_rel` 是 belt-and-suspenders |
| 不输出用户家目录缩写 | 同上 |
| 不输出工作区名 | 同上 |
| 缩略图为已存在的 P1 派生 | 与 `web/data/artworks.json` 引用一致 |

## 7. 后续发布到 GitHub Pages

P3B 阶段不做发布。后续路线：

1. 把 `digests/` 软链/同步到 GitHub Pages 项目的 `projects/artvee-gallery-digests/` 目录
2. HTML 已经是自包含静态；Markdown 可借助 MkDocs / pandoc 转 HTML
3. `digests.json` 可以加进 GitHub Pages 主页的 `projects/data.json`，作为新 entry：
 ```json
 {
   "title": "Artvee Daily Digests",
   "url": "/projects/artvee-gallery-digests/",
   "category": "tools",
   ...
 }
 ```

## 8. 后续接入视觉模型或 LLM

P3B 把扩展点留好了：

| 当前 | 后续 |
|---|---|
| `analyze_visual()` 返回 `prompt_seed` | 接 BLIP-2 / LLaVA 给 `caption: "..."` |
| dominant palette 用 Pillow 简单 k-means | 接 UMAP + KMeans 做更准确的主题色 |
| `use_cases` 写死在 `CATEGORY_HINTS` | 接 CLIP embedding 计算与目标场景的相似度 |
| prompt_seed 是单行字符串 | 接本地 LLM 展开成多 prompt 候选 + 模板填充 |
| 完全 deterministic | 增加 `--seed` 参数控制 LLM 温度，让输出可重现 |

但**任何后续接入都必须保持**：
- 不修改 `web/data/artworks.json`、`thumbs/`、`images/`
- 不调用任何外部服务（除非显式 `--enable-llm` flag）
- digest 失败不污染 nightly 主任务状态

— 文档结束 —