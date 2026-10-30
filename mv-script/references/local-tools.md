# 可选本地媒体检查

`scripts/inspect_media.py` 使用 Python 标准库。FFprobe 可用时读取本地媒体参数；FFmpeg 另行可用且有视频流时抽取有限 JPEG 帧。PCM WAV 可在无 FFprobe 时按样本读取时长。图片与文本只列清单，由宿主实际读取。

脚本不联网、不估计 BPM、不分段、不转录、不理解图像或音乐。抽样不能证明看懂画面、运镜或整片剪辑密度。没有辅助工具也可继续文字创作。

## 调用

从实际技能目录定位脚本，不假定当前工作目录是安装目录。`SKILL_DIR` 是占位符，执行前替换为实际目录，输入输出使用本轮授权位置。

```sh
python3 "SKILL_DIR/scripts/inspect_media.py" --check-tools
python3 "SKILL_DIR/scripts/inspect_media.py" "song.wav" "reference.mp4" --output "mv_project/media_inspection"
python3 "SKILL_DIR/scripts/inspect_media.py" "reference.mp4" --output "mv_project/detail_v02" --frames 10
```

`--check-tools` 只向标准输出报告能力。检查素材时必须指定 `--output`，目录须不存在或为空，拒绝覆盖旧报告。只传文件，不传目录或 URL；不递归扫描，不复制原素材。

| 约束 | 默认与硬上限 |
| --- | --- |
| 输入数量 | 最多 20 文件 |
| 每视频代表帧 | 默认 6，允许 0 至 12 |
| 帧最长边 | 768 像素，保留比例，不放大小图 |
| 全部输出预算 | 默认 32 MiB，允许 1 至 128 MiB，含报告预留 |
| 单帧上限 | 2 MiB，预算不足则停止 |
| 输入大小 | 每文件默认 4096 MiB，可降低，硬上限相同 |
| 子进程超时 | FFprobe 20 秒，FFmpeg 单帧 30 秒 |

只允许本地文件与管道协议，子进程使用参数数组，不执行 shell。临时帧在脚本自建临时目录生成，失败只清理这些临时文件。输入不写入或删除，帧与报告写到显式输出目录。

## 输出

`inspection.json` 记录逐项元数据、能力、错误与帧索引；`inventory.md` 提供可读索引。帧按输入序号命名，同名输入不会冲突。

帧记录采样目标 `requested_seconds`、可解析时的 `decoded_pts_seconds`、流起点和 `source_relative_seconds`。相对时间以源视频流起点为零。无解码时间时相对时间保持空值，请求时间只能称采样目标。

覆盖标为 `sparse_uniform_samples`，不执行切点检测。`visual_review`、`music_structure` 和 `bpm` 标为未执行。宿主必须看帧才可做风格分析，并注明实际解码时间；若只有请求时间须明确。

元数据失败、超时、超限或无工具时记录原因并继续其他输入。参数不合法时非零退出；逐项能力不足仍写报告，宿主按每项状态降级，不只依据退出码。
