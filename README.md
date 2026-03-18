# Percy Skin Editor

English users: scroll down to the English section.

---

### 介绍
Percy Skin Editor 是一个用于 osu!mania 的投皮编辑工具。

投皮（percy skin）是将 LN 面身拉伸到很长后，再通过顶部截断获得短尾视觉效果的做法。
本工具用于在stb和lzr下调整“投机取巧程度”，即 cut off by x pixels（从图片顶部到第一个非背景像素的距离）。

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

英文界面：

```bash
python percy_en.py
```

### 注意事项
- 处理前请备份原图
- 若 LN 结构不符合预期，处理可能失败
- Lazer 模式会进行 -75px 修正（下限 0），同时将图片长度固定在32800px。
- 本程序暂不支持渐变颜色面身、非单一颜色或含有图案面身的皮肤。

---

## English

### Overview
Percy Skin Editor is a utility for editing osu!mania LN skin images.

A percy skin stretches the LN body to a very large height, then cuts from the top to create a short-tail visual effect.
This tool adjusts the cut-off amount at the top of the image, i.e., cut off by x pixels (distance from image top to the first non-background pixel).

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

Chinese UI:

```bash
python percy.py
```

English UI:

```bash
python percy_en.py
```

### Notes
- Back up original files before processing
- Invalid LN structure may cause processing errors
- Lazer mode applies a -75px correction (minimum 0), and normalizes all images to a fixed height of 32800px to prevent excessive stretching.
- This program currently does not support gradient, patterned, or other complex non-uniform note bodies.
