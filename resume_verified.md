# BrowserAgent｜大模型浏览器自动化智能体

**技术栈：Python / Qwen-Agent / Playwright / Pydantic / Streamlit / pytest**

面向 AI 应用与 Agent 开发的浏览器自动化项目。基于 Qwen function calling 实现观察、决策、执行循环，通过 Playwright 操作真实浏览器，并用独立验证器与运行轨迹提升任务结果的可验证性和可调试性。

- 设计 9 类 Schema 校验浏览器工具，以 `snapshot_id + element_id` 绑定页面元素；页面变化后拒绝旧引用，降低模型使用过期索引导致的误操作。
- 实现包含最大步数、步骤间耗时检查、无效输出、无进展检测和协作式取消的受控 Agent 循环，将模型报告完成与规则验证结果拆分为独立状态。
- 构建 Streamlit 执行面板与后台 Worker，展示逐步工具调用、执行结果和验证状态；Worker 运行生成隔离 JSONL 轨迹，对敏感表单值脱敏并在敏感填写后停止截图。
- 搭建本地课程检索、详情与报名演示站和 15 条确定性任务集（6 条开发集、9 条保留集）；验证器分别检查页面证据与报告，脚本化 Playwright 基线 15/15 通过。
- 对比 browser-use、Stagehand、Skyvern 等开源方案，并分析 Qwen-Agent 与 LangGraph 在工具调用、状态管理和工作流控制上的取舍，形成可落地的分层架构方案。

面试时应说明：15/15 是不调用模型的脚本化回归基线，不能表述为 Qwen Agent 自主任务成功率；真实模型评测需单独运行并记录结果。
