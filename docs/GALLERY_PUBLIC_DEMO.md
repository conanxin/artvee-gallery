# Artvee Gallery · Public Demo 导出与发布

> **P2 目标**：从 P1 已构建的本地图库派生一个**精选静态 demo 包**，可用于任意静态服务器 / CDN 托管。
> **P2 不做**：不下载新图、不动原始 images/、不发布全量图库。

---

## 1. Public demo 是什么

```
dist/artvee-gallery-public-demo/
├── index.html                      ← 来自 web/index.html
├── app.js                          ← 来自 web/app.js
├── style.css                       ← 来自 web/style.css
├── data/
│   ├── artworks.json               ← 精选 N 条 (默认 100)
│   └── gallery_stats.json          ← demo 统计
└── assets/thumbs/
    ├── 256/*.jpg                   ← 精选缩略图 (256)
    └── 512/*.jpg                   ← 精选缩略图 (512)
```

- **零原图**：不复制 1.4G `images/`。
- **零元数据**：不复制 `metadata/*.json`。
- **精选缩略图**：默认 100 张 / 256 + 512 两套。
- **详情页 fallback**：点开图时直接用 512 缩略图作为"预览图"，并保留 `source_url` 链回 artvee.com 原页面。
- **总盘**：100 张 × (256 + 512) ≈ 10-20MB（实测可小可大），远小于 1.4G 全量。

## 2. 为什么不直接发布全量

| 维度 | 全量 1.4G | 精选 demo (~15MB) |
|---|---|---|
| 月度 CDN 成本 | $5-20 | $0.01-0.05 |
| 部署时间 | 几小时 | 几十秒 |
| 公网法律风险 | 引用 740 个第三方来源 | 引用 100 个，可人工审核 |
| 维护成本 | nightly 自动同步 | 每次手动 export |
| 用户体验 | 信息过载，搜索筛选慢 | 浏览/分享/嵌入更聚焦 |

Public demo 是"对外展示窗口"，全量是"本地完整资产库"。两者职责不同。

## 3. 如何生成 public demo

```bash
cd <project-root>

# 默认：最近 100 张
python3 scripts/export_artvee_gallery_public_demo.py

# 试跑 30 张
python3 scripts/export_artvee_gallery_public_demo.py --limit 30

# 按 category 分散选 100 张
python3 scripts/export_artvee_gallery_public_demo.py --limit 100 --strategy diverse

# 输出到指定目录
python3 scripts/export_artvee_gallery_public_demo.py --out-dir /tmp/demo

# 模拟运行（不写文件）
python3 scripts/export_artvee_gallery_public_demo.py --dry-run --limit 30

# 上 CDN 时改 base-url
python3 scripts/export_artvee_gallery_public_demo.py --base-url https://cdn.example.com/artvee
```

### 参数一览

| 参数 | 默认 | 含义 |
|---|---|---|
| `--limit N` | 100 | 入选记录数上限 |
| `--out-dir PATH` | `dist/artvee-gallery-public-demo` | 输出目录 |
| `--base-url URL` | `.` | 资产路径前缀。`./` 适合同站托管；`https://cdn.example.com/artvee` 适合 CDN |
| `--strategy` | `recent` | `recent`（按 downloaded_at 倒序）/ `diverse`（按 category 轮转） |
| `--dry-run` | — | 不写文件，只打计划 |

## 4. 如何本地预览

```bash
cd <project-root>/dist/artvee-gallery-public-demo
python3 -m http.server 8890 --bind 127.0.0.1
# 打开 http://127.0.0.1:8890/
```

P1 与 public demo 的 UI 是**同一份** `app.js`，区别只在于：
- P1：`/web/data/artworks.json`（路径带 `web/`）
- demo：`/data/artworks.json`（无 `web/`，因为 `index.html` 直接在 demo 根）

`fetch("data/artworks.json")` 是相对路径，浏览器从哪个 URL 加载 `index.html` 就解析到哪个目录——**因此 P1 的前端零修改即可在 demo 下工作**。

## 5. 如何发布到线上

### 5.1 GitHub Pages

适合：纯静态、流量小、海外为主、可接受一定延迟。

```bash
# 1) 在 GitHub 上建一个 repo，例如 conanxin/artvee-gallery-demo
# 2) 把 dist/artvee-gallery-public-demo/ 的内容推到 gh-pages 分支
cd <project-root>/dist/artvee-gallery-public-demo
git init
git checkout -b gh-pages
git add .
git commit -m "Initial public demo"
git remote add origin git@github.com:conanxin/artvee-gallery-demo.git
git push -f origin gh-pages
# 3) 在 GitHub 仓库 Settings → Pages → Source = gh-pages branch
# 4) 访问 https://conanxin.github.io/artvee-gallery-demo/
```

