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
- When picking a folder you can target only the matching LN note-body files, or all images
- Persistent configuration (output mode, output folder, backup folder, UI language)

### Requirements
- A 64-bit Windows system (the released executables are 64-bit builds)
- The executable bundles the complete runtime, so no Python or third-party dependencies are needed
- Everything works offline except "Check updates", which needs access to GitHub

### Usage

**Option 1: download the executable (recommended)**

Download `percy.exe` from the Releases page and double-click it. No Python or dependencies required.

**Option 2: run from source**

```bash
pip install -r requirements.txt
python percy.py
```

Requires Python 3.8+; third-party dependencies are listed in `requirements.txt`.

### Menu and Keys

The current output mode is always shown above the menu. The menu is **single-key**:
press one key and it runs immediately, no Enter needed.

| Key | Function |
|---|---|
| `?` | Help (both the half-width `?` and the full-width `？` work) |
| `0` | Reset default config (output mode and folders apply immediately; the UI language switches after a restart) |
| `1` | Switch mode (Stable / Lazer) |
| `2` | View current d (single image shows its own d; directory mode lists the d of every selected image) |
| `3` | Modify d |
| `4` | Single-image batch generation (single-image mode only) |
| `5` | Mode fix tool (Stable: "Fix Tail White Line"; Lazer: "Stretch Repair") |
| `6` | Adjust output mode |
| `7` | Adjust output/backup folder |
| `8` | Switch image |
| `9` | Check updates |
| `L` | Language / 语言 (switch the interface language: 中文 / English) |
| `Q` | Quit (saves config) |

Places that need typed text (image/folder paths, the d value, batch start/end/step) still use
whole-line input confirmed with Enter. In menus `7` and `L`, **leaving the input empty
(pressing Enter) returns to the parent menu**.

### Selecting a Directory

After you choose a directory, the tool first lists the files named like `mania-note<digit>L`
or `NoteImage*L` and reports the total PNG count, then asks you to confirm the scope:

- `1` - Only the matched files listed above
- `2` - All image files in that directory
- Enter - return to the path input

When several files are selected, menu `2` lists the cut-off amount of every image, one per line.

### Output Modes

- **Normal Mode (default)**: results are written to the output folder (default `/output`); original files are never modified.
- **Replace Mode**: before output, each selected original is copied into the backup folder (default `/backup-archive`) under a `[timestamp]` subfolder, then the output replaces the original file.

Details:
- All files in the same batch share **one backup folder**.
- Before confirming output, Replace Mode clearly indicates the original files that are about to be overwritten and shows this run's backup path.
- On success the backup location shown is the folder that was **actually created**: `/backup-archive/[timestamp]`.
- A batch keeps only the very first original version: repeatedly generating from menu 4 does not overwrite the backup again.
- During a Replace-Mode batch (menu 4), **every d is regenerated from the original file** rather than
  applied on top of the previous result, so the output matches generating each image in Normal Mode and
  the note body is never consumed cumulatively.
- In Normal Mode, if the output folder is set to the source directory *and* no filename suffix is
  used, the output path would equal the original file. In that case the file is **skipped with a
  message** rather than overwriting the original.

### Images Shorter Than 1000px

Such images are **outside this tool's scope**: they are usually a different tail structure rather
than a Repeat-mode note body, so tiling them vertically would not achieve anything. The tool
**excludes them from the current run** and explains why — it **does not modify any file**:

- if other processable files were selected, it skips these and continues with the rest;
- if every selected image is of this kind, it says so and returns to the path input so you can choose again.

### Config File

- The config file is `percy_config.json` next to the executable (or next to the script when run from
  source); it is read at startup and **saved on exit**.
- If the file does not exist, a default config file is created at startup.
- Defaults: output mode `Normal Mode`, output folder `/output`, backup folder `/backup-archive`
  (on Windows; on other platforms these defaults are the relative names `output` / `backup-archive`,
  because `/output` is an absolute path under the filesystem root on POSIX).
- The interface language is taken from the **system UI language on first run**, and is governed by the
  config file afterwards (changeable from menu `L`, or forced at startup with the
  `--lang zh|en` command-line option, which also works before a config file exists).
- If the config file cannot be parsed, or parses but is not a JSON object, it is first renamed to
  `percy_config.json.bak` before the defaults are written, so settings are never discarded silently.
- On **Windows** a leading `/` or `\` in the output/backup folder means **relative to the program
  directory**; absolute paths are also accepted. On other platforms a leading `/` is an ordinary
  absolute path and is left alone.

### Notes
- Back up original files before processing (Replace Mode backs up automatically, but keeping your own copy is still recommended)
- Invalid LN structure may cause processing errors
- Lazer mode applies a -75px correction (minimum 0), and forcibly normalizes images (height fixed at 32800px).
- This program currently does not support gradient, patterned, or other complex non-uniform note bodies.
