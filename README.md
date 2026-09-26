# 麦麦晚安睡眠管理

> 本仓库是 [goodnight_sleep_manager](https://github.com/RaTaiHok/goodnight_sleep_manager)（作者 RaTaiHok）的Fork，在上游 v1.1.3（2026-05-17）基础上延续维护。
>
> Copyright (C) 2026 RaTaiHok，以 GPL-3.0 许可证发布。

让 Bot 在合适时间、并且自己确认要睡后进入临时睡眠状态。睡眠期间可以暂停新消息、表达学习、Planner 结果和后续出站消息，避免 Bot 半夜继续被拉起来聊天。

## 兼容性

| 项目 | 要求 |
| --- | --- |
| 主程序 `host_application` | `>= 1.0.0`，`<= 1.9.0` |
| 插件 SDK | `>= 2.4.0`，`<= 2.99.99` |
| 第三方依赖 | 无 |
| 声明能力 | `send.text` / `llm.generate` / `config.get` |

上游 v1.1.3 的清单把主程序版本上限固定在 `1.0.0`，主程序高于该版本时插件会被判定不兼容而无法加载；本仓库已将该上限放开到 `1.9.0`。

当前版本已在 **MaiBot 1.2.5 + 插件 SDK 2.8.2** 上逐项核对通过（Hook 载荷字段、配置校验、命令分发、Context Item 协议）。

## 安装

```bash
cd <你的 MaiBot 目录>/plugins
git clone https://github.com/ValleyWinds/Sleep-Manager.git goodnight_sleep_manager
```

目录名建议保持 `goodnight_sleep_manager`：插件目录名变了会重新生成 `config.toml`，已有配置无法沿用。睡眠状态等数据存放在主程序的 `data/plugins/<插件 ID>/` 下，与目录名无关。后续更新在插件目录内 `git pull` 即可。

## 核心行为

- Bot 自己发出“我睡了”“该睡了”“大家晚安”等短句时，插件会判断是否进入睡眠
- 用户在允许入睡时间内催睡时，插件只记录一次待确认状态，并把上下文交给 Planner
- 只有 Bot 随后自己发出明确入睡确认，才会真正睡眠
- 用户在非入睡时间催睡时，默认会回复并拦截，不进入 Planner
- 普通聊天不会每条都调用额外模型

睡眠期间默认会暂停：

- 新入站消息进入主处理链路
- 表达学习提取和写入
- Planner 响应结果和工具调用
- 睡眠后的后续出站消息

## 入睡判定

插件默认使用一层轻量 AI 判定器判断 Bot 是否真的在表达“自己要睡”。判定器只接受 `SLEEP / NOT_SLEEP / UNSURE`，只有 `SLEEP` 会触发入睡。

AI 判定只会在允许入睡时间内触发：

- 有待确认催睡时，判断 Bot 随后的回复
- 没有待确认催睡时，只判断 Bot 自己发出的睡眠相关短句，相关关键词可以在“AI 判定触发关键词”里用逗号分隔调整

如果希望完全交给 AI 语义判断，可以开启“AI 判定全部短句”。开启后，允许入睡时间内的所有短出站文本都会进入 AI 判定，不再要求先命中睡眠相关关键词，但模型调用次数会增加。

为了避免被诱导睡觉，插件默认只接受短句、自我入睡或群体收尾晚安。带 `@`、明显称呼别人、引用回复、或“晚安，某某”这类对个人说晚安的内容不会触发。正则规则仍保留为 AI 不可用或结果不确定时的兜底。

AI 入睡判定运行在插件的出站消息 Hook 中，不属于 Maisaka Planner 思考链，所以不会出现在 Planner HTML。需要查看判定过程时，开启“显示 AI 入睡判定日志”，日志会记录跳过原因、AI 判定开始、结果、耗时和正则兜底结果。

AI 判定模板会在插件加载时同步到主程序 Prompt 目录，文件名为 `goodnight_sleep_confirmation.prompt`。可以在 WebUI 的 Prompt 页面修改它；保存后的自定义内容会优先生效。

## 睡眠状态

睡眠状态默认保存到插件数据目录：

`data/plugins/<插件 ID>/sleep_state.json`

插件 ID 见 `_manifest.json` 的 `id` 字段（当前为 `local.goodnight-sleep-manager`）。从上游版本升级时，插件会在加载时把旧目录 `data/plugins/goodnight_sleep_manager/` 里的状态与回顾数据一次性复制过来（只复制、不删除旧文件）。

如果 MaiBot、插件 Runner 或插件本身在睡眠期间重启，插件加载时会恢复尚未过期的睡眠状态。预计醒来时间已过时会自动清理。手动 `/sleep_wake`、`/sleep_wake_all` 或自然到点唤醒也会清理对应作用域。

“自然到点醒来”默认开启。进入睡眠后才会启动后台检查任务，到达预计醒来时间后自动唤醒。这个任务不调用 LLM，不消耗 token；没有睡眠记录时会自动退出。关闭后，睡眠状态会在有人发消息、执行命令或其他链路查询时懒唤醒。

## 静默入睡

“静默入睡”默认关闭。开启后，插件会在后台检查两个计时器：

- `完全安静入睡分钟`：没有任何入站或出站消息多久后入睡
- `无参与入睡分钟`：Bot 连续多久没有参与话题后入睡

静默入睡不调用 LLM，也不会额外发送“晚安”。它只会把对应作用域切到睡眠状态。

相关配置：

- `启用静默入睡`：是否启用静默入睡
- `检查间隔秒`：后台检查频率
- `话题判断缓冲秒`：临近无参与入睡时，给新话题进入 Planner 判断的时间
- `提及延长缓冲` / `@ 延长缓冲`：被喊到时延长缓冲
- `睡眠中提及唤醒`：睡着后被提及或 `@` 是否自动醒来
- `Planner 动作算参与`：有效 Planner 动作是否刷新无参与计时

无参与计时只会被 Bot 出站消息或有效 Planner 动作刷新。`no_action`、`no_reply`、`no_react`、`no_plan`、`finish`、`wait`、`continue` 不算参与。

## 分群作息

全局“作息”是默认时间配置。需要某个群单独使用不同作息时，在“分群作息”里添加群号和时间配置：

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

因此某个群睡着后，不会影响其他群或私聊。如果想恢复旧逻辑，让默认聊天流共用全局睡眠状态，可以关闭“默认聊天流独立睡眠”。

## 睡醒回顾

“睡醒回顾”默认关闭。开启后，插件会在睡眠期间保存被拦截消息，并在对应作用域醒来时生成本地回顾文件。

回顾文件路径：

`data/plugins/<插件 ID>/sleep_review/reports/`

回顾内容包括：

- 群号、群名、私聊用户、QQ 号、昵称或群名片
- 睡眠期间的轻量聊天记录
- 每个聊天流的简短总结和重要上下文

插件不会向群聊或私聊补发历史回复。总结成本由这些配置控制：

- `单聊最大消息数`
- `单聊最大字符数`
- `单次最大聊天流`
- `单聊总结输出上限`

未启用睡醒回顾时，不记录消息，也不调用模型总结。

## 命令

- `/sleep_status`：查看当前聊天流对应作用域的睡眠状态
- `/sleep_wake`：手动唤醒当前聊天流对应作用域，不解除全部聊天流睡眠
- `/sleep_wake_all`：手动唤醒全部聊天流，解除所有睡眠作用域
- `/sleep_now`：在当前作息允许入睡时记录一次管理员催睡，等待 Bot 自己确认
- `/sleep_force`：无视时间窗口，让当前作用域立即睡眠
- `/sleep_force_all`：无视时间窗口，让全部聊天流进入睡眠

`/sleep_now`、`/sleep_force` 和 `/sleep_force_all` 可以通过“允许管理入睡命令”关闭。填写“管理员用户 ID”后，只有列表内用户能使用；留空则不限制。

## 注意事项

当前 MaiBot 的 `maisaka.planner.before_request` hook 不允许直接中止请求，所以插件在睡眠期间改用两个手段：清空 Planner 工具定义，并向请求 Items 追加一条系统指令，要求 Planner 不要回复；`maisaka.planner.after_response` 则在睡眠期间把 Planner 输出 Items 置空，丢弃回复内容与工具调用。新消息入口会被拦截，正常情况下不会再由新消息触发 Planner。

当用户在允许入睡时间内催睡时，插件不会强制 Bot 立刻睡觉。它只会提醒 Planner 当前已经落在配置窗口内，是否说晚安入睡仍由 Bot 根据上下文自己决定。

## 依赖的主程序 Hook

插件通过以下 Hook 实现拦截，全部为 `BLOCKING` 模式：

| Hook | 顺序 | 作用 |
| --- | --- | --- |
| `send_service.after_build_message` | LATE | 检测 Bot 出站短句是否表达自己要睡 |
| `send_service.before_send` | EARLY | 睡眠后拦截后续出站消息（触发入睡的那条会放行） |
| `chat.receive.before_process` | EARLY | 睡眠期间尽早拦截入站消息 |
| `chat.receive.after_process` | EARLY | 二次拦截，阻止消息进入命令与 Maisaka 主链路 |
| `expression.learn.after_extract` | EARLY | 睡眠期间暂停表达学习提取 |
| `expression.learn.before_upsert` | EARLY | 睡眠期间阻止表达学习写库 |
| `maisaka.planner.before_request` | EARLY | 睡眠期间清空工具定义，并追加“不要回复”的系统指令 Item |
| `maisaka.planner.after_response` | LATE | 睡眠期间清空 Planner 输出 Items |

`maisaka.planner.*` 两个 hook 通过序列化的 Context Items 传递请求与响应：插件只做「追加一条系统指令 Item」和「置空输出」两类操作，回带时保持 `item_schema_version` 不变。如果主程序调整该协议版本，插件会退回「只清空工具定义」的降级行为，不会导致加载失败。

## 插件结构

```text
goodnight_sleep_manager/
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
├─ prompts/                可同步到主程序 Prompt 页面的默认模板
│  └─ zh-CN/
│     └─ goodnight_sleep_confirmation.prompt
├─ i18n/                   插件基础国际化文本
│  ├─ zh-CN.json
│  └─ en-US.json
├─ README.md               使用说明
└─ LICENSE                 开源许可证
```
