# 来源与实现范围

本技能根据用户提供的多模态 AI MV 编剧需求书独立编写，最终名称按用户要求为 `mv-script`。

2026 年 10 月 30 日核对了 [Micro-Drama-Skills](https://github.com/zhaihao118/Micro-Drama-Skills) 的 [produce-mv 入口](https://github.com/zhaihao118/Micro-Drama-Skills/blob/main/.claude/skills/produce-mv/SKILL.md)、[视觉风格配置](https://github.com/zhaihao118/Micro-Drama-Skills/blob/main/.config/visual_styles.json) 与 [README](https://github.com/zhaihao118/Micro-Drama-Skills/blob/main/README.md)。当时 produce-mv 目录只含 `SKILL.md`，其 Git blob SHA 为 `bcdc4a7f4eb0ae5f43b0993aa4211fa3db3ed24b`。README blob SHA 为 `10f9514e816e95196d044812180cd7cdb23f248e`，风格配置 blob SHA 为 `5eac22b012cc5d83818409df2fbdd909331b5096`。这些是文件标识，不是仓库 commit SHA。

借鉴音乐段落与视觉节奏对应、角色和场景档案、风格切换与连续性记录的设计思路。入口、规范、模板和代码均重新编写，没有复制上游正文、代码、风格预设或示例歌词。

未引入固定片段时长、九宫格、绘图补全、视频任务配置与提交、全局索引或专用目录依赖。本技能独立运行。

上游 README 声明 MIT；本次检查的完整仓库树未发现独立 LICENSE、COPYING 或 NOTICE 文件，因此未补造版权年份、署名条款或许可证正文。保留来源与核对边界；以后如实际复制文件或代码，应重新核对当时许可。

本独立实现采用 MIT 许可证，完整许可见本目录的 `LICENSE`。上游项目的权利与许可不因本项目的独立实现而改变。
