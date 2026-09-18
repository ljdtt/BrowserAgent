# browser-use 与 Skyvern 调研

查询日期：2026-09-18。仅采用官方仓库、源码和 GitHub REST API；未安装或运行项目。源码链接指向查询时 main，后续可能变化。Web 抓取多数标注 today；Skyvern agent.py 为 2 days ago，前端依赖文件为 last month。

## 热度与维护

精确值由主调研线程直接读取 GitHub REST API：

| 项目 | Stars | 创建日期 | 最近 pushed_at（UTC） | 许可证 |
|---|---:|---|---|---|
| browser-use/browser-use | 115,076 | 2024-10-31 | 2026-09-15 22:49:04 | MIT |
| Skyvern-AI/skyvern | 23,024 | 2024-02-28 | 2026-09-18 03:44:31 | AGPL-3.0 |

来源：[browser-use 元数据](https://api.github.com/repos/browser-use/browser-use)、[Skyvern 元数据](https://api.github.com/repos/Skyvern-AI/skyvern)。pushed_at 是推送活动，不等于发行日期或质量证明。

## browser-use

功能：通用自然语言浏览器 Agent，Python 库支持本地或云浏览器、自定义工具、模型选择和结构化结果。CLI、托管 Agent API 与云浏览器为不同使用路径，云产品能力不能一概视为本地库能力。[仓库](https://github.com/browser-use/browser-use)

当前技术栈：Python >=3.11、asyncio、Pydantic、多家模型 SDK、cdp-use、bubus；查询时版本为 0.13.10。核心依赖没有 Playwright，不能照搬旧教程的“LangChain + Playwright”表述。[依赖声明](https://raw.githubusercontent.com/browser-use/browser-use/main/pyproject.toml)

架构：Agent 调度决策与执行；BrowserSession 通过 EventBus 和 CDPClient 管理事件与会话；DOM 服务融合 DOM tree、snapshot 和 accessibility tree，处理 iframe 并序列化可交互元素。AX 树失败时尽量保留可用 DOM。[会话源码](https://raw.githubusercontent.com/browser-use/browser-use/main/browser_use/browser/session.py)、[DOM 服务](https://raw.githubusercontent.com/browser-use/browser-use/main/browser_use/dom/service.py)

执行控制包含步数和连续失败限制、循环检测、规划配置、历史压缩、成本统计和可选 judge。源码特别注明：judge 不覆盖 Agent 自报 success，而是另存结论。[Agent 源码](https://raw.githubusercontent.com/browser-use/browser-use/main/browser_use/agent/service.py)

优势（分析）：与本项目最接近，观察、动作、会话、历史分层可借鉴，Python 便于理解。边界（分析）：完整 CDP/DOM 管线规模较大；直接用库替代自己的循环，会将项目贡献转为集成与扩展。许可证为 MIT。[许可证](https://github.com/browser-use/browser-use/blob/main/LICENSE)

## Skyvern

功能：面向业务流程的浏览器平台，提供 Playwright 兼容 SDK、工作流构建界面、自然语言动作、结构化提取、页面状态验证、表单与文件任务。官方以视觉模型和多 Agent 协作介绍系统；此处是官方设计描述，并非本次独立实测。[README](https://github.com/Skyvern-AI/skyvern)

技术栈：Python、Playwright、LiteLLM、FastAPI、SQLAlchemy；前端 React、TypeScript、Vite、Tailwind、React Flow。依赖分 local/server/cloud；local 注释说明仍是 Forge 兼容桥，尚非最小浏览器运行时。[Python 依赖](https://raw.githubusercontent.com/Skyvern-AI/skyvern/main/pyproject.toml)、[前端依赖](https://raw.githubusercontent.com/Skyvern-AI/skyvern/main/skyvern-frontend/package.json)

架构：Forge Agent 连接 Task/Step 状态、模型调用器、工作流上下文、动作解析与 ActionHandler，保存日志与 artifacts。当前代码包含多引擎和 taskv3 路径，旧架构图不能代表唯一执行路径。[Agent](https://raw.githubusercontent.com/Skyvern-AI/skyvern/main/skyvern/forge/agent.py)、[动作执行](https://raw.githubusercontent.com/Skyvern-AI/skyvern/main/skyvern/webeye/actions/handler.py)

部署：README 的 pip 路径表述默认 SQLite；Compose 明确使用 PostgreSQL、后端和 UI，并保存 artifacts、videos、har、log、downloads。不能说所有本地运行都必须 PostgreSQL。[Compose](https://raw.githubusercontent.com/Skyvern-AI/skyvern/main/docker-compose.yml)

优势（分析）：任务/工作流分离、结果 schema、独立验证、执行产物记录适合业务自动化。边界（分析）：完整平台会扩大个人项目维护范围；视觉推理的耗时与费用需实际测量。许可证为 AGPL-3.0，直接复用代码时应核对适用要求。[许可证](https://github.com/Skyvern-AI/skyvern/blob/main/LICENSE)

## 对 BrowserAgent 的裁剪建议（设计推断）

1. 保留 Qwen 模型适配器、自有 Agent 循环和 Playwright 执行器；借鉴分层，不为跟随 CDP 技术栈重写底层。
2. 观察包含 URL、正文、元素和 observation_id。元素引用绑定观察版本；页面改变或定位失效时重新观察。
3. 工具参数用 schema 校验，统一成功与错误返回；分别约束总步数、连续失败和无进展重复动作。
4. 每次运行保存状态、步骤、截图、结果、耗时和失败原因。首版 JSONL 与本地文件即可。
5. 分开 reported_success 和 verified_success；本地任务使用确定性断言，公开网页任务保留证据，不把 done 自动算成成功。
6. 先完成 DOM/文本主路径；视觉作为可测扩展，在固定任务集比较成功率、耗时和 token 后决定是否启用。

上述为适合 Python/Qwen-Agent/Playwright/Streamlit 原型的裁剪方案，并非宣称两个开源项目采用同一实现。
