# 当前 Wiki 生成问题总结

## 背景

本轮修复围绕前台/后台 Wiki 生成链路统一、引用路径规范化、默认模型选择、日志稳定性与页面 grounding 质量展开。当前已有若干底层问题得到修复，但 LiveKit Agents 重新生成后的文档内容质量仍存在明显缺陷，需要继续跟进。

## 已完成的修复

### 1. 前后台运行时核心统一
- 新增共享聊天运行时：`api/chat_runtime.py`
- 前台 HTTP / WebSocket 与后台 worker 共享核心运行时调用
- 后台不再维护独立的模型调用主链

### 2. 日志系统稳定性修复
- 收口重复 `setup_logging()` 调用，只保留主入口初始化
- 开发环境禁用 rotating file handler，避免 Windows + reload 场景下 `application.log` 文件锁冲突

### 3. 后台 one-shot 调用修复
- 修复 `run_chat_once()` 错误地沿用 `stream=True` 导致 `AsyncStream` 被当成普通 completion 解析的问题

### 4. embedding 批量默认值降低
- `api/config/embedder.json` 中 OpenAI 兼容 embedding 批量从 `500` 降到 `50`
- 目的是降低 embedding timeout 和空向量批次扩散概率

### 5. 页面 source 路径合并策略修复
- 新增 `api/page_source_merge.py`
- 页面阶段不再用 retrieval 文件全量覆盖 structure 阶段的 `relevant_files`
- 改为保留原始锚点文件并限量补充 retrieval 命中文件

### 6. 分支处理与 citation 路径规范化修复
- 新增 `api/repo_branch.py`
- 后台生成时按真实默认分支而非固定 `main` 生成 source 链接
- citation 路径中的 Windows 反斜杠已规范为正斜杠

### 7. 前端 provider/model 默认策略修复
- 新增 `src/utils/modelDefaults.js`
- 前端在 provider/model 为空时不再固定回退到 `google`
- 改为按可用环境变量动态选择默认 provider/model

### 8. 结构请求 helper 已就位
- `src/app/[owner]/[repo]/page.tsx` 内部已存在 `buildStructureRequestBody(...)`
- `src/utils/wikiRequestBodies.js` 也已建立对应 helper

## 当前仍存在的问题

### 问题 1：前端结构生成调用点仍未完全切到 helper
虽然 `buildStructureRequestBody(...)` 已存在，但 `determineWikiStructure(...)` 中旧的超长 request body 模板字符串仍残留，调用点尚未完全收敛到 helper。

影响：
- 前端结构生成链仍可能绕开新 helper 逻辑
- 后续问题定位复杂化

状态：
- 当前 `src/app/[owner]/[repo]/page.tsx` 仍有未提交改动，主要与此处重构有关

### 问题 2：重新生成的页面正文仍缺少稳定的原始项目文件路径引用
最新 LiveKit Agents 生成结果表明：
- 页首可能有 `<details>` 或少量 source 信息
- 但正文关键段落仍然没有稳定出现 `Sources: [path/to/file:line-line](...)`
- 用户感知上仍然像泛化总结，而非严格基于项目文件逐段生成

影响：
- 文档可信度不足
- 无法满足“必须结合实际项目文档生成”的要求

### 问题 3：质量门禁仍未有效阻止弱 grounded 页面写入缓存
虽然 `validate_generated_wiki_page(...)` 已做过收紧，但最新实际产物说明：
- 弱引用页面仍可能通过并写入缓存
- 需要继续核实：
  - 校验是否执行到了
  - 失败页是否仍被原始内容覆盖
  - 校验标准是否仍然不够“正文感知”

### 问题 4：embedding 超时与空向量问题仍可能持续影响内容质量
虽然已将批量从 500 降到 50，但根本问题仍可能存在：
- embedding provider timeout
- 某些批次失败后产生空向量文档
- RAG 过滤这些文档后，真实可用上下文下降

影响：
- 页面 grounding 退化
- 结构选择与正文引用质量下降

## 当前最可能的根因排序

### A. 页面校验和失败页写入策略不够严格
最值得优先继续跟进。实际结果表明：
- “看起来成功”的弱 grounded 页面仍会进入缓存

### B. 前端结构请求调用点尚未完全切换
会让前台仍夹带旧链路逻辑，增加行为不一致性。

### C. retrieval 虽不再完全覆盖 structure source files，但页面正文对 source files 的使用约束仍不足
说明 prompt 和 validator 还需要更强的正文级引用要求。

### D. embedding provider 稳定性问题仍是上游噪声源
虽然不是当前唯一根因，但会持续放大质量问题。

## 建议的下一步

1. 完成 `determineWikiStructure(...)` 到 `buildStructureRequestBody(...)` 的彻底切换
2. 增加页面校验审计日志：
   - structure filePaths
   - retrieved filePaths
   - final merged filePaths
   - content 内实际 Sources 路径
3. 强化失败页策略：
   - 对弱 grounded 页面不再写入成功内容
   - 必须明确落失败页
4. 进一步强化正文级引用校验：
   - 多个 `Sources:`
   - 多个相关源文件
   - 不能只靠 README
   - 最好要求 section 级引用
5. 若 embedding 仍频繁 timeout，再继续处理 provider 或批量策略

## 当前提交范围说明

本次准备提交的仅是 `src/app/[owner]/[repo]/page.tsx` 当前改动，以保留本轮已经落地但未提交的前端状态。

## 备注

当前文档基于已验证的本地代码、测试输出和实际生成产物总结，不代表最终问题已完全解决。核心症状“正文缺少原始项目文件引用路径”仍待继续修复。
