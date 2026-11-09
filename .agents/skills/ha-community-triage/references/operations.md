# 操作说明

`scripts/feedback.py` 使用 Python 标准库及已登录的 `gh`、`meegle` CLI。在本 Skill 目录运行命令，用 `--help` 查看参数。

## 一次检查

1. 采集 GitHub 和飞书材料：

   ```sh
   python3 scripts/feedback.py collect --out /tmp/ha-scan.json
   ```

   脚本分页读取两个仓库的全部 Issues 和评论。`changed_issue_keys` 指出本次需要阅读的问题，`changed_source_urls` 指出新增、修改或删除的来源；已删除的评论通过保留的历史记录核对。`issues` 包含上下文，`existing` 包含飞书候选条目。

   首次处理最近 30 天更新的问题，完整历史用于理解上下文和查重。`weekly_review` 为 true 时，也检查 `tracked_issues` 对应的未结项，以本次读回的飞书状态为准。

2. 阅读变化和已有条目，为每个需要处理的问题编写草稿，并记录待补信息、已解决或重复的判断依据。
3. 预览每份草稿：

   ```sh
   python3 scripts/feedback.py publish --scan /tmp/ha-scan.json --draft /tmp/ha-draft.json
   ```

4. 核对来源、目标工作项及字段后，执行新建或追加：

   ```sh
   python3 scripts/feedback.py publish --scan /tmp/ha-scan.json --draft /tmp/ha-draft.json --apply
   ```

5. 所有问题处理完后，保存本次检查进度：

   ```sh
   python3 scripts/feedback.py finish --scan /tmp/ha-scan.json
   ```

`collect` 生成快照，`publish` 默认预览，`publish --apply` 写入飞书，`finish` 保存检查进度。采集或预览任务做到对应步骤；完整检查结束时执行 `finish`，包括没有变化的情况。

## 草稿格式

每份草稿处理一个问题。`source_key` 是问题的固定本地标识，可直接使用采集结果中的 Issue `key`；两个仓库报告同一个问题时沿用已跟踪的标识。一条 Issue 涉及多个独立问题时，与用户确定拆分方式，再为各问题分配标识。

`sources[].url` 从快照中原样取用 Issue 或评论链接。来源日期由脚本取自原帖，更新时间会单独标注。跨仓库的来源可以出现在同一份草稿中。

新建草稿示例：

```json
{
  "mode": "create",
  "source_key": "github-maginawin-ha-dali-center-issue-82",
  "title": "[待用户确认] 六键 DALI-2 面板未出现在 Home Assistant 中",
  "steps": "用户在 DALI Center 应用中发现六键面板，再查看 Home Assistant 中的设备和实体。",
  "expected": "能够在 Home Assistant 中使用面板。",
  "actual": "用户报告面板未出现。维护者已请用户核对实际使用的集成，尚未收到确认。",
  "sources": [
    {"url": "https://github.com/maginawin/ha-dali-center/issues/82", "summary": "用户报告六键面板未出现"},
    {"url": "https://github.com/maginawin/ha-dali-center/issues/82#issuecomment-6258192781", "summary": "维护者请求核对集成页面"}
  ]
}
```

追加草稿包含 `mode: "append"`、沿用的 `source_key`、查到的整数 `work_item_id`、事实进展 `progress` 和 `sources`。

追加会在「实际结果」的原有正文后增加事实进展和来源。脚本核对来源或本地映射、目标类型和项目归属，Codex 判断内容是否属于同一问题。脚本支持向唯一匹配的缺陷追加；匹配到需求或多个条目时，按 Skill 中的归并流程处理。

## 信息放在哪里

| 信息 | 位置 |
| --- | --- |
| 流程、判断要点、用户决策 | `SKILL.md` |
| 来源仓库、飞书目标、经办人、字段映射 | `config.json` |
| 原始反馈和对外讨论 | GitHub Issue 与评论 |
| 跟进事实、排期、负责人、处理状态 | 飞书工作项 |
| 检查进度、来源版本、映射、未核实写入 | `${CODEX_HOME:-$HOME/.codex}/automations/ha-community-state.json` |
| 本次快照和草稿 | `--out`、`--draft` 指定的仓库外文件 |

`--config`、`--state` 是全局参数，放在子命令前。试运行可用独立状态文件：

```sh
python3 scripts/feedback.py --state /tmp/ha-preview-state.json collect --out /tmp/ha-preview-scan.json
```

同一轮预览、写入和结束使用同一配置与状态文件。变更配置时，先核对已有映射并处理状态迁移，再用新配置采集；配置不一致的旧状态和快照会报错。

## 结果与失败处理

| 状态 | 含义 |
| --- | --- |
| `preview` | 返回待写入字段供核对 |
| `existing` | 找到相同 Issue 来源或映射，返回匹配条目 |
| `unchanged` | 目标已包含该进展和来源，本条处理完成 |
| `verified` | 单条写入并读回核对完成 |
| `checkpoint_saved` | 本地检查进度已保存 |

命令失败、分页不完整或仍有问题待判断时，保留快照和草稿，完成处理后再执行 `finish`。命令错误会显示堆栈，报告具体失败步骤。

脚本在写入前保存 `pending_writes`，写入和读回核对成功后移除。超时或核对失败时，保留这份记录，按其中的工作项 ID 和来源链接查询结果，报告「已写入但未核对」或「是否写入尚不确定」。当前通过人工核实结果、修复映射来恢复；恢复后重新采集，继续处理。执行写入或保存进度时，脚本会检查未核实写入和快照对应的检查进度，发现问题就报错。
