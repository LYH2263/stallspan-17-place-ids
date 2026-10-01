# StallSpan 市集摊档开间

沿街段一维 First-Fit 开间分配，挡柱不可被摊位跨越，输出分配图与放不下清单。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4700 |
| API | http://localhost:9700 |
| API 文档 | http://localhost:9700/docs |
| Postgres | localhost:5448 |

健康检查：`GET http://localhost:9700/api/health`

## 使用说明

1. 在「集日」「街段」确认开市日与可用宽度。
2. 在「摊主」「挡柱」维护需求宽度与障碍位置；摊主可改名，改名只影响之后的确认，旧运行保留旧名快照。
3. 打开「分配带」：「试摆预览」只算不写；「确认入库」才把整次运行写入库。
4. 主图点开摊位色块可查看空档序号与距左禁入沿米数；「运行抽屉」可按运行对账同一份库行。
5. 在「放不下」查看无法安置的摊位。

## 入库口径

- 正式入库的占位行（`placement_rows`）除街段名、摊主号与名称、起止米、宽度外，钉死所属柱间空档序号（`span_index`，1 起）与起点相对该空档左禁入沿的距离米（`offset_from_span_left_m`）。
- 确认时先对照当时切空结果逐行校验：字段缺失、序号越界、距柱与起止对不上即整次写入失败（422，行数不增），此类失败是数据口径错误，不会报成空隙不足。
- `POST /api/allocate/preview` 试摆（零写）、`POST /api/allocate/confirm` 确认（原子写入）、`GET /api/allocate/latest` 只读回放最近运行、`GET /api/allocate/runs` 运行目录。

## 开发与测试

```bash
docker compose exec api pytest -q
```
