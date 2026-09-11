# Percy Skin Editor

English users: scroll down to the English section.
Note: I use AI translation for the English version, so there may be some inaccuracies. Please refer to the Chinese version for the most accurate information.

---

### 介绍
Percy Skin Editor 是一个用于 osu!mania 的投皮编辑工具。

投皮（percy skin）是将 LN 面身拉伸到很长后，再通过顶部截断获得短尾视觉效果的做法。
本工具用于在stb和lzr下调整“投机取巧程度”，即 cut off by x pixels（从图片顶部到第一个非背景像素的距离）。

### 特性
- 支持批量处理、批量生成
- 支持 stb 和 lazer 两种模式
- 自动检测 LN 结构，适应不同皮肤设计
- 支持修复lazer中过度拉伸导致的视觉问题
- 支持修复stable中面尾白线问题
- 支持 常规 / 替换 两种输出模式，替换前自动备份原文件
- 自动检测并处理高度小于 1000px 的图片
- 配置持久化（输出模式、输出文件夹、备份文件夹、界面语言）
- 中英文双语界面，可在菜单 11 中随时切换

### 环境要求
- Python 3.8+
- Pillow
- requests
- packaging

### 安装

```bash
pip install -r requirements.txt
```

### 使用方法

```bash
python percy.py
```

### 菜单与按键

菜单上方始终显示当前输出模式。菜单为**整行输入**，输入后按回车确认。

| 按键 | 功能 |
|---|---|
| `?` | 帮助（半角 `?` 与全角 `？` 均可触发） |
| `0` | 重置默认配置（二次确认，需重启程序生效） |
| `1` | 切换模式（Stable / Lazer） |
| `2` | 查看当前投机取巧程度（仅单图模式） |
| `3` | 修改投机取巧程度 |
| `4` | 单图批量生成（仅单图模式） |
| `5` | 模式修复功能（Stable 为“修复面尾白线”，Lazer 为“图片拉伸修复”） |
| `6` | 调整输出模式 |
| `7` | 调整输出/备份文件夹 |
| `8` | 更换图片 |
| `9` | 检查更新 |
| `10` | 退出（保存配置） |
| `11` | 语言 / Language（切换界面语言：中文 / English） |

### 输出模式

- **常规模式（默认）**：处理结果输出到输出文件夹（默认 `/output`），不改动原文件。
- **替换模式**：输出前先把所选原文件复制到备份文件夹（默认 `/backup-archive`）下的 `[备份时间戳]` 子文件夹，随后用输出文件替换原文件。

细则：
- 同一批处理的文件共用**同一个时间戳文件夹**，不会因备份时间细微不同而拆成多个文件夹。
- 替换模式在用户确认输出前，会用醒目红色警告提示将覆盖原文件，并给出本次备份路径。
- 替换成功后提示原文件位置：`/backup-archive/[备份时间戳]-replaced-file`。
- 提示中的 `-replaced-file` / `-height-adjustment` 是**备份原因标记**，实际文件夹名为 `[备份时间戳]`。
- 替换模式下输出文件名与原文件保持一致，因此不再询问是否添加后缀。
- 同一批次只保留最初版本的原文件：菜单 4 连续生成多张时，不会反复覆盖备份。

### 高度小于 1000px 的图片

处理到高度小于 1000px 的图片时，程序会**先列出所有需要修改的文件名**，然后让你选择：

- `1 - 调整图片使其达到 1000px`：
  1. 将原文件复制到 `/backup-archive/[备份时间戳]`；
  2. 将图片纵向复制，副本紧贴不重叠；
  3. 高度达到 1000px 时停止复制；
  4. 输出结果替换原文件；
  5. 提示 `图片已成功调整，原文件已保存至 /backup-archive/[备份时间戳]-height-adjustment`。
- `2 - 返回`：返回文件选择输入界面，不做任何改动。

### 配置文件

