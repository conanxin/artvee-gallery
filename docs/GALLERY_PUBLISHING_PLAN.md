# Artvee Gallery · 线上发布计划 (P2+)

> **本阶段不真正上传到公网**。本文档只描述三种未来发布路线 + 数据流 + 边界条件。
> 触发条件：用户明确说"上线"时再按本文档执行。

---

## 0. 发布前必问

| 问题 | 影响 |
|---|---|
| 是否要发布**全部**图（740+ 张）？ | 全量图库：~1.4G 原图 + ~100M 缩略图 |
| 是否只发布**精选**（50-100 张）？ | 走 `selection.csv` 子集，不需要动 builder |
| 是否允许第三方访问 artvee.com 的原图 URL？ | artvee.com 公开 PD-Art / CC0，可以 |
| 国内访问 / 海外访问 优先哪边？ | 国内：腾讯云 COS / 阿里云 OSS；海外：Cloudflare R2 / AWS S3 / GitHub Pages |
| 是否需要登录 / 私密性？ | 当前数据全公开 (CC0 / PD-Art)，不需要登录 |

---

## 1. 三种发布模式

### 模式 A：只开源代码，不发布图片

- `web/index.html` + `app.js` + `style.css` + `docs/` 进 GitHub
- `images/`、`metadata/`、`thumbs/`、`web/data/` 全部留在本地不进 git
- 用户 clone 后跑 `python3 scripts/build_artvee_gallery.py --mode local` 即可本地浏览
- **好处**：0 成本、0 法律风险、隐私无忧
- **适用**：开发期间、demo、协作

### 模式 B：发布精选图库（50-100 张）

- 新建 `selection/curated.csv`，列出精选条目
- builder 加 `--input selection/curated.csv` 参数（未来扩展）
- 上传：原图 + thumbs 一起放到对象存储；web/ 部署到 GitHub Pages / Cloudflare Pages
- JSON 走 `--mode public --base-url https://cdn.example.com/artvee`
- **好处**：可控 + 精选质量高 + 体量小
- **适用**：博客配图库、Obsidian 主题资源、社交媒体二创素材

### 模式 C：完整图库线上化

- 把 `images/` `thumbs/` `web/data/` 全部同步到对象存储（**不是** git，是 CDN 同步）
- web/ 部署到静态站
- 数据流：本地 batch → 本地 build → `rclone sync` → 静态站读取 CDN 资源
- **好处**：完整可搜索、自动随 nightly 更新
- **适用**：个人 / 团队内部图库、长期稳定的素材资源

---

## 2. 三种模式对照

| 维度 | A 只开代码 | B 精选 | C 全量 |
|---|---|---|---|
| 原图是否上线 | ❌ | ✅ 部分 | ✅ 全部 |
| 缩略图是否上线 | ❌ | ✅ | ✅ |
| web 前端上线 | ✅ GitHub | ✅ GitHub Pages | ✅ 静态站 |
| Git 体积 | 几 KB | 几 KB（不含图） | 几 KB（不含图） |
| CDN 月度成本 (估) | 0 | $0.5-2 | $5-20 (1.4G) |
| 部署复杂度 | 低 | 中 | 中-高 |
| 自动化程度 | 手动 | 半自动 | 全自动 (cron 同步) |
| 法律风险 | 无 | 低（注明出处） | 低（CC0 / PD-Art） |

---

## 3. 模式 C 数据流 (未来推荐)

```
┌──────────────  本地  ──────────────┐         ┌──────────  远端  ──────────┐
│                                    │         │                            │
│  batch.py (nightly)                │         │   Object Storage (R2/S3/COS)│
│   ↓                                │         │   ├─ /images/...           │
│  index/artworks.csv + metadata     │         │   ├─ /thumbs/256/...       │
│   ↓                                │         │   ├─ /thumbs/512/...       │
│  build_artvee_gallery.py           │  sync   │   └─ /web/...              │
│   ↓                                │ ──────► │                            │
│  web/data/*.json                   │         │   Static Site (Pages/R2)   │
│  thumbs/                           │         │   └─ /index.html, app.js   │
│                                    │         │                            │
└────────────────────────────────────┘         └────────────────────────────┘
                                                       ↓
                                                公网访问：example.com/gallery/
```

### 关键脚本（待实现）

1. `scripts/sync_artvee_gallery_to_cdn.sh` — `rclone sync` images/ thumbs/ web/data/ 到 CDN
2. `scripts/publish_artvee_gallery.sh` — git push web/ 到 gh-pages 分支 / Cloudflare Pages
3. 全部参数化（CDN endpoint、bucket、prefix、target branch）

### 频率

- 推荐：每晚 batch 完成后 30 分钟内同步一次（让 CDN 与本地 build_artvee 结果对齐）
- 不推荐：实时同步（一次 batch 增量太小，CDN 调用浪费）

---

## 4. 法律 / 来源声明

artvee.com 上的素材**大多是 PD-Art / CC0**（来源是 Met Museum / Smithsonian / Rijksmuseum 等的扫描件）。但仍建议：

- web/ 页面底部加 "Source: artvee.com (CC0 / Public Domain)" 声明
- 每条记录的 `source_url` 直接链回 artvee 原页面
- 不删除 metadata 里的 `raw_artist` / `raw_title` / `source`
- 不在生产图上添加任何新水印

---

## 5. 未来 builder 扩展点

- `--input <csv>`：从 `selection/curated.csv` 取子集
- `--thumbs-only`：只重建缩略图，不动 JSON
- `--json-only`：只重建 JSON，不动缩略图
- `--category-filter <cat1,cat2>`：按分类过滤
- `--max-edge <N>`：自定义缩略图尺寸（默认 256 / 512）
- `--source-filter <wikimedia,met>`：未来多源数据

---

## 6. 何时再写这份文档

- 用户决定走 A / B / C 任一模式后，再写一份对应的"实操发布 runbook"
- 本文档保持"路线图"性质，避免误用为已落地

— 计划结束 —