注意：不要把 `images/` `metadata/` `thumbs/` `web/` `scripts/` 任何源文件推上去。只推 `dist/artvee-gallery-public-demo/` 的内容。

### 5.2 Cloudflare Pages

适合：海外加速、零运维、自动 HTTPS、慷慨免费额度。

```bash
# 方式 A: 直接连 GitHub repo
# 在 Cloudflare Pages 后台选 conanxin/artvee-gallery-demo，分支 gh-pages，build command 留空。
# 每次 push 自动部署。

# 方式 B: 直接 wrangler
npm i -g wrangler
cd <project-root>/dist/artvee-gallery-public-demo
wrangler pages deploy . --project-name artvee-gallery-demo
```

### 5.3 腾讯云静态站 / COS

适合：国内访问、低延迟、需要 ICP 备案的域名。

```bash
# 1) 创建 COS bucket：artvee-gallery-demo-125xxxxxx  (北京/上海/广州 区域)
# 2) 开启静态网站托管：默认索引 = index.html
# 3) 用 coscli 或控制台上传
coscli cp -r <project-root>/dist/artvee-gallery-public-demo/ \
  cos://artvee-gallery-demo-125xxxxxx/ --delete
# 4) 访问 https://artvee-gallery-demo-125xxxxxx.cos-website.ap-guangzhou.myqcloud.com/
```

也可以走腾讯云 "静态网站托管" 服务（与 COS 区别：前者 HTTP 入口，后者是对象存储）。简单 demo 用 COS 静态托管即可。

### 5.4 通用 nginx / caddy

```nginx
server {
    listen 80;
    server_name gallery.example.com;
    root /var/www/artvee-gallery-demo;     # dist/artvee-gallery-public-demo 的内容
    index index.html;
    # 静态资源 cache
    location ~* \.(jpg|css|js)$ {
        expires 7d;
    }
}
```

## 6. 控制导出数量

- `--limit N`：硬上限。N 越大，体积越大，CDN 成本越高。
- 100 张是经验值（首页一屏 ~30 张、3 屏可看完）
- 若想做"超轻预览 demo"：20-30 张
- 若想做"差不多完整公开库"：500-740 张
- 若做"全量公开"：直接用 P1 + 自建 CDN（见 `GALLERY_PUBLISHING_PLAN.md` 模式 C）

## 7. 选择 recent / diverse

| 策略 | 适用场景 | 结果举例 (limit=30) |
|---|---|---|
| `recent` | "看我们最近在抓什么"、"时效性营销" | 30 张全是最新的，category 偏向当下 batch 的偏好 |
| `diverse` | "demo 第一印象"、"客户先看个大概" | 4 类大致平均分布，每类 ~7-8 张 |

`diverse` 内部算法：按 category 桶内按 `downloaded_at` 倒序，再轮转 pop；最后是稳定的"每类各几张"。

## 8. 哪些内容可以公开 / 哪些不要

### ✅ 可以公开

- `dist/artvee-gallery-public-demo/` 全部（HTML/JS/CSS/JSON/精选 thumbs）
- `scripts/export_artvee_gallery_public_demo.py`（开源）
- `scripts/build_artvee_gallery.py`（开源）
- `web/index.html` `app.js` `style.css`（开源）
- `docs/*.md`（开源）

### ❌ 不要提交 / 不要公开

- `images/` (1.4G 原图)
- `metadata/` (~3M 元数据)
- `thumbs/256/` `thumbs/512/`（源端全量缩略图，与本地图库共生）
- `inbox/` (manifest / candidates 内部数据)
- `logs/` (运行日志)
- `web/data/*.json` (源端全量 JSON)
- `dist/artvee-gallery-public-demo/assets/thumbs/`（**精选缩略图**可以发布，但**不要在 git 仓里追踪**——它们是 dist/ 生成物，导出时再生成）

> 简单规则：dist/ 默认不入 git；导出到 /tmp 或 CDN，再单独部署。

## 9. 与 P1 的关系

- P1 是**源**（读 index/ + metadata/ + images/ → 写 web/data/ + thumbs/）
- P2 是**派生**（读 P1 的输出 → 写 dist/）

```
       index/manifest/seed/    (源数据)
              ↓
    run_artvee_nightly_batch.py  (nightly 下载)
              ↓
   images/ + metadata/ + index/artworks.csv  (源)
              ↓
    build_artvee_gallery.py       (P1 builder)
              ↓
   web/data/*.json + thumbs/     (P1 派生)
              ↓
    export_artvee_gallery_public_demo.py   (P2 exporter)  ← 这次
              ↓
   dist/artvee-gallery-public-demo/        (P2 派生)
              ↓
   python3 -m http.server 8890 / 静态站 / CDN
```

每一步都是**只读上游 + 只写自己**的目录，互不污染。

— 文档结束 —
