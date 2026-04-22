# 2026-04-21-wiki-background-frontend-parity-plan

## 目标

将后台 Wiki 生成链路改造成与前台完全同源：统一 prompt、统一 RAG 注入、统一模型调用、统一 grounding 校验，避免后台刷新或生成时出现与项目无关的幻觉内容。

## 核心改造

1. 新增共享 wiki generation service，供前台 HTTP/WebSocket 和后台 worker 共同调用。
2. 将前台当前使用的 structure/page prompt 抽取为单一来源，禁止前后台双份维护。
3. 后台 worker 不再直接构建 prompt + 调模型，而是只做任务调度、状态更新、checkpoint、结果保存。
4. 去掉后台结构阶段对 `repo_files[:200]` 的截断，保证结构输入源与前台一致。
5. 强化 grounding 校验：无 `<details>`、无有效 `Sources:`、引用文件不在 repo 中时，视为失败而不是写入伪成功页面。

## 实施步骤

### 阶段 1：补测试，固定期望行为
- 结构 prompt 必须包含完整 file tree，不再静默裁剪到 200
- 页面输出校验必须要求 `<details>` 与 `Sources:`

### 阶段 2：统一 prompt 来源
- 将前台 prompt 模板迁移到 Python 共享模块
- 后续前台/后台都从共享模块获取 prompt

### 阶段 3：抽共享生成服务
- 抽出统一的 RAG + prompt + provider 调用逻辑
- HTTP/WebSocket/Worker 共同复用

### 阶段 4：切换 worker
- worker 改为调用共享生成服务
- 删除旧独立生成链

### 阶段 5：多角度校验
- 路径校验
- prompt hash 一致性
- RAG 检索文件一致性
- grounding 质量校验
- 刷新链路校验
- 大仓库回归校验

## 验收标准

- 后台不再有独立 wiki 生成链
- 背景刷新不再生成与项目无关的内容
- grounding 不合格结果不会覆盖旧缓存
- 大仓库结构阶段不再因为 200 文件截断而漂移
