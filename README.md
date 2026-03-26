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


### 注意事项
- 处理前请备份原图
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

### Notes
- Back up original files before processing
- Invalid LN structure may cause processing errors
- Lazer mode applies a -75px correction (minimum 0), and normalizes all images to a fixed height of 32800px to prevent excessive stretching.
- Stable mode keeps original behavior during normal processing; for white-line repair, if image height exceeds 32767px, content beyond 32767px is cropped and discarded, and the last row is set to fully transparent.
- This program currently does not support gradient, patterned, or other complex non-uniform note bodies.
