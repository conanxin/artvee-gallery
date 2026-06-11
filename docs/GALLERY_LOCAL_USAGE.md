# Artvee Gallery · 本地使用文档

> 本阶段目标：把已下载的 700+ 张 Artvee 素材变成可搜索、可筛选、可浏览的本地图库。
> **不**触发任何新下载；所有数据来自 `index/artworks.csv` + `metadata/*.json` + `images/`。

## 1. 一句话启动

```bash
cd ~/hermes-agent/project/artvee-library
bash scripts/serve_artvee_gallery.sh        # 默认端口 8877
# 或：PORT=9000 bash scripts/serve_artvee_gallery.sh
```

打开 http://127.0.0.1:8877/web/ 即可浏览。

## Daily Digest

每日新增的精选灵感日报，deterministic 本地生成，输出 Markdown + HTML。

```bash
cd ~/hermes-agent/project/artvee-library

# 生成今日 digest（diverse 策略，5 张精选，候选池 20）
python3 scripts/build_artvee_daily_digest.py

# 试跑
python3 scripts/build_artvee_daily_digest.py --dry-run

# 输出
digests/artvee-digest-YYYY-MM-DD.md
digests/artvee-digest-YYYY-MM-DD.html
web/data/digests.json   # 滚动索引（幂等，按 date 倒序）
```

每张精选包含：标题、艺术家、分类、source URL、512 缩略图、视觉分析（构图 + dominant palette）、用途建议、prompt seed。

**自动触发**：`scripts/artvee_nightly_wrapper.sh` 在 batch 成功后会自动调用 digest 生成；失败用 `|| true` 隔离，不污染主任务状态。

详见 [`docs/GALLERY_DAILY_DIGEST.md`](./GALLERY_DAILY_DIGEST.md)。

## Public demo export

> P1 是"本机完整图库"（740 张、1.4G），P2 是"对外公开 demo"（精选 100 张、~15MB）。
> 两者职责不同：P1 给本地用，P2 给公网/分享用。

### 区别

| 维度 | P1 本地图库 | P2 public demo |
|---|---|---|
| 体积 | 1.4G 原图 + 727 thumbs × 2 尺寸 | ~15MB (100 张精选) |
| 路径 | `web/data/*.json` + `../images/...` | `data/*.json` + `./assets/thumbs/...` |
| 原图 | 保留 1.4G | **不复制**，详情页用 512 缩略图 |
| 适用 | 本机 / 团队内 | 公网 / 分享 / 嵌入 |
| UI | `web/index.html` | `dist/.../index.html`（同一份 app.js） |

### 生成 demo

```bash
cd ~/hermes-agent/project/artvee-library

# 默认：精选 100 张
python3 scripts/export_artvee_gallery_public_demo.py

# 试跑 30 张
python3 scripts/export_artvee_gallery_public_demo.py --limit 30 --dry-run

# 类别分散版
python3 scripts/export_artvee_gallery_public_demo.py --limit 100 --strategy diverse
```

### 本地预览 demo

```bash
cd dist/artvee-gallery-public-demo
python3 -m http.server 8890 --bind 127.0.0.1
# 打开 http://127.0.0.1:8890/
```

### 发布到公网

详见 [`docs/GALLERY_PUBLIC_DEMO.md`](./GALLERY_PUBLIC_DEMO.md)，含 GitHub Pages / Cloudflare Pages / 腾讯云 COS / 通用 nginx 四种部署方式。

> **不需要先跑 batch**。只要 `web/data/artworks.json` + `web/data/gallery_stats.json` 存在，浏览器就能加载。

## 2. 重建图库

```bash
# 全量（已存在缩略图自动跳过；740 张约 100 秒）
python3 scripts/build_artvee_gallery.py --mode local

# 试跑：只看前 30 条
python3 scripts/build_artvee_gallery.py --mode local --limit 30

# 未来发布到对象存储时
python3 scripts/build_artvee_gallery.py --mode public --base-url https://cdn.example.com/artvee
```

### 输出

- `web/data/artworks.json` — 740 条记录，UI 消费
- `web/data/gallery_stats.json` — 顶部统计 + 元信息
- `thumbs/256/<basename>.jpg` — 长边 ≤256 像素
- `thumbs/512/<basename>.jpg` — 长边 ≤512 像素

### 增量行为

- 已存在 `thumbs/256/<basename>.jpg` 直接跳过（按文件名判断）
- manifest / images / metadata 任何原始数据**绝不动**
- 失败单条不中断，错误计入 `gallery_stats.json` 的 `thumb_results.errors`

## 3. UI 用法

