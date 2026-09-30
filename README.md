# 睡眠管理Next

> [goodnight_sleep_manager](https://github.com/RaTaiHok/goodnight_sleep_manager)（作者 RaTaiHok）的 Fork，在上游 v1.1.3 基础上适配新版主程序并延续维护。
>
> Copyright (C) 2026 RaTaiHok, GPL-3.0-or-later。

让 Bot 在合适时间、并且自己确认要睡后进入临时睡眠状态，避免 Bot 半夜继续被拉起来聊天、消耗 token。

睡眠期间暂停以下链路：

- 新入站消息进入主处理链路
- 表达学习提取和写入
- Planner 响应结果和工具调用
- 睡眠后的后续出站消息

## 兼容性

| 项目 | 要求 |
| --- | --- |
| 主程序 | `>= 1.2.5`（上界 `999.999.999`，不锁小版本） |
| 插件 SDK | `>= 2.6.0`，`<= 2.99.99` |
| 第三方依赖 | 无 |
| 声明能力 | `send.text` / `llm.generate` / `config.get` |

已在 MaiBot 1.3.1 + 插件 SDK 2.8.2 上验证通过。

## 安装

```bash
cd <你的 MaiBot 目录>/plugins
git clone https://github.com/ValleyWinds/Sleep-Manager.git
```

后续更新在插件目录内 `git pull` 即可。`config.toml` 存放在插件目录内。

## 核心行为

- Bot 自己发出"我睡了""该睡了""大家晚安"等短句时，插件会判断是否进入睡眠
- 用户在允许入睡时间内催睡时，插件只记录一次待确认状态，并把上下文交给 Planner
- 只有 Bot 随后自己发出明确入睡确认，才会真正睡眠
- 用户在非入睡时间催睡时，默认会回复并拦截，不进入 Planner
- 普通聊天不会每条都调用额外模型

## 入睡判定

插件默认使用一层轻量 AI 判定器判断 Bot 是否真的在表达"自己要睡"。判定器只接受 `SLEEP / NOT_SLEEP / UNSURE`，只有 `SLEEP` 会触发入睡。

AI 判定只会在允许入睡时间内触发：

- 有待确认催睡时，判断 Bot 随后的回复
- 没有待确认催睡时，只判断 Bot 自己发出的睡眠相关短句，相关关键词可以在"AI 判定触发关键词"里用逗号分隔调整

如果希望完全交给 AI 语义判断，可以开启"AI 判定全部短句"。开启后，允许入睡时间内的所有短出站文本都会进入 AI 判定，不再要求先命中睡眠相关关键词，但模型调用次数会增加。

为了避免被诱导睡觉，插件默认只接受短句、自我入睡或群体收尾晚安。带 `@`、明显称呼别人、引用回复、或"晚安，某某"这类对个人说晚安的内容不会触发。正则规则仍保留为 AI 不可用或结果不确定时的兜底。

AI 判定模板内置在插件代码中，不依赖主程序 Prompt 目录。

## 睡眠状态

睡眠状态保存到 `data/plugins/<插件 ID>/sleep_state.json`（插件 ID 为 `valleywinds.sleep-manager`）。

重启后会恢复尚未过期的睡眠状态；预计醒来时间已过则自动清理。手动唤醒或自然到点也会清理对应作用域。

"自然到点醒来"默认开启，进入睡眠后才启动后台检查任务，不调用 LLM、不消耗 token。关闭后改为懒唤醒（有人发消息或查询时才唤醒）。

## 静默入睡

"静默入睡"默认关闭。开启后在后台检查两个计时器：

- `完全安静入睡分钟`：没有任何入站或出站消息多久后入睡
- `无参与入睡分钟`：Bot 连续多久没有参与话题后入睡

静默入睡不调用 LLM，也不会额外发送"晚安"。

相关配置：

- `启用静默入睡`：是否启用静默入睡
- `检查间隔秒`：后台检查频率
- `话题判断缓冲秒`：临近无参与入睡时，给新话题进入 Planner 判断的时间
- `提及延长缓冲` / `@ 延长缓冲`：被喊到时延长缓冲
- `睡眠中提及唤醒`：睡着后被提及或 `@` 是否自动醒来
- `Planner 动作算参与`：有效 Planner 动作是否刷新无参与计时

无参与计时只会被 Bot 出站消息或有效 Planner 动作刷新。`no_action`、`no_reply`、`no_react`、`no_plan`、`finish`、`wait`、`continue` 不算参与。

## 分群作息

全局"作息"是默认时间配置。需要某个群单独使用不同作息时，在"分群作息"里添加群号和时间配置：

- `允许入睡开始`
- `允许入睡结束`
- `目标醒来时间`
- `最短睡眠分钟`
- `最长睡眠分钟`
- `醒来随机浮动`

命中群号时，分群作息优先于全局作息。未命中时继续使用全局作息。

睡眠状态默认按作用域隔离：

- 配置了单独作息的群：使用 `group:<群号>`
- 未配置单独作息的群：默认也使用 `group:<群号>`，时间沿用全局作息
- 未配置单独作息的私聊：使用自己的聊天流作用域，时间沿用全局作息

如果想让默认聊天流共用全局睡眠状态，可以关闭"默认聊天流独立睡眠"。

## 睡醒回顾

"睡醒回顾"默认关闭。开启后，插件会在睡眠期间保存被拦截消息，并在对应作用域醒来时生成本地回顾文件。

回顾文件路径：`data/plugins/<插件 ID>/sleep_review/reports/`

回顾内容包括：

- 群号、群名、私聊用户、QQ 号、昵称或群名片
- 睡眠期间的轻量聊天记录
- 每个聊天流的简短总结和重要上下文

> **注意**：回顾文件包含完整的用户 ID、消息原文等**敏感数据**，长期保存在插件数据目录。备份或分享数据时请注意脱敏；不需要时建议定期清理 `sleep_review/` 目录。

插件不会向群聊或私聊补发历史回复。

## 命令

- `/sleep_status`：查看当前聊天流对应作用域的睡眠状态
- `/sleep_wake`：手动唤醒当前聊天流对应作用域，不解除全部聊天流睡眠
- `/sleep_wake_all`：手动唤醒全部聊天流，解除所有睡眠作用域
- `/sleep_now`：在当前作息允许入睡时记录一次管理员催睡，等待 Bot 自己确认
- `/sleep_force`：无视时间窗口，让当前作用域立即睡眠
- `/sleep_force_all`：无视时间窗口，让全部聊天流进入睡眠

`/sleep_now`、`/sleep_force` 和 `/sleep_force_all` 可以通过"允许管理入睡命令"关闭。"管理员用户 ID"留空时管理命令对所有人不可用（默认安全），需填写至少一个用户 ID 才能启用。

> **注意**：如果同时关闭"允许控制命令"和"自然到点醒来"，睡眠期间所有 `/sleep_*` 命令都会失效，只能等睡眠自然到期。建议至少保留其中一项，避免 Bot 长时间静默无法干预。

## 插件结构

```text
Sleep-Manager/
├─ _manifest.json          插件元信息
├─ plugin.py               插件入口和生命周期
├─ config_models.py        配置模型
├─ schema_i18n.py          WebUI 配置文案
├─ core_mixin.py           睡眠状态、入睡判定和后台任务核心逻辑
├─ hook_handlers.py        主程序 Hook 处理
├─ command_handlers.py     /sleep_* 命令处理
├─ confirmation_judge.py   AI 入睡确认判定
├─ context_items.py        主程序 Planner Hook 的 Context Item 构造与解析
├─ matchers.py             入睡、催睡、排除规则匹配
├─ pattern_utils.py        正则规则工具
├─ message_utils.py        消息解析工具
├─ schedule_utils.py       作息窗口和醒来时间计算
├─ state.py                运行期状态结构
├─ state_storage.py        睡眠状态持久化
├─ sleep_review.py         睡醒回顾记录和总结
├─ reply_generator.py      非入睡时间催睡回复生成
├─ defaults.py             默认规则和配置数据
├─ i18n/                   插件基础国际化文本
│  ├─ zh-CN.json
│  └─ en-US.json
├─ README.md               使用说明
└─ LICENSE                 开源许可证
```

## 致谢

基于 [RaTaiHok/goodnight_sleep_manager](https://github.com/RaTaiHok/goodnight_sleep_manager) 上游 v1.1.3 开发，感谢原作者的贡献。