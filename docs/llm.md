# 语义质检与模型调用

## 受控边界

语义质检只接收 RAG 返回的食品规则候选；不会自主选择 Tool、创建规则或循环规划。模型输出必须是 JSON，并且每个发现都要提供候选规则 ID 与版本、输入字段、原文中逐字存在的证据片段、理由和修改建议。

系统会拒绝以下输出：非候选规则、版本不匹配、未授权字段、证据片段为空或不在原始字段中的发现。结构化输出不合法时仅尝试修复一次；第二次仍失败时返回 `structured_output_invalid` 并要求人工复核。模型调用失败时返回 `llm_failed` 并要求人工复核。

确定性 Tool Issue 始终优先：语义结论不能删除或降低 Tool Issue。若同一字段和规则出现冲突，保留 Tool Issue，并添加 `Tool/Rule/LLM 结论冲突` 人工复核原因。

## 版本与可观测性

Prompt 文件位于 `prompts/semantic_risk/1.0.0.json`，版本由文件名与 Trace 元数据记录。Trace 可记录 Prompt 版本、模型名、Token 使用量、耗时、候选规则 ID、决策、错误类别和降级信息；不得长期保存完整商品原文、完整 Prompt 或 LLM 原始输出。

默认 Provider 使用 DeepSeek 的 JSON 输出接口。真实密钥只能放在本机 `.env`，不得写入文档、提交 Git 或输出到日志。
