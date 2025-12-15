# Log

## 2025-12-15

- 增加“按浏览器隔离”的 LLM 开关：默认关闭，即使后端配置了 `OPENAI_API_KEY` 也不会自动调用付费模型。
- 后端为每个 WebSocket 连接维护 `client_settings`（`llm_enabled` / `model_alias`），仅在该连接开启时才调用 LLM；否则只返回启发式建议并标记 `reason=client_disabled_llm`。
- 实现按需付费调用接口：`POST /tables/{table_id}/ai_advice/llm`（前端点击一次 `Ask` 触发一次调用）。
- 前端新增 `LLM` 开关与 `Ask` 按钮，并将设置写入 `localStorage`（浏览器级别持久化），同时通过 WS 下发到后端生效。
- 为支持不同浏览器选择不同模型，新增 `use_model_alias(...)` 并发锁，避免并发调用串模型。
- UI：将 `LLM` 开关改为 toggle switch 风格，并将 `Ask` 改为 `Ask once`。
- UI：为 `Ask once` 增加交互反馈（loading spinner / Done / Failed），防重复点击，并加 15s 超时。
- 自检：`pytest -q`（53 passed）。
