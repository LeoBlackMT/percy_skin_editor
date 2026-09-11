# Percy Skin Editor

[中文](README.md) | [English](README_EN.md)

### Overview
Percy Skin Editor is a utility for editing osu!mania percy skin images.

A percy skin stretches the LN body to a very large height, then cuts from the top to create a short-tail visual effect, making LN charts easier to read.
This tool adjusts the cut-off amount at the top of the image, i.e., cut off by x pixels (distance from the image top to the first non-background pixel).

### Features
- Supports batch processing and batch generation
- Supports both Stable and Lazer client
- Automatically detects LN structure and adapts to different skin designs
- Supports fixing visual issues caused by excessive stretching in Lazer
- Supports fixing the tail white-line issue in Stable
- Supports both Normal and Replace output modes; originals are backed up automatically before replacement, making it convenient to edit existing skins directly
- Detects and handles images shorter than 1000px automatically
- Persistent configuration (output mode, output folder, backup folder, UI language)

### Requirements
- A 64-bit Windows system (the released executables are 64-bit builds)
- No Python or third-party dependencies required; the executables bundle the complete runtime
- Everything works offline except "Check updates", which needs access to GitHub

### Build from Source / Usage

```bash
pip install -r requirements.txt
python percy_en.py
```

`percy.py` is the same program with Chinese as the default interface language.

### Menu and Keys

The current output mode is always shown above the menu. The menu uses **whole-line input**: type and press Enter.

| Key | Function |
|---|---|
| `?` | Help (both the half-width `?` and the full-width `？` work) |
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
- All files in the same batch share **one backup folder**
- Before confirming output, Replace Mode clearly indicates the original files that are about to be overwritten and shows this run's backup path.
- On success the backup location is shown as `/backup-archive/[timestamp]-replaced-file`.
- The `-replaced-file` / `-height-adjustment` markers describe the **reason for the backup**; the real folder name is `[timestamp]`.
- A batch keeps only the very first original version: repeatedly generating from menu 4 does not overwrite the backup again.

### Handling Images Shorter Than 1000px

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
- Menu `0 - Reset default config` requires restarting the program to take effect.

### Notes
- Back up original files before processing (Replace Mode backs up automatically, but keeping your own copy is still recommended)
- Invalid LN structure may cause processing errors
- Lazer mode applies a -75px correction (minimum 0), and forcibly normalizes images (height fixed at 32800px).
- This program currently does not support gradient, patterned, or other complex non-uniform note bodies.