| 区域 | 功能 |
|---|---|
| 顶部统计 | 已下载 / 分类 / 艺术家 / 缩略图 / 最近下载时间 |
| 搜索框 | 匹配 title / artist / category / source_url / tags（不区分大小写） |
| 分类筛选 | 全部分类 / japanese-prints / book-illustrations / posters-design / botanical-charts |
| 艺术家筛选 | 全部艺术家 / 单选 |
| 最近筛选 | 全部 / 7 天 / 30 天 / 90 天 |
| 排序 | 最新下载（默认） / 按标题 / 按艺术家 |
| 网格卡片 | 缩略图 + 标题 + 艺术家 + 分类 + 标签 + 下载日期 |
| 详情面板 | 512 缩略图 + 全字段 metadata + 本地路径 + 源 URL |
| 关闭详情 | 点 × 或按 Esc |

## 4. 新增图片后如何更新

### 方式 A：nightly batch 之后（自动）

`scripts/artvee_nightly_wrapper.sh` 已集成：

> batch 成功（exit=0） → 自动调 `python3 scripts/build_artvee_gallery.py --mode local`
> 失败不阻塞主 batch；Telegram 多一行 `图库: updated, records=…` 或 `图库: update failed (rc=…)`

### 方式 B：手动

```bash
cd ~/hermes-agent/project/artvee-library
python3 scripts/build_artvee_gallery.py --mode local
# 增量：只补缺失的缩略图，秒级
```

## 5. 常见问题

### Q1. 打开页面，网格是空白
- 检查浏览器 Console（应该能看到 fetch 错误）
- 多半是 `web/data/artworks.json` 缺失
- 解决：`python3 scripts/build_artvee_gallery.py --mode local`

### Q2. 图片不显示 / 部分不显示
- 当前源数据中部分图片在磁盘缺失（早期 13 条 `image_path` 找不到原图）
- builder 不会为它们生成缩略图；UI 上 `card` 的 `thumb_256` 为空，`onerror` 会回退到 `image_path`（若原图也缺，则破图）
- 可执行 `python3 -c "from pathlib import Path; import csv; ... 检查实际差异"` 自行比对

### Q3. artworks.json 为空
- `index/artworks.csv` 不存在或为空
- 检查 `wc -l index/artworks.csv`（当前 740 条）

### Q4. Pillow 不存在
- builder 会输出 `ERROR: Pillow is required.`
- 安装：`~/hermes-agent/.venv/bin/pip install Pillow`
- builder 不动环境；只检测 + 报错

### Q5. 端口被占用
- 启动日志会提示：`WARNING: 端口 8877 已被占用`
- 换端口：`PORT=9000 bash scripts/serve_artvee_gallery.sh`

### Q6. 缩略图缺失但原图在
- builder 单条失败不中断；查看 stdout 的 `WARN: thumb fail ...`
- 直接重跑：`python3 scripts/build_artvee_gallery.py --mode local`（已存在的会跳过，未生成的会补）

### Q7. 想增量重建 thumbnails 但清掉旧的
- 删 `thumbs/256/*.jpg thumbs/512/*.jpg` 即可；下次 build 全量重生成

## 6. 文件结构（速查）

```
artvee-library/
├── index/artworks.csv           # 源：740 条索引
├── metadata/*.json              # 源：727 个元数据（早期 13 条 image 缺失但 metadata 还在）
├── images/<category>/*.jpg      # 源：727 张原图
│
├── scripts/
│   ├── build_artvee_gallery.py  # 新增：缩略图 + JSON 生成
│   └── serve_artvee_gallery.sh  # 新增：本地 HTTP 服务
│
├── thumbs/256/*.jpg             # 生成：256 缩略图
├── thumbs/512/*.jpg             # 生成：512 缩略图
├── web/
│   ├── index.html               # 新增
│   ├── app.js                   # 新增
│   ├── style.css                # 新增
│   └── data/
│       ├── artworks.json        # 生成：740 条记录
│       └── gallery_stats.json   # 生成：顶部统计
│
└── docs/
    ├── GALLERY_LOCAL_USAGE.md     # 本文档
    ├── GALLERY_DATA_SCHEMA.md     # 数据 schema
    └── GALLERY_PUBLISHING_PLAN.md # 未来发布计划
```

## 7. 设计取舍

- **不引入框架**（React / Vue / Tailwind），全靠原生 HTML + CSS Grid + fetch。
- **不打包**，直接 `python3 -m http.server` 就能跑。
- **数据 schema 通用**：虽然现在数据源是 Artvee，但 `source` 字段保留扩展空间，未来接入 Wikimedia / Met Museum 只需改 builder 的 input。
- **缩略图双尺寸**：256 给网格快，512 给详情清晰；512 比 256 大约 4x 字节，但 727 张才 1.x G 总盘可接受。
