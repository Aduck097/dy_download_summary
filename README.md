# Douyin Fetch Pipeline

[English](#douyin-fetch-pipeline) | [中文](#中文说明)

This repository contains a local MVP pipeline for:

1. downloading a Douyin user's videos with an external downloader
2. converting the downloaded media files into normalized MP3 files for ASR
3. writing a machine-readable manifest for downstream processing

The implementation follows the OpenSpec change at [openspec/changes/add-douyin-fetch-pipeline](/D:/codex/openspec/changes/add-douyin-fetch-pipeline).

## Prerequisites

- Python 3.11+
- `ffmpeg` available on `PATH`, or pass `--ffmpeg-path`
- A Douyin downloader CLI available on `PATH`, or pass `--downloader-bin`
- Valid Douyin cookies when the downloader requires them

This repository is designed to wrap an external downloader rather than reimplement Douyin crawling logic. The recommended downloader is `f2`, but the pipeline keeps the actual download command configurable because downloader flags may change across versions.

## Quick Start

1. Copy the shared example config:

```powershell
Copy-Item config.example.json config.json
```

2. Update `config.json` with the values for `douyin`, `ffmpeg`, `oss`, and `funasr` that match your environment.

3. Run the pipeline:

```powershell
python scripts/douyin_pipeline.py run --config config.json --profile-url "https://www.douyin.com/user/xxx"
```

4. Check the run output under `runs/<timestamp-slug>/`.

## Downloader Template

The pipeline substitutes placeholders into a command template before launching the downloader.

Supported placeholders:

- `{profile_url}`
- `{sec_user_id}`
- `{cookie}`
- `{cookie_file}`
- `{run_dir}`
- `{videos_dir}`

Example template shape:

`config.json` now uses one shared structure for the whole project. The downloader command lives at `douyin.download_template`.

Use the exact `f2` command line syntax that matches the version installed on your machine.

## Output Layout

Each run writes to `runs/<timestamp>-<slug>/`:

- `videos/`: downloaded video files
- `audio/`: converted MP3 files
- `manifest.json`: structured metadata for the run

## Example

```powershell
python scripts/douyin_pipeline.py run `
  --config config.json `
  --profile-url "https://www.douyin.com/user/MS4wLjABAAAA..." `
  --cookie-file ".\\cookies\\douyin.txt" `
  --audio-sample-rate 16000 `
  --audio-channels 1 `
  --audio-bitrate 64k
```

If you already have videos downloaded, skip the fetch step:

```powershell
python scripts/douyin_pipeline.py run --skip-download --video-dir ".\\existing-videos"
```

## Shared Config

The project uses a single shared config file: [config.example.json](/D:/codex/config.example.json).

Important sections:

- `douyin`: downloader command template and media discovery settings
- `ffmpeg`: audio conversion settings
- `oss`: OSS credentials, bucket, endpoint, and URL generation
- `funasr`: Bailian API key and transcription parameters
- `qwen_image`: Qwen image generation settings

The `douyin` section can also hold:

- `cookie`: raw Douyin cookie string
- `cookie_file`: path to a cookie file if you prefer not to inline the cookie

Runtime flags still override config values, so `--cookie` and `--cookie-file` take precedence when provided.

If you do not want secrets in `config.json`, leave them empty and use environment variables:

- `ALIYUN_ACCESS_KEY_ID`
- `ALIYUN_ACCESS_KEY_SECRET`
- `ALIYUN_SECURITY_TOKEN`
- `BAILIAN_API_KEY` or `DASHSCOPE_API_KEY`

## Bailian FunASR

This repository also includes a Bailian FunASR client at [scripts/bailian_funasr.py](/D:/codex/scripts/bailian_funasr.py).

The repository now bridges that constraint by uploading local audio files to OSS first, then submitting the resulting OSS-backed URL to Bailian FunASR.

Submit and wait for completion:

```powershell
python scripts/bailian_funasr.py --config config.json run `
  --local-file ".\runs\manual-download\audio\example_audio.mp3" `
  --download-results
```

Query an existing task:

```powershell
python scripts/bailian_funasr.py --config config.json status `
  --task-id "your-task-id" `
  --download-results
```

If you only want to upload a file to OSS and inspect the generated URL:

```powershell
python scripts/bailian_funasr.py --config config.json upload `
  --local-file ".\runs\manual-download\audio\example_audio.mp3"
```

Output files are written under `runs/funasr/<timestamp>/` by default:

- `uploads.json`: local file to OSS object mapping
- `submit.json`: raw submit response
- `task.json`: raw task status response
- `result_N.json`: downloaded transcription result JSON
- `result_N.txt`: extracted plain-text transcript
- `result_N.timeline.json`: sentence-level timeline with `begin_time_ms` and `end_time_ms`
- `result_N.srt`: subtitle file generated from sentence timestamps

## Video Scene Planning

The repository now also includes a first-stage text-to-video planner at [scripts/video_pipeline.py](/D:/codex/scripts/video_pipeline.py).

Current scope:

- read a script from `--text` or `--input-file`
- split it into scene-sized narration chunks
- generate `scene_plan.json` with `scene_id`, `narration`, `image_prompt`, and `duration`
- generate `image_tasks.json` for external image generation
- generate scene images directly with Qwen-Image
- render a draft `output.mp4` from existing `scene_XXX.png/jpg` images with a Ken Burns style motion pass

Example:

```powershell
python scripts/video_pipeline.py --config config.json plan `
  --input-file ".\vedio.md" `
  --output-dir ".\runs\video\demo-plan"
```

The default output directory is `runs/video/<timestamp>/`.

For a project-scoped remake run that keeps download, STT, rewrite, images, renders, and comparison outputs together, use:

```powershell
python scripts/story_video_project.py --config config.json run `
  --profile-url "https://www.douyin.com/video/7614714151727189617" `
  --max-scenes 4
```

That command now runs this chain:

- `Douyin -> STT -> summary -> rewrite -> TTS -> storyboard -> route A / route B -> final mux`

It writes one cohesive project tree under `runs/projects/<project-slug>/<timestamp>/`:

- `01_ingest/`
- `02_stt/`
- `03_summary/`
- `04_rewrite/`
- `05_tts/`
- `06_storyboard/`
- `07_route_a_qwen_ffmpeg/`
- `08_route_b_wan_i2v/`
- `09_final/`
- `10_compare/`

The TTS stage uses Bailian/Qwen TTS by default with `qwen3-tts-instruct-flash` and the `Serena` voice, then builds a shared narration track and aligned `subtitles.srt` for both video routes.

## Codex Skill

This repository now also includes a reusable Codex skill at [story-video-pipeline](/D:/codex/.codex/skills/story-video-pipeline).

Use that skill when you want Codex to:

- run the full remake workflow
- rerun an existing project root
- validate outputs
- check whether subtitles, audio, and final mux artifacts are complete

### Install In Another Codex

If another Codex environment can access this repository locally, copy the skill folder into that environment's Codex skills directory.

Windows example:

```powershell
Copy-Item `
  "D:\codex\.codex\skills\story-video-pipeline" `
  "$env:USERPROFILE\.codex\skills\story-video-pipeline" `
  -Recurse -Force
```

If you cloned this repository somewhere else, replace `D:\codex` with that local path.

The minimum files to copy are:

- `.codex/skills/story-video-pipeline/SKILL.md`
- `.codex/skills/story-video-pipeline/agents/openai.yaml`
- `.codex/skills/story-video-pipeline/references/workflow.md`

### Use In Another Codex

After the skill is installed, ask Codex with the skill name or with an equivalent intent, for example:

```text
Use story-video-pipeline to run the Douyin remake workflow for this video.
```

Or:

```text
Use story-video-pipeline to rerun the existing project root and verify final outputs.
```

The skill expects the target workspace to contain the pipeline scripts from this repository, especially:

- `scripts/story_video_project.py`
- `scripts/douyin_pipeline.py`
- `scripts/bailian_funasr.py`
- `scripts/video_pipeline.py`
- `config.json`

If another repository does not already contain those scripts, install the project module first or copy the relevant project files over before using the skill.

Generate image tasks from a scene plan:

```powershell
python scripts/video_pipeline.py image-tasks `
  --scene-plan ".\runs\video\demo-plan\scene_plan.json"
```

Generate images with Qwen-Image:

```powershell
python scripts/video_pipeline.py --config config.json generate-images `
  --scene-plan ".\runs\video\demo-plan\scene_plan.json" `
  --output-dir ".\runs\video\demo-images"
```

If you want to inspect requests before calling the paid API:

```powershell
python scripts/video_pipeline.py --config config.json generate-images `
  --scene-plan ".\runs\video\demo-plan\scene_plan.json" `
  --output-dir ".\runs\video\demo-images" `
  --dry-run
```

Render a video from existing scene images:

```powershell
python scripts/video_pipeline.py --config config.json render `
  --scene-plan ".\runs\video\demo-plan\scene_plan.json" `
  --images-dir ".\runs\video\demo-plan\images" `
  --output-dir ".\runs\video\demo-render"
```

Image filenames should follow `scene_001.png`, `scene_002.png`, or the same numbering with `.jpg/.jpeg/.webp`.

## 中文说明

这个仓库提供了一个本地可运行的 MVP 流水线，用于：

1. 通过外部下载器下载抖音用户视频
2. 将下载后的媒体文件转换为适合 ASR 的标准 MP3
3. 生成供后续处理使用的结构化清单文件

实现对应的 OpenSpec 变更见 [openspec/changes/add-douyin-fetch-pipeline](/D:/codex/openspec/changes/add-douyin-fetch-pipeline)。

### 运行前准备

- Python 3.11+
- `ffmpeg` 已加入 `PATH`，或通过 `--ffmpeg-path` 指定
- 可用的抖音下载器 CLI 已加入 `PATH`，或通过 `--downloader-bin` 指定
- 下载器需要时，准备好有效的抖音 Cookie

这个项目的目标是封装外部下载器，而不是自己实现抖音抓取逻辑。推荐下载器是 `f2`，但实际下载命令仍然保持可配置，以适配不同版本参数变化。

### 快速开始

1. 复制示例配置文件：

```powershell
Copy-Item config.example.json config.json
```

2. 按你的环境修改 `config.json` 中的 `douyin`、`ffmpeg`、`oss` 和 `funasr` 配置。

3. 运行流水线：

```powershell
python scripts/douyin_pipeline.py run --config config.json --profile-url "https://www.douyin.com/user/xxx"
```

4. 在 `runs/<timestamp-slug>/` 下查看输出结果。

### 下载命令模板

流水线会在执行下载器前，把占位符替换进命令模板。

支持的占位符：

- `{profile_url}`
- `{sec_user_id}`
- `{cookie}`
- `{cookie_file}`
- `{run_dir}`
- `{videos_dir}`

项目现在统一使用共享配置结构，下载命令位于 `douyin.download_template`。

请使用与你本机已安装版本一致的 `f2` 命令行参数格式。

### 输出目录

每次运行会写入 `runs/<timestamp>-<slug>/`：

- `videos/`：下载得到的视频文件
- `audio/`：转换后的 MP3 文件
- `manifest.json`：本次运行的结构化元数据

### 使用示例

```powershell
python scripts/douyin_pipeline.py run `
  --config config.json `
  --profile-url "https://www.douyin.com/user/MS4wLjABAAAA..." `
  --cookie-file ".\\cookies\\douyin.txt" `
  --audio-sample-rate 16000 `
  --audio-channels 1 `
  --audio-bitrate 64k
```

如果你已经提前下载好了视频，可以跳过下载阶段：

```powershell
python scripts/douyin_pipeline.py run --skip-download --video-dir ".\\existing-videos"
```

### 共享配置

项目使用单一共享配置文件：[config.example.json](/D:/codex/config.example.json)。

关键配置项：

- `douyin`：下载命令模板与媒体发现设置
- `ffmpeg`：音频转换设置
- `oss`：OSS 凭证、bucket、endpoint 和 URL 生成配置
- `funasr`：百炼 FunASR 的 API Key 与转写参数

`douyin` 部分还可以配置：

- `cookie`：直接写入的抖音 Cookie 字符串
- `cookie_file`：Cookie 文件路径，适合不想内联 Cookie 的场景

运行时命令行参数优先级更高，所以如果传入了 `--cookie` 或 `--cookie-file`，会覆盖配置文件中的值。

如果你不想把密钥写进 `config.json`，可以留空并改用环境变量：

- `ALIYUN_ACCESS_KEY_ID`
- `ALIYUN_ACCESS_KEY_SECRET`
- `ALIYUN_SECURITY_TOKEN`
- `BAILIAN_API_KEY` 或 `DASHSCOPE_API_KEY`

### 百炼 FunASR

仓库同时包含一个百炼 FunASR 客户端：[scripts/bailian_funasr.py](/D:/codex/scripts/bailian_funasr.py)。

由于流程需要先让本地音频具备可访问 URL，当前实现会先把音频上传到 OSS，再把对应的 OSS URL 提交给百炼 FunASR。

提交任务并等待完成：

```powershell
python scripts/bailian_funasr.py --config config.json run `
  --local-file ".\runs\manual-download\audio\example_audio.mp3" `
  --download-results
```

查询已有任务：

```powershell
python scripts/bailian_funasr.py --config config.json status `
  --task-id "your-task-id" `
  --download-results
```

如果你只想上传文件到 OSS 并查看生成的 URL：

```powershell
python scripts/bailian_funasr.py --config config.json upload `
  --local-file ".\runs\manual-download\audio\example_audio.mp3"
```

默认输出目录为 `runs/funasr/<timestamp>/`，其中包括：

- `uploads.json`：本地文件与 OSS 对象的映射
- `submit.json`：提交接口原始响应
- `task.json`：任务状态接口原始响应
- `result_N.json`：下载得到的转写结果 JSON
- `result_N.txt`：提取出的纯文本转写内容
- `result_N.timeline.json`：按句保存的时间轴，包含 `begin_time_ms` 和 `end_time_ms`
- `result_N.srt`：根据时间轴生成的字幕文件

### 视频分镜规划

仓库现在还增加了一个第一阶段的视频流水线入口：[scripts/video_pipeline.py](/D:/codex/scripts/video_pipeline.py)。

当前这一步只负责：

- 读取 `--text` 或 `--input-file` 输入脚本
- 按分镜时长把文本拆成旁白片段
- 输出包含 `scene_id`、`narration`、`image_prompt` 和 `duration` 的 `scene_plan.json`
- 输出给外部文生图环节消费的 `image_tasks.json`
- 可直接调用 Qwen-Image 生成分镜图片并下载到本地
- 基于现有 `scene_XXX.png/jpg` 图片用 ffmpeg 合成草稿视频 `output.mp4`

示例：

```powershell
python scripts/video_pipeline.py --config config.json plan `
  --input-file ".\vedio.md" `
  --output-dir ".\runs\video\demo-plan"
```

默认输出目录为 `runs/video/<timestamp>/`。

根据分镜生成图片任务清单：

```powershell
python scripts/video_pipeline.py image-tasks `
  --scene-plan ".\runs\video\demo-plan\scene_plan.json"
```

直接调用 Qwen-Image 出图：

```powershell
python scripts/video_pipeline.py --config config.json generate-images `
  --scene-plan ".\runs\video\demo-plan\scene_plan.json" `
  --output-dir ".\runs\video\demo-images"
```

如果你想先检查请求，不立刻调用计费接口：

```powershell
python scripts/video_pipeline.py --config config.json generate-images `
  --scene-plan ".\runs\video\demo-plan\scene_plan.json" `
  --output-dir ".\runs\video\demo-images" `
  --dry-run
```

使用现有分镜图片渲染视频：

```powershell
python scripts/video_pipeline.py --config config.json render `
  --scene-plan ".\runs\video\demo-plan\scene_plan.json" `
  --images-dir ".\runs\video\demo-plan\images" `
  --output-dir ".\runs\video\demo-render"
```

图片文件名建议使用 `scene_001.png`、`scene_002.png`，也支持同编号的 `.jpg`、`.jpeg`、`.webp`。
