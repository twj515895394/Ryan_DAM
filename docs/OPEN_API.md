# Ryan_DAM 开放接口（Open API）

供**同一局域网内的其他项目**复用 Ryan_DAM 的 AI 生图 / 图生图能力：

- **免鉴权**：仅 `/api/v1/open` 前缀开放，无需任何 Token；本应用自用的其余接口仍仅限本机 + 令牌。
- **跟随默认模型**：不传 `model_profile_id` 时，使用「模型与路由」设置中配置的默认生图 / 图生图模型。
- **默认入库**：任务成功后结果**自动入库**到「AI 生成」目录（`auto_import: false` 可关闭；生成历史始终永久保留）。

## 服务地址

| 途径 | 说明 |
|---|---|
| 本机 | `http://127.0.0.1:8765/api/v1/open` |
| 局域网其他设备 | `http://<Ryan_DAM 所在电脑 IP>:8765/api/v1/open` |
| 固定端口 | 默认 `8765`，可设环境变量 `RYAN_DAM_LAN_PORT`；端口被占用时自动回退随机端口 |
| 服务发现 | 桌面应用启动后端后写 `~/.ryan_dam/data/endpoint.json`（含 `port`、`lan_ips`、`open_base_urls`、内部 `token`），退出时删除 |

> Windows 首次启动可能在防火墙弹窗中询问是否允许，需允许专用网络访问后其他电脑才能连入。
> 设置窗口 →「外部接口」页可直接查看当前地址、默认模型并复制调用示例。

## 端点一览

| 方法 | 路径 | 职责 |
|---|---|---|
| GET | `/info` | 服务版本、可用与默认模型、自动入库目录 |
| POST | `/images/generations` | 一站式生图 / 图生图（见下） |
| GET | `/images/tasks/{task_id}` | 查询任务状态与结果 |
| GET | `/images/results/{result_id}/content` | 取回生成图片二进制（PNG） |

### POST /images/generations 请求体

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `prompt` | string | 必填 | 生成/编辑提示词 |
| `negative_prompt` | string | — | 透传给上游模型（经 `extra_params`） |
| `task_type` | `"auto"｜"image_generate"｜"image_edit"` | `"auto"` | auto：带 references 即图生图 |
| `model_profile_id` | int | — | 不传则用项目默认模型 |
| `size` | string | `1024x1024` | 如 `"1536x1024"` |
| `aspect_ratio` | string | — | 如 `"16:9"`，用于编辑画幅适配 |
| `n` | int 1–4 | `1` | 张数 |
| `seed` / `quality` | int / string | — | 透传上游 |
| `references` | array | `[]` | 每项三选一：`image_base64`（可含 dataURL 前缀）、`asset_id`（库内资产）、`history_result_id`（历史结果）；`role`: `"reference"｜"mask"` |
| `auto_import` | bool | `true` | 成功后自动入库 |
| `target_folder_id` | int | — | 入库目录，缺省「AI 生成」 |
| `wait` | bool | `false` | true 时阻塞至任务终态再返回 |
| `wait_timeout_s` | int 5–900 | `300` | wait 最长等待（超时返回当前状态，可继续轮询） |
| `request_timeout_s` | int 10–900 | `120` | 单次上游模型调用超时 |
| `extra_params` | object | — | 透传给上游接口的附加参数 |

未知字段会被直接拒绝（422），便于及早发现拼写错误。

### 响应（任务对象）

```json
{
  "task_id": "aitask_9f3c...",
  "task_type": "image_generate",
  "status": "queued | running | succeeded | failed | canceled | partial_failed",
  "progress_pct": 100,
  "prompt": "...",
  "error_code": null,
  "error_message": null,
  "created_at": "2026-10-30T12:00:00",
  "results": [
    {
      "result_id": "aires_ab12...",
      "idx": 0,
      "mime_type": "image/png",
      "width": 1024, "height": 1024, "size_bytes": 1483921,
      "content_path": "/api/v1/open/images/results/aires_ab12.../content",
      "imported_asset_id": 517
    }
  ]
}
```

`status` 终态取值：`succeeded / partial_failed / failed / canceled`。`imported_asset_id` 非空即已自动入库。

## 示例

### 文生图（等待结果）

```bash
curl -X POST http://192.168.1.10:8765/api/v1/open/images/generations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "窗边读书的白猫，电影感柔光", "size": "1024x1024", "wait": true}'
```

### 图生图（base64 参考图 + 蒙版）

```bash
curl -X POST http://192.168.1.10:8765/api/v1/open/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "把人物服装换成红色汉服",
    "references": [
      { "image_base64": "<原图 base64>", "role": "reference" },
      { "image_base64": "<蒙版 base64>", "role": "mask" }
    ]
  }'
```

### 异步提交 + 轮询 + 取图

```bash
TASK=$(curl -s -X POST http://192.168.1.10:8765/api/v1/open/images/generations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "赛博朋克雨夜街道", "n": 2}' | jq -r .task_id)

curl -s http://192.168.1.10:8765/api/v1/open/images/tasks/$TASK | jq '.status, .results'

curl -s -o out.png http://192.168.1.10:8765/api/v1/open/images/results/<result_id>/content
```

### Python 调用

```python
import base64, requests

BASE = "http://192.168.1.10:8765/api/v1/open"

task = requests.post(f"{BASE}/images/generations", json={
    "prompt": "水墨风格的远山", "wait": True, "wait_timeout_s": 300,
}, timeout=320).json()

for r in task["results"]:
    img = requests.get(BASE + r["content_path"]).content
    print(r["result_id"], r["imported_asset_id"], len(img))
```

## 错误约定

与主 API 一致：`{"error": {"code": "...", "message": "..."}}` + 对应状态码。
常见：`no_model_available`（400，未配置任何生图模型）、`missing_reference`（422，编辑任务未带参考图）、`invalid_base64`（400）、`task_not_found` / `result_not_found`（404）、`invalid_image`（400，参考图不是有效图片）。

## 边界说明

- 开放接口只做生图链路的只读/生成操作，不暴露删除、导入外部目录、设置修改等主业务接口。
- 自动入库仅新增资产记录，不改动工作台"手动入库"流程；生成历史永久保留的语义不变。
