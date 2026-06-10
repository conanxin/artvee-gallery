# Artvee Gallery · 数据 Schema

> 本文档描述 `web/data/artworks.json` 和 `web/data/gallery_stats.json` 的字段。
> **设计原则**：字段通用化，**不**硬编码 Artvee；未来接入 Wikimedia / Met Museum / Rijksmuseum 等只需换 builder 的源 input。

---

## 1. `web/data/artworks.json`

类型：JSON 数组，每个元素对应一张图片。**当前 740 条**。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 唯一标识，等于原图 basename（无扩展名）。例如 `Ohara_Koson_Songbird_and_Lotus_japanese-prints_standard` |
| `title` | string |   | 来源 metadata 的 title；缺则从 `index/artworks.csv` 取 |
| `artist` | string |   | 作者署名 |
| `category` | string |   | 类别：japanese-prints / book-illustrations / posters-design / botanical-charts |
| `download_variant` | string |   | 变体（standard / hd …）；缺省 `standard` |
| `tags` | string |   | `;` 分隔的标签，例如 `japanese;bird;botanical;quiet` |
| `usage_note` | string |   | 自由用途备注 |
| `source_url` | string |   | 原始页面 URL（artvee.com、wikimedia.org…） |
| `source` | string |   | 来源域名或简称（`artvee.com`、`wikimedia.org` …），用于将来多源过滤 |
| `downloaded_at` | string (ISO8601) |   | 本地下载时间，例如 `2026-04-11T21:19:51.267681` |
| `image_path` | string | ✓ | 原图路径。**local mode** = `../images/<category>/<basename>.jpg`；**public mode** = `<base-url>/images/<...>.jpg` |
| `thumb_256` | string |   | 256 缩略图路径，**始终** = `../thumbs/256/<basename>.jpg`（public 模式也保持相对，因为 thumbs 与 web/ 同级） |
| `thumb_512` | string |   | 512 缩略图路径，**始终** = `../thumbs/512/<basename>.jpg` |
| `metadata_path` | string |   | 原始 metadata JSON 路径（local/public 模式同理） |

### 示例

```json
{
  "id": "Ohara_Koson_Songbird_and_Lotus_japanese-prints_standard",
  "title": "Songbird and Lotus (1900 - 1936)",
  "artist": "Ohara Koson (Japanese, 1877-1945)",
  "category": "japanese-prints",
  "download_variant": "standard",
  "tags": "japanese;bird;botanical;quiet",
  "usage_note": "Obsidian封面测试",
  "source_url": "https://artvee.com/dl/songbird-and-lotus/",
  "source": "artvee.com",
  "downloaded_at": "2026-04-11T21:19:51.267681",
  "image_path": "../images/japanese-prints/Ohara_Koson_Songbird_and_Lotus_japanese-prints_standard.jpg",
  "thumb_256": "../thumbs/256/Ohara_Koson_Songbird_and_Lotus_japanese-prints_standard.jpg",
  "thumb_512": "../thumbs/512/Ohara_Koson_Songbird_and_Lotus_japanese-prints_standard.jpg",
  "metadata_path": "../metadata/Ohara_Koson_Songbird_and_Lotus_japanese-prints_standard.json"
}
```

### 字段兼容性约定

- `thumb_256` / `thumb_512` 缺失时：UI 回退到 `image_path`（`onerror` handler）。
- `metadata_path` 缺失时：UI 详情面板显示 "—"，不影响浏览。
- `downloaded_at` 缺失时：UI 排序时按空串处理，落到"旧"端；筛选"最近 N 天"会自然排除。

---

## 2. `web/data/gallery_stats.json`

类型：JSON 对象，描述整批数据的整体情况 + builder 本次运行的健康度。

### 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `generated_at` | string (ISO8601) | 本次 build 完成的时间（带秒精度） |
| `mode` | string | `local` 或 `public` |
| `base_url` | string | public 模式下的 CDN / 静态站根；local 模式为空串 |
| `counts.artworks` | int | 记录条数（与 `artworks.json` 长度一致） |
| `counts.categories` | int | 不同 category 数 |
| `counts.artists` | int | 不同 artist 数 |
| `counts.thumb_256_total` | int | 256 缩略图理论应有数（=artworks 数） |
| `counts.thumb_512_total` | int | 512 缩略图理论应有数 |
| `thumb_results.created` | object | 本次新生成的尺寸计数 `{ "256": N, "512": M }` |
| `thumb_results.skipped` | object | 本次跳过的尺寸计数（已存在） |
| `thumb_results.errors` | object | 本次失败的尺寸计数；非空 = 需排查 |
| `last_downloaded_at` | string | 全集中最新的 `downloaded_at` |
| `categories` | object | `{ "japanese-prints": 191, ... }` 全量分类计数 |
| `top_artists` | object | 前 15 名艺术家计数（不全量） |

### 示例

```json
{
  "generated_at": "2026-06-11T02:55:12",
  "mode": "local",
  "base_url": "",
  "counts": {
    "artworks": 740,
    "categories": 4,
    "artists": 66,
    "thumb_256_total": 740,
    "thumb_512_total": 740
  },
  "thumb_results": {
    "created": {"256": 697, "512": 697},
    "skipped": {"256": 43,  "512": 43},
    "errors":   {}
  },
  "last_downloaded_at": "2026-06-11T02:05:16.441258",
  "categories": {
    "botanical-charts": 206,
    "book-illustrations": 201,
    "japanese-prints": 191,
    "posters-design": 142
  },
  "top_artists": {
    "Utagawa Kuniyoshi (Japanese, 1797-1861)": 142,
    "...": "..."
  }
}
```

---

## 3. 与 `index/artworks.csv` 的差异

`index/artworks.csv` 是 batch 写入的"扁平行"，无缩略图路径，无 schema 校验。
`web/data/artworks.json` 是 gallery 专用的"消费型数据"，加了 thumb 路径、source、id 归一化字段。

| 维度 | index/artworks.csv | web/data/artworks.json |
|---|---|---|
| 字段数 | 9 | 13 |
| 缩略图路径 | 无 | `thumb_256` / `thumb_512` |
| `id` 字段 | 无（隐式 = source_url） | 有（= 原图 basename） |
| `source` 字段 | 无（隐式 = artvee） | 有（保留扩展） |
| 字段大小写 | CSV 原样 | 同上 |
| 写入频率 | 每晚 batch | 每晚 batch 后由 wrapper 自动调 build |
| 主要消费者 | batch.py、refill.py | web/ 前端 |

> **修改建议**：未来如果把 `index/artworks.csv` 替换成数据库表，`artworks.json` 的字段不应跟随改，而要保持"消费型"稳定。

---

## 4. 路径模式对照

| 模式 | 触发参数 | `image_path` 例子 | 何时用 |
|---|---|---|---|
| `local` | `--mode local`（默认） | `../images/japanese-prints/foo.jpg` | 本地 `python3 -m http.server` 浏览 |
| `public` | `--mode public --base-url https://cdn.example.com/artvee` | `https://cdn.example.com/artvee/images/japanese-prints/foo.jpg` | 上传到对象存储 + GitHub Pages / Cloudflare Pages 时 |

`thumb_256` / `thumb_512` **始终**是 `../thumbs/...`（相对路径），因为浏览器从 `web/index.html` 视角访问 thumbs 不需要换 base-url。如果未来 thumbs 也放 CDN，可以扩展出 `--thumbs-base-url`。
