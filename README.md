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