- 配置文件为程序运行目录下的 `percy_config.json`，启动时读取、**退出时保存**。
- 若该文件不存在，启动时会自动创建默认配置文件。
- 默认值：输出模式 `常规模式`，输出文件夹 `/output`，备份文件夹 `/backup-archive`，语言 `中文`。
- 输出/备份文件夹以 `/` 或 `\` 开头表示**相对于程序运行目录**；也可以直接填绝对路径。
- 菜单 `0 - 重置默认配置` 会先二次确认，重置后提示需重启程序才能生效。

### 语言与入口程序

- 全部逻辑集中在 `percy.py`（单一实现，不再有重复代码）。
- `percy_en.py` 只是一个极薄的启动器，仅把**默认**界面语言设为 English，便于继续构建 `percy_en.exe`。
- 无论从哪个入口启动，都可以在菜单 `11 - 语言 / Language` 中切换语言，切换后界面立即生效，并写入配置文件。
- 配置文件已存在时，其中保存的语言优先于入口程序的默认值。

### 注意事项
- 处理前请备份原图（替换模式虽会自动备份，仍建议自行留存）
- 若 LN 结构不符合预期，处理可能失败
- Lazer 模式会进行 -75px 修正（下限 0），同时将强制执行图片标准化（长度固定在32800px）。
- 本程序暂不支持渐变颜色面身、非单一颜色或含有图案面身的皮肤。

---

## English

### Overview
Percy Skin Editor is a utility for editing osu!mania LN skin images.

A percy skin stretches the LN body to a very large height, then cuts from the top to create a short-tail visual effect.
This tool adjusts the cut-off amount at the top of the image, i.e., cut off by x pixels (distance from image top to the first non-background pixel).

### Features
- Supports batch processing and batch generation
- Supports both Stable and Lazer client
- Automatically detects LN structure and adapts to different skin designs
- Supports fixing visual issues caused by excessive stretching in Lazer
- Supports fixing the tail white-line issue in Stable
- Normal / Replace output modes, with automatic backup of originals before replacement
- Detects and can automatically fix images shorter than 1000px
- Persistent configuration (output mode, output folder, backup folder, UI language)
- Bilingual Chinese/English interface, switchable at any time from menu 11

### Requirements
- Python 3.8+
- Pillow
- requests
- packaging

### Installation

```bash
pip install -r requirements.txt
```

### Usage

```bash
python percy_en.py
```

### Menu and Keys

The current output mode is always shown above the menu. The menu uses **whole-line input**: type and press Enter.

| Key | Function |
|---|---|
| `?` | Help (both `?` and the full-width `？` work) |
| `0` | Reset default config (second confirmation; restart required) |
| `1` | Switch mode (Stable / Lazer) |
| `2` | View current d (single-image mode only) |
| `3` | Modify d |
| `4` | Single-image batch generation (single-image mode only) |
| `5` | Mode fix tool (Stable: "Fix Tail White Line"; Lazer: "Stretch Repair") |
| `6` | Adjust output mode |
| `7` | Adjust output/backup folder |
| `8` | Switch image |
| `9` | Check updates |
| `10` | Quit (saves config) |
| `11` | Language / 语言 (switch the interface language: 中文 / English) |

### Output Modes

- **Normal Mode (default)**: results are written to the output folder (default `/output`); original files are never modified.
- **Replace Mode**: before output, each selected original is copied into the backup folder (default `/backup-archive`) under a `[timestamp]` subfolder, then the output replaces the original file.

Details:
- All files in the same batch share **one timestamp folder**; small timing differences never split a batch.
- Before the user confirms output, Replace Mode shows a bold red warning that originals will be overwritten, together with this run's backup path.
- On success the original file location is reported as `/backup-archive/[timestamp]-replaced-file`.
- The `-replaced-file` / `-height-adjustment` markers describe the **reason for the backup**; the real folder name is `[timestamp]`.
- In Replace Mode the output filename equals the original filename, so no suffix is asked.
- A batch keeps only the very first original version: repeatedly generating from menu 4 does not overwrite the backup again.

### Images Shorter Than 1000px

When an image shorter than 1000px is encountered, the tool **lists every file that needs modifying first**, then asks:

- `1 - Adjust image(s) to reach 1000px`:
  1. copy the original into `/backup-archive/[timestamp]`;
  2. tile the image vertically, copies flush and non-overlapping;
  3. stop once the height reaches 1000px;
  4. the result replaces the original file;
  5. report `Originals saved to /backup-archive/[timestamp]-height-adjustment`.
- `2 - Go back`: return to the path input screen without changing anything.

### Config File

- The config file is `percy_config.json` in the program working directory; it is read at startup and **saved on exit**.
- If the file does not exist, a default config file is created at startup.
- Defaults: output mode `Normal Mode`, output folder `/output`, backup folder `/backup-archive`, language `中文`.
- A leading `/` or `\` in the output/backup folder means **relative to the program directory**; absolute paths are also accepted.
- Menu `0 - Reset default config` asks for a second confirmation and then tells you to restart the program.

### Language and Entry Points

- All logic now lives in `percy.py` (a single implementation, no more duplicated code).
- `percy_en.py` is only a thin launcher that sets the **default** interface language to English,
  so the existing `percy_en.exe` build still works.
- Whichever entry point you start, you can switch language from menu `11 - Language / 语言`;
  the change takes effect immediately and is written to the config file.
- If a config file already exists, the language stored in it wins over the entry point default.

### Notes
- Back up original files before processing (Replace Mode backs up automatically, but keeping your own copy is still recommended)
- Invalid LN structure may cause processing errors
- Lazer mode applies a -75px correction (minimum 0), and normalizes all images to a fixed height of 32800px to prevent excessive stretching.
- Stable mode keeps original behavior during normal processing; for white-line repair, if image height exceeds 32767px, content beyond 32767px is cropped and discarded, and the last row is set to fully transparent.
- This program currently does not support gradient, patterned, or other complex non-uniform note bodies.
