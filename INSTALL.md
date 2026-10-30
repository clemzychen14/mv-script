# MV Script 安装与使用

技能目录是 `mv-script/`。运行时只有 Markdown 指令和一个可选 Python 标准库脚本，无需 API Key 或模型下载。`validation/` 是交付验收材料，不需要安装。

## 安装

Codex 用户级目录使用 `~/.agents/skills/mv-script/`，依据 [OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills)。Claude Code 可使用 `~/.claude/skills/mv-script/`；该平台未在本次环境中实测。也可把技能目录放入项目的 `.agents/skills/`。

从本交付目录运行下面的 Python 命令。它先检查并备份同名目录，备份完整性通过逐文件 SHA256 核对后才替换；已有目录为符号链接时保留并报错，避免误改其他位置。安装不修改全局配置。

```sh
python3 install_skill.py
```

安装到 Claude Code 时运行：

```sh
python3 install_skill.py --host claude
```

也可以下载仓库源码，把其中整个 `mv-script/` 目录放入上述位置。同名目录存在时先检查与备份，不直接覆盖。Codex 通常自动发现新增技能；没有出现时重启应用后再查找。

## 调用

在支持技能提及的输入框中输入 `$mv-script` 或选择 `MV Script`。以下示例不要求每类素材齐全。

有参考视频时，默认优先参照其段落结构、剪辑节奏与动作节拍，再适配目标歌曲；可通过明确要求限定为只参考美术或某个片段。节奏判断需要实际连续证据，有限抽帧结果会保留不确定项。

```text
使用 $mv-script，参考这两段视频、这首歌和三张角色图，先如实分析素材，再给我三个原创 MV 创意方向。

使用 $mv-script，我只有歌词，先给两个不同的概念，不要写分镜。

使用 $mv-script，把第二个方向扩写成完整场次级 MV 剧本。

使用 $mv-script，把这份已确认剧本做成导演分镜，未核验的时间请标明。

使用 $mv-script，只修改第二次副歌的视觉叙事，保持其他段落和角色设定。
```

如果本轮技能列表尚未刷新，可以明确说“读取已安装 mv-script 的 SKILL.md 并执行”，或在新对话中调用。安装与格式校验不能代替宿主应用选择器的实际加载测试。

## 本地依赖与验证

Python 非创作必需。需要自动读取媒体参数或抽帧时使用 Python 3.9 及以上，FFprobe 与 FFmpeg 都是可选依赖。没有它们仍支持歌词、描述、可读图片及顺序型剧本；PCM WAV 可用标准库按样本读取时长。辅助脚本不自动估计 BPM、识别音乐结构或理解画面。

交付目录内运行 `python3 validation/test_inspect_media.py` 执行本地检查。测试会创建明确标注的合成样本；可读测试图片的创建使用已安装 Pillow，缺少时跳过，不安装任何依赖。媒体工具缺少时对应媒体检查跳过，其余降级检查仍可运行。

技能本身的 YAML、相对引用、能力与分阶段行为记录见 [验证范围](docs/validation.md)。试写结果见 [完整剧本](examples/screenplay.md) 与 [分镜示例](examples/storyboard.md)。
