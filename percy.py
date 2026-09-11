import json
import os
import shutil
import sys
from datetime import datetime

import requests
from packaging.version import parse as parse_version
from PIL import Image

VERSION = "1.6.0"

_OWNER = "LeoBlackMT"
_REPO = "percy_skin_editor"
_GITHUB_API = "https://api.github.com"

# ---------------- 界面语言 / UI language ----------------

DEFAULT_LANGUAGE = "zh"
LANGUAGES = ("zh", "en")

LANG = DEFAULT_LANGUAGE


def t(zh_text, en_text):
    """按当前界面语言返回文本。中文为基准语言，英文作为替代文本传入。"""
    return zh_text if LANG == "zh" else en_text


def language_label(lang=None):
    lang = lang or LANG
    return "中文" if lang == "zh" else "English"


def _entry_language(default_language=None):
    """把入口程序传入的默认语言规范化为受支持的语言代码。"""
    return default_language if default_language in LANGUAGES else DEFAULT_LANGUAGE

# ---------------- 配置持久化 ----------------

CONFIG_FILENAME = "percy_config.json"

OUTPUT_MODE_NORMAL = "normal"
OUTPUT_MODE_REPLACE = "replace"

MIN_IMAGE_HEIGHT = 1000

DEFAULT_CONFIG = {
    "output_mode": OUTPUT_MODE_NORMAL,
    "output_dir": "/output",
    "backup_dir": "/backup-archive",
    "language": DEFAULT_LANGUAGE,
}

_CONFIG = None


def get_base_dir():
    """程序运行目录：配置文件与默认输出/备份目录的基准。"""
    return os.getcwd()


def get_config_path():
    return os.path.join(get_base_dir(), CONFIG_FILENAME)


def default_config():
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    try:
        with open(get_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_config(default_language=None):
    """读取配置；若程序运行目录下不存在配置文件则自动创建默认配置文件。"""
    cfg = default_config()
    cfg["language"] = _entry_language(default_language)
    path = get_config_path()
    if not os.path.isfile(path):
        save_config(cfg)
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        save_config(cfg)
        return cfg
    if isinstance(data, dict):
        for key in cfg:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                cfg[key] = value.strip()
    if cfg["output_mode"] not in (OUTPUT_MODE_NORMAL, OUTPUT_MODE_REPLACE):
        cfg["output_mode"] = OUTPUT_MODE_NORMAL
    if cfg["language"] not in LANGUAGES:
        cfg["language"] = _entry_language(default_language)
    return cfg


def config(default_language=None):
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_config(default_language)
    return _CONFIG


def set_config(cfg):
    global _CONFIG
    _CONFIG = cfg


def reset_default_config(language=None):
    """重置为默认配置并立即写回配置文件。"""
    cfg = default_config()
    cfg["language"] = _entry_language(language)
    save_config(cfg)
    set_config(cfg)
    return cfg


def output_mode_label(mode=None):
    if mode is None:
        mode = config().get("output_mode", OUTPUT_MODE_NORMAL)
    return t("替换模式", "Replace Mode") if mode == OUTPUT_MODE_REPLACE else t("常规模式", "Normal Mode")


def resolve_dir(path):
    """解析目录配置：单个前导 / 或 \\ 表示相对程序运行目录。"""
    if not path or not str(path).strip():
        return get_base_dir()
    p = str(path).strip()
    if len(p) > 1 and p[0] in "/\\" and p[1] not in "/\\":
        p = p[1:]
    if os.path.isabs(p):
        return os.path.normpath(p)
    return os.path.normpath(os.path.join(get_base_dir(), p))


def get_output_dir():
    d = resolve_dir(config().get("output_dir", DEFAULT_CONFIG["output_dir"]))
    os.makedirs(d, exist_ok=True)
    return d


def get_backup_root():
    d = resolve_dir(config().get("backup_dir", DEFAULT_CONFIG["backup_dir"]))
    os.makedirs(d, exist_ok=True)
    return d


def make_timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def backup_dir_for(timestamp):
    d = os.path.join(get_backup_root(), timestamp)
    os.makedirs(d, exist_ok=True)
    return d


def backup_file(src, timestamp):
    """把原文件复制到 备份根/[备份时间戳]/ 下。

    同一批次内若目标已存在则不重复覆盖，保证一批备份只保留最初的原文件。
    """
    target = os.path.join(backup_dir_for(timestamp), os.path.basename(src))
    if not os.path.exists(target):
        shutil.copy2(src, target)
    return target

def getch():
    """返回用户按下的单个字符（不等待回车）"""
    if os.name == 'nt':  # Windows
        import msvcrt
        return msvcrt.getch().decode('utf-8', errors='ignore')
    else:  # Unix/Linux/Mac
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def normalize_input_path(path: str):
    path = path.strip()
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    elif path.startswith("'") and path.endswith("'"):
        path = path[1:-1]
    return path

def build_output_path(source_path, d_value, lzr=False, suffix=True):
    base = os.path.basename(source_path)
    name, _ = os.path.splitext(base)
    if not suffix:
        output_name = f"{name}.png"
    elif lzr:
        output_name = f"{name}-{d_value}px-lzr.png"
    else:
        output_name = f"{name}-{d_value}px.png"
    return os.path.join(get_output_dir(), output_name)

def build_normalize_output_path(source_path, lzr=False):
    base = os.path.basename(source_path)
    name, _ = os.path.splitext(base)
    if lzr:
        output_name = f"{name}-lzr-normalized.png"
    else:
        output_name = f"{name}-stable-tail-fixed.png"
    return os.path.join(get_output_dir(), output_name)

def collect_png_targets(path):
    if os.path.isfile(path):
        if os.path.splitext(path)[1].lower() != '.png':
            raise LNImageError(t("仅支持 PNG 格式图片。", "Only PNG images are supported."))
        return [path], "file"
    if os.path.isdir(path):
        pngs = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if os.path.isfile(full) and os.path.splitext(name)[1].lower() == '.png':
                pngs.append(full)
        if not pngs:
            raise LNImageError(t("目录下未找到 PNG 文件。", "No PNG files found in this directory."))
        return pngs, "dir"
    raise LNImageError(t("路径不存在，请重新输入。", "Path does not exist. Please try again."))

def find_undersized(targets):
    """返回高度小于 MIN_IMAGE_HEIGHT 的图片路径列表。"""
    undersized = []
    for path in targets:
        try:
            with Image.open(path) as tmp:
                if tmp.height < MIN_IMAGE_HEIGHT:
                    undersized.append(path)
        except Exception as e:
            raise LNImageError(f"{t('无法打开图片 ', 'Cannot open image ')}{path}: {e}")
    return undersized


def tile_image_to_height(img, target=MIN_IMAGE_HEIGHT):
    """纵向平铺副本（紧贴不重叠），直到高度达到 target，多余部分裁掉。"""
    w, h = img.size
    if h <= 0:
        raise LNImageError(t("图片高度为 0，无法调整。", "Image height is 0 and cannot be adjusted."))
    if h >= target:
        return img
    new_img = Image.new("RGBA", (w, target), (0, 0, 0, 0))
    y = 0
    while y < target:
        new_img.paste(img, (0, y))
        y += h
    return new_img


def adjust_image_height(path, timestamp):
    """备份原文件后把图片纵向平铺到 MIN_IMAGE_HEIGHT，并用结果替换原文件。"""
    backup_file(path, timestamp)
    with Image.open(path) as im:
        img = im.convert("RGBA")
    fixed = tile_image_to_height(img)
    tmp_path = path + ".percy-tmp.png"
    try:
        fixed.save(tmp_path)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def handle_undersized(undersized):
    """处理高度不足的图片。返回 True 表示继续，False 表示返回文件选择界面。"""
    print(f"\n{Color.WARNING}"
          + t(f"检测到 {len(undersized)} 张图片高度小于 {MIN_IMAGE_HEIGHT}px，低于该高度可能无法正确识别结构：",
              f"Detected {len(undersized)} image(s) shorter than {MIN_IMAGE_HEIGHT}px; "
              f"structure detection may fail below that height:")
          + f"{Color.ENDC}")
    for path in undersized:
        print(f"  {Color.BOLD}- {path}{Color.ENDC}")
    print(f"\n{Color.OKBLUE}{t('请选择操作:', 'Select an action:')}{Color.ENDC}")
    print(t("  1 - 调整图片使其达到 1000px（原文件先备份，结果替换原文件）",
            "  1 - Adjust image(s) to reach 1000px (originals are backed up first, results replace them)"))
    print(t("  2 - 返回", "  2 - Go back"))
    print("> ", end='', flush=True)
    ans = input().strip()
    if ans != '1':
        return False

    timestamp = make_timestamp()
    done = 0
    errors = []
    for path in undersized:
        try:
            adjust_image_height(path, timestamp)
            done += 1
        except Exception as e:
            errors.append((path, str(e)))

    backup_label = os.path.join(get_backup_root(), f"{timestamp}-height-adjustment")
    if errors:
        print(f"{Color.WARNING}"
              + t(f"调整结束：成功 {done} 张，失败 {len(errors)} 张。",
                  f"Adjustment finished: {done} succeeded, {len(errors)} failed.")
              + f"{Color.ENDC}")
        for path, err in errors:
            print(f"{Color.FAIL}{t('失败: ', 'Failed: ')}{path} -> {err}{Color.ENDC}")
    else:
        print(f"{Color.OKGREEN}"
              + t(f"图片已成功调整，原文件已保存至 {backup_label}",
                  f"Image(s) adjusted successfully. Originals saved to {backup_label}")
              + f"{Color.ENDC}")
    return True

def confirm_action(prompt):
    print(f"{Color.WARNING}{prompt}{Color.ENDC}")
    ans = input("输入 y 确认，其他任意键取消: ").strip().lower()
    return ans == 'y'

def emit_output(src, mode, timestamp, build_path, produce):
    """按输出模式写出结果，返回结果文件路径。

    常规模式：写到 build_path() 指定的输出路径。
    替换模式：先把原文件备份到 备份根/[备份时间戳]/，再用结果替换原文件。
    """
    if mode == OUTPUT_MODE_REPLACE:
        backup_file(src, timestamp)
        tmp_path = src + ".percy-tmp.png"
        try:
            produce(tmp_path)
            os.replace(tmp_path, src)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        return src
    output_path = build_path()
    produce(output_path)
    return output_path

def process_targets(targets, d_value, lzr=False, suffix=True, mode=None, timestamp=None):
    if mode is None:
        mode = config().get("output_mode", OUTPUT_MODE_NORMAL)
    if mode == OUTPUT_MODE_REPLACE and timestamp is None:
        # 同一批次只取一个时间戳，保证一批备份落在同一个文件夹
        timestamp = make_timestamp()
    success = 0
    failed = 0
    errors = []
    last_output_path = ""
    for src in targets:
        try:
            last_output_path = emit_output(
                src,
                mode,
                timestamp,
                lambda s=src: build_output_path(s, d_value, lzr=lzr, suffix=suffix),
                lambda p, s=src: process_ln_image(s, d_value, lzr=lzr, output_path=p),
            )
            success += 1
        except Exception as e:
            failed += 1
            errors.append((src, str(e)))
    return success, failed, errors, last_output_path

def process_normalize_targets(targets, lzr=False, mode=None, timestamp=None):
    if mode is None:
        mode = config().get("output_mode", OUTPUT_MODE_NORMAL)
    if mode == OUTPUT_MODE_REPLACE and timestamp is None:
        timestamp = make_timestamp()
    success = 0
    failed = 0
    errors = []
    last_output_path = ""
    for src in targets:
        try:
            last_output_path = emit_output(
                src,
                mode,
                timestamp,
                lambda s=src: build_normalize_output_path(s, lzr=lzr),
                lambda p, s=src: normalize_image_file(s, lzr=lzr, output_path=p),
            )
            success += 1
        except Exception as e:
            failed += 1
            errors.append((src, str(e)))
    return success, failed, errors, last_output_path

def build_d_values(start_value, end_value, step):
    if step == 0:
        raise LNImageError("步长不能为 0。")
    if start_value <= end_value:
        return list(range(start_value, end_value + 1, step))
    return list(range(start_value, end_value - 1, -step))

class Color:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class LNImageError(Exception):
    """自定义异常"""
    pass

def check_update(current_version: str):
    """
    检查更新
    """
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        r = requests.get(f"{_GITHUB_API}/repos/{_OWNER}/{_REPO}/releases/latest", headers=headers, timeout=10)
        if r.status_code == 200:
            rel = r.json()
        else:
            r2 = requests.get(f"{_GITHUB_API}/repos/{_OWNER}/{_REPO}/releases", headers=headers, timeout=10)
            r2.raise_for_status()
            rels = r2.json()
            rel = None
            for rr in rels:
                if rr.get("draft"):
                    continue
                if rr.get("prerelease"):
                    continue
                rel = rr
                break
            if not rel:
                return False, ""
    except Exception:
        return False, ""

    tag = rel.get("tag_name") or rel.get("name") or ""
    latest = tag.lstrip("vV").strip()
    if not latest:
        return False, ""
    try:
        has = parse_version(latest) > parse_version(current_version.lstrip("vV").strip())
    except Exception:
        has = latest != current_version.lstrip("vV").strip()
    return has, latest

def normalize_height(img, bg, lzr=False):
    w, h = img.size

    if lzr:
        target_h = 32800
        if h == target_h:
            return img
        if h > target_h:
            return img.crop((0, 0, w, target_h))

        need = target_h - h
        new_img = Image.new("RGBA", (w, target_h), bg)
        new_img.paste(img, (0, 0))
        y_offset = h
        while y_offset < target_h:
            take = min(need, h)
            bottom_slice = img.crop((0, h - take, w, h))
            new_img.paste(bottom_slice, (0, y_offset))
            y_offset += take
            need -= take
        return new_img

    if h <= 32767:
        return img

    new_img = img.crop((0, 0, w, 32767))
    new_img.paste((0, 0, 0, 0), (0, 32766, w, 32767))
    return new_img

def normalize_image_file(image_path, lzr=False, output_path=None):
    img = Image.open(image_path).convert("RGBA")
    bg = img.getpixel((0, 0))
    fixed_img = normalize_height(img, bg, lzr=lzr)
    if output_path:
        fixed_img.save(output_path)
    return fixed_img

def find_first_non_bg_row(img, bg):
    """返回第一个包含非背景色像素的行号，即图片当前的投皮程度 d。"""
    w, h = img.size
    px = img.load()
    for y in range(h):
        for x in range(w):
            if px[x, y] != bg:
                return y
    raise LNImageError(t("未找到非背景色像素，图片可能全为背景。",
                         "No non-background pixel found; the image may be entirely background."))

def detect_ln_structure(img, bg):
    """探测 LN 结构，返回 (a_true, x1, x2, y)。

    a_true : 第一个非背景色像素所在行（当前 d 值）
    x1, x2 : 中点行上面身的最左 / 最右非背景色列
    y      : 从 x1、x2 两列各自向上找到的背景色行号的较大者（面尾下边界）
    """
    a_true = find_first_non_bg_row(img, bg)
    w, h = img.size
    px = img.load()

    mid_y = h // 2
    x1 = None
    for x in range(w):
        if px[x, mid_y] != bg:
            x1 = x
            break
    if x1 is None:
        raise LNImageError(t("在左侧中点未能找到非背景色像素。",
                             "No non-background pixel found at the left of the middle row."))

    x2 = None
    for x in range(w - 1, -1, -1):
        if px[x, mid_y] != bg:
            x2 = x
            break
    if x2 is None:
        raise LNImageError(t("在右侧中点未能找到非背景色像素。",
                             "No non-background pixel found at the right of the middle row."))

    def find_background_upwards(col, start_y):
        for y in range(start_y, -1, -1):
            value = px[col, y]
            if value == bg or value[3] == 0:
                return y
        raise LNImageError(t(f"在列 {col} 从 y={start_y} 向上未找到背景色像素。",
                             f"No background pixel found in column {col} above y={start_y}."))

    y1 = find_background_upwards(x1, mid_y)
    y2 = find_background_upwards(x2, mid_y)
    return a_true, x1, x2, max(y1, y2)

def get_current_d(image_path):
    """返回当前图片的投机取巧程度 d"""
    with Image.open(image_path) as im:
        img = im.convert("RGBA")
    bg = img.getpixel((0, 0))
    return find_first_non_bg_row(img, bg)

def process_ln_image(image_path, user_d, lzr=False, output_path=None):
    with Image.open(image_path) as im:
        img = im.convert("RGBA")
    w, h = img.size
    bg = img.getpixel((0, 0))

    a_true, x1, x2, y = detect_ln_structure(img, bg)

    if y > a_true + 1:
        if lzr:
            a_target = max(0, user_d - 75)
        else:
            a_target = user_d

        tail_h = y - a_true + 1
        y_target = a_target + tail_h - 1

        tail_region = img.crop((x1, a_true, x2 + 1, y + 1))
        body_region = None
        if y + 1 < h:
            body_region = img.crop((x1, y + 1, x2 + 1, h))
        body_h = body_region.height if body_region else 0

        fill_region = None
        body_new = body_region
        if y_target < y:
            gap = y - y_target
            if body_h == 0:
                raise LNImageError(t("需要填充间隙，但面身不存在，无法截取。",
                                     "A gap must be filled but no note body exists."))
            if gap > body_h:
                raise LNImageError(t("需要填充的间隙大于面身高度，无法单次截取。",
                                     "The gap to fill is taller than the note body."))
            fill_region = body_region.crop((0, 0, x2 - x1 + 1, gap))
            if body_h - gap > 0:
                body_new = body_region.crop((0, gap, x2 - x1 + 1, body_h))
            else:
                body_new = None
        elif y_target > y:
            overlap = y_target - y
            if body_h == 0:
                raise LNImageError(t("需要丢弃重叠部分，但面身不存在。",
                                     "Overlap must be discarded but no note body exists."))
            if overlap >= body_h:
                body_new = None
            else:
                body_new = body_region.crop((0, overlap, x2 - x1 + 1, body_h))
        else:
            pass

        tail_h = tail_region.height
        fill_h = fill_region.height if fill_region else 0
        body_new_h = body_new.height if body_new else 0
        total_h = a_target + tail_h + fill_h + body_new_h

        new_img = Image.new("RGBA", (w, total_h), bg)
        new_img.paste(tail_region, (x1, a_target))
        if fill_region:
            new_img.paste(fill_region, (x1, a_target + tail_h))
        if body_new:
            new_img.paste(body_new, (x1, a_target + tail_h + fill_h))

    else:
        if lzr:
            new_top = max(0, user_d - 75)
        else:
            new_top = user_d
        body_region = img.crop((x1, a_true, x2 + 1, h))
        body_h = body_region.height
        delta = new_top - a_true
        if delta > 0:
            gap = delta
            if gap > body_h:
                fill_region = body_region
                new_img = Image.new("RGBA", (w, new_top + body_h), bg)
                new_img.paste(fill_region, (x1, new_top))
            else:
                fill_region = body_region.crop((0, 0, x2 - x1 + 1, gap))
                remaining_region = body_region.crop((0, gap, x2 - x1 + 1, body_h))
                new_img_h = new_top + body_h
                new_img = Image.new("RGBA", (w, new_img_h), bg)
                new_img.paste(fill_region, (x1, new_top))
                new_img.paste(remaining_region, (x1, new_top + gap))
        elif delta < 0:
            cut = -delta
            if cut >= body_h:
                new_img = Image.new("RGBA", (w, 1), bg)
            else:
                remaining_region = body_region.crop((0, cut, x2 - x1 + 1, body_h))
                new_top_actual = max(0, new_top)
                new_img_h = new_top_actual + (body_h - cut)
                new_img = Image.new("RGBA", (w, new_img_h), bg)
                new_img.paste(remaining_region, (x1, new_top_actual))
        else:
            new_img = Image.new("RGBA", (w, h), bg)
            new_img.paste(body_region, (x1, a_true))

    if lzr:
        new_img = normalize_height(new_img, bg, lzr=True)

    if output_path:
        new_img.save(output_path)
    return new_img

def print_help():
    if LANG == "en":
        help_text = f"""
{Color.BOLD}{Color.OKGREEN}========== Help Information =========={Color.ENDC}
{Color.OKCYAN}[What Is Percy]{Color.ENDC}
  - Percy stretches a note body to an extremely long image, then creates a short-tail
    visual effect by clipping from the top.
  - In high-density LN charts, many players use percy skins for better readability.
  - Percy can reduce reading pressure, but cannot provide precise release timing.
  - We define the distance from the first non-background pixel to the top as the
    cut-off amount, also called d in this program.
{Color.OKCYAN}[Mode Explanation]{Color.ENDC}
  - Stable Mode: Set a new d directly. The tool moves tail and body automatically.
  - Lazer Mode: Based on measurements, early-2026 lazer may stretch by roughly +75px.
    So in this mode, user input is converted by minus 75 (with lower bound 0).
    Also, output height is normalized to 32800px.
{Color.OKCYAN}[Output Mode Explanation]{Color.ENDC}
  - Normal Mode: default. Results are written to the output folder (default /output);
    original files are never modified.
  - Replace Mode: before processing, each selected original is copied into the backup
    folder (default /backup-archive) under a [timestamp] subfolder, then the result
    replaces the original file.
    All files in the same batch share one timestamp folder.
    The -replaced-file / -height-adjustment markers in messages only describe the
    reason for the backup; the real folder name is [timestamp].
{Color.OKCYAN}[Menu Description]{Color.ENDC}
  - ? - Help: Show this help page (both ? and the full-width ？ work).
  - 0 - Reset Default Config: after a second confirmation, restore the output mode,
    output folder, backup folder and language to defaults. A restart is required.
  - 1 - Switch Mode: Toggle between Stable and Lazer.
    Note: In Lazer mode, the minimum d is 75.
  - 2 - View Current d: Available only in single-image mode.
    Not available in directory batch mode.
  - 3 - Modify d:
    Single-image mode outputs one image.
    Directory mode applies the same d to all PNG files in that directory.
    In Normal Mode you may choose whether to add a suffix to the output filename;
    in Replace Mode the filename never changes, so no suffix is asked.
    Replace Mode shows a bold red warning that originals will be overwritten.
  - 4 - Single-Image Batch Generation:
    Only available in single-image mode.
    Input start, end, and step to generate a d list, then output one image per d.
    Step cannot be 0; for large counts there is an extra confirmation.
    In Replace Mode all generations share one backup timestamp, so the backup keeps
    only the very first original.
  - 5 - Mode Fix Tool:
    In Lazer mode, this shows "Stretch Repair" and runs Lazer normalization (fixed to 32800px).
    In Stable mode, this shows "Fix Tail White Line" and runs Stable normalization
    (crop if over 32767px and clear the last row).
  - 6 - Adjust Output Mode: Switch between Normal Mode and Replace Mode. The current
    output mode is always shown above the menu.
  - 7 - Adjust Output/Backup Folder: Choose whether to adjust the output folder or the
    backup folder, then enter a new path.
  - 8 - Switch Image: Select a new PNG or directory path.
  - 9 - Check Updates: Query latest release info from GitHub.
  - 10 - Quit: Save the config and exit the program.
  - 11 - Language/语言: Switch the interface language (中文 / English). The choice is
    saved into the config file; percy_en.exe starts in English by default.
{Color.OKCYAN}[Images Shorter Than 1000px]{Color.ENDC}
  When an image shorter than 1000px is found, the tool lists those files and asks:
  - 1 - Adjust image(s) to reach 1000px: the original is copied into the [timestamp]
    folder first, then the image is tiled vertically (copies flush, no overlap) up to
    1000px and the result replaces the original; the tool then reports
    "Originals saved to [timestamp]-height-adjustment".
  - 2 - Go back: return to the path input screen without changing anything.
{Color.OKCYAN}[Config File]{Color.ENDC}
  - The config file is {CONFIG_FILENAME} in the program working directory; it is read at
    startup and saved on exit.
  - If the file does not exist, a default config file is created at startup.
  - Defaults: output mode Normal Mode, output folder /output, backup folder /backup-archive,
    language 中文.
  - A leading / or \\ in the output/backup folder means "relative to the program directory".
{Color.OKCYAN}[Notes]{Color.ENDC}
  1. PNG only (RGBA). Background color is the top-left pixel.
  2. Height must be at least 1000px, otherwise structure detection may fail
     (the tool offers to adjust such images).
  3. In Normal Mode, output goes to the output folder with filename format:
      original-name-dpx.png       (Stable)
      original-name-dpx-lzr.png   (Lazer)
      If "no suffix" is chosen, only original-name.png is used.
     In Replace Mode the result overwrites the original and the filename is unchanged.
  4. Before using Replace Mode, make sure important files are backed up; a batch keeps
     only the very first original version.
  5. If the image structure is invalid (e.g., tail/body not found), the tool returns to menu.
  6. Gradient or patterned note bodies are not supported currently.
  7. Inputting a directory path will batch all .png files in that folder (non-recursive).
  8. If you encounter issues, open an issue on GitHub or contact the author.
{Color.BOLD}{Color.OKGREEN}======================================{Color.ENDC}
"""
    else:
        help_text = f"""
{Color.BOLD}{Color.OKGREEN}========== 帮助信息 =========={Color.ENDC}
{Color.OKCYAN}【什么是投皮】{Color.ENDC}
  • 投皮是一个将面身拉伸到上万像素长，随后通过顶部截断的方式来制造视觉上的短尾效果。
  • 在高密度LN中，玩家通常会使用投皮来获得更好的视觉反馈和操作体验。
  • 投皮往往能够大幅减轻读谱压力，但是无法精确地找到松手位置。
  • 我们约定，一个皮肤顶部截断了多少像素(即第一个非背景色像素到顶部的距离)，称为"投机取巧程度"或"投了多少像素"。
  • 在本程序中，使用 d 来代替这个值。
{Color.OKCYAN}【模式说明】{Color.ENDC}
  • Stable 模式 : 直接设置新的 d 值，程序自动移动面尾和面身。
  • Lazer 模式 : 根据我的测定，26年初的lazer版本会使皮肤错误拉伸。大致为stb+75px。
                因此，该模式下输入的任何数据都会被-75px，下限为0.
                另外，为防止过度拉伸，所有图片长度将被固定在32800px。
{Color.OKCYAN}【输出模式说明】{Color.ENDC}
  • 常规模式 : 默认模式。处理结果输出到输出文件夹（默认 /output），不改动原文件。
  • 替换模式 : 处理前先把所选原文件复制到备份文件夹（默认 /backup-archive）下的
              [备份时间戳] 子文件夹，随后用处理结果替换原文件。
              同一批处理的文件共用同一个时间戳文件夹。
              提示中的 -replaced-file / -height-adjustment 是备份原因标记，
              实际文件夹名为 [备份时间戳]。
{Color.OKCYAN}【菜单说明】{Color.ENDC}
  • ? - 帮助 : 显示本说明页（半角 ? 与全角 ？ 均可触发）。
  • 0 - 重置默认配置 : 二次确认后把输出模式、输出文件夹、备份文件夹、语言恢复为默认值，
                       需要重启程序才会生效。
  • 1 - 切换模式 : 在 Stable 和 Lazer 之间切换。注意 Lazer 模式下 d 最小为 75。
  • 2 - 查看当前投机取巧程度 : 仅单图模式可用；目录批处理模式下不可用。
  • 3 - 修改投机取巧程度 :
        单图模式会输出 1 张结果图；目录模式会对该目录下所有 PNG 进行同一 d 的批处理。
        常规模式下输入 d 值后可选择是否为输出文件名添加后缀，随后会再确认一次；
        替换模式下文件名不变，因此不再询问后缀。
        替换模式在确认前会用醒目红色警告提示将覆盖原文件。
  • 4 - 单图批量生成 :
        仅单图模式可用。输入起始值、终止值、步长生成列表后，会按其逐个生成多张图。
        步长不能为 0；若数量较多会再次提示确认。
        替换模式下多次生成共用同一个备份时间戳，备份只保留最初的原文件。
  • 5 - 模式修复功能 :
      Lazer 模式显示为“图片拉伸修复”，会执行 Lazer 标准化（固定到 32800px）。
      Stable 模式显示为“修复面尾白线”，会执行 Stable 标准化（超过 32767px 时裁切并清空末行）。
  • 6 - 调整输出模式 : 在 常规模式 与 替换模式 之间切换；菜单上方始终显示当前输出模式。
  • 7 - 调整输出/备份文件夹 : 先选择要调整“输出文件夹”还是“备份文件夹”，再输入新的文件夹路径。
  • 8 - 更换图片 : 重新选择单个 PNG 或文件夹路径。
  • 9 - 检查更新 : 从 GitHub 获取最新发布版本信息。
  • 10 - 退出 : 保存配置并关闭程序。
  • 11 - 语言/Language : 切换界面语言（中文 / English），设置会保存到配置文件。
{Color.OKCYAN}【高度小于 1000px 的图片】{Color.ENDC}
  处理到高度小于 1000px 的图片时，程序会列出这些文件名并让你选择：
  • 1 - 调整图片使其达到 1000px : 先把原文件复制到 [备份时间戳] 文件夹，再把图片纵向
        复制（副本紧贴不重叠）到 1000px，输出结果替换原文件；随后提示
        图片已成功调整，原文件已保存至 [备份时间戳]-height-adjustment。
  • 2 - 返回 : 回到文件选择输入界面，不做任何改动。
{Color.OKCYAN}【配置文件】{Color.ENDC}
  • 配置文件为程序运行目录下的 {CONFIG_FILENAME}，启动时读取、退出时保存。
  • 若该文件不存在，启动时会自动创建默认配置文件。
  • 默认值：输出模式 常规模式，输出文件夹 /output，备份文件夹 /backup-archive，语言 中文。
  • 输出文件夹、备份文件夹以 / 或 \\ 开头表示相对于程序运行目录。
{Color.OKCYAN}【注意事项】{Color.ENDC}
  1. 仅支持 PNG 图片（RGBA 模式），背景色以左上角第一个像素为准。
  2. 图片高度不得小于 1000 像素，否则可能无法正确识别结构（可按提示调整）。
  3. 常规模式输出到输出文件夹，命名格式为：
      原文件名-新d值px.png      （Stable模式）
      原文件名-新d值px-lzr.png  （Lazer 模式）
      若选择"不添加后缀"，则仅使用 原文件名.png。
     替换模式下结果直接覆盖原文件，文件名保持不变。
  4. 使用替换模式前请确认重要文件已备份；同一批次只保留最初版本的原文件。
  5. 如果原图不符合预期结构（例如找不到面尾/面身），程序会报错并返回菜单。
  6. 本程序暂不支持渐变颜色面身、非单一颜色或含有图案面身的皮肤。
  7. 输入文件夹路径时会批处理该目录下所有 .png 文件（不递归子目录）。
  8. 如果你遇到任何问题，请在GitHub仓库上提交issue或联系作者。
{Color.BOLD}{Color.OKGREEN}=============================={Color.ENDC}
"""
    print(help_text)
    input(f"{Color.WARNING}{t('按回车键返回菜单...', 'Press Enter to return to menu...')}{Color.ENDC}")



def main(default_language=DEFAULT_LANGUAGE):
    global LANG
    cfg = config(default_language)
    LANG = cfg.get("language", _entry_language(default_language))
    clear_screen()
    print(f"{Color.BOLD}{Color.HEADER}osu!mania {t('投皮调整工具', 'Percy Skin Editor')} - v{VERSION}{Color.ENDC}")
    print(f"{Color.BOLD}{Color.HEADER}{t('作者: Leo_Black', 'Author: Leo_Black')}{Color.ENDC}")
    print(f"{Color.BOLD}{Color.HEADER}Github: LeoBlackMT/percy_skin_editor{Color.ENDC}")
    print(f"{Color.OKGREEN}{t('配置文件: ', 'Config file: ')}{Color.BOLD}{get_config_path()}{Color.ENDC}")
    current_image_path = None
    current_targets = []
    current_source_type = "file"
    current_mode = "stable"

    while True:
        if current_image_path is None:
            print(f"\n\n{Color.OKCYAN}{t('[提示: 如何找到面身文件]', '[Tip: How to locate note body files]')}{Color.ENDC}")
            print(t("\n对于Stable:\n游戏设置 - 皮肤 - 打开皮肤文件夹 - 找到skin.ini - 找到你想修改的key数(如Keys: 4) - 找到NoteImage*L,*是轨道序号 - 其对应的目录就是图片路径",
                    "\nFor Stable:\nGame Settings -> Skin -> Open Skin Folder -> find skin.ini -> find target key count (e.g. Keys: 4) -> find NoteImage*L (* is lane index) -> the referenced path is your image path"))
            print(t("\n对于Lazer:\n游戏设置 - 皮肤 - 打开皮肤编辑器 - 左上角文件 - 打开外部编辑 - 找到skin.ini -> 后续与Stable相同",
                    "\nFor Lazer:\nGame Settings -> Skin -> Open Skin Editor -> top-left File -> Open External Editor -> find skin.ini -> then same process as Stable"))
            print(t("\n如果未在skin.ini中找到NoteImage*L, 那么图片应该直接在皮肤目录下，名称为mania-note*L.png\n",
                    "\nIf NoteImage*L is not in skin.ini, image files are usually in skin root as mania-note*L.png\n"))
            print(t("\n你可以随时使用 Ctrl+C 退出程序。\n",
                    "\nYou can press Ctrl+C to exit at any time.\n"))
            print(f"\n{Color.OKBLUE}{t('请输入图片或文件夹绝对/相对路径（或直接拖拽，输入 q 退出）:', 'Enter an absolute/relative image or directory path (or drag-and-drop path, q to quit):')}{Color.ENDC}")
            path = input().strip()
            if path.lower() == 'q':
                break
            path = normalize_input_path(path)
            try:
                targets, source_type = collect_png_targets(path)
                if source_type == "dir":
                    if not confirm_action(t(f"警告: 检测到文件夹，将批处理该目录下 {len(targets)} 个 .png 文件。是否继续？",
                                            f"Warning: directory detected. {len(targets)} .png files will be batch processed. Continue?")):
                        clear_screen()
                        continue
                undersized = find_undersized(targets)
            except Exception as e:
                print(f"{Color.FAIL}{e}{Color.ENDC}")
                continue
            if undersized:
                if not handle_undersized(undersized):
                    clear_screen()
                    continue
            current_image_path = path
            current_targets = targets
            current_source_type = source_type
            
        clear_screen()
        if current_source_type == "dir":
            print(f"\n{Color.OKGREEN}{t('当前目录: ', 'Current directory: ')}{Color.BOLD}{current_image_path}{Color.ENDC}")
            print(f"{Color.OKGREEN}{t('待处理图片数量: ', 'PNG files to process: ')}{Color.BOLD}{len(current_targets)}{Color.ENDC}")
        else:
            print(f"\n{Color.OKGREEN}{t('当前图片: ', 'Current image: ')}{Color.BOLD}{current_image_path}{Color.ENDC}")
        mode_label = "Stable" if current_mode == "stable" else "Lazer"
        current_output_mode = config().get("output_mode", OUTPUT_MODE_NORMAL)
        out_mode_label = output_mode_label(current_output_mode)
        print(f"{Color.OKGREEN}{t('当前模式: ', 'Current mode: ')}{Color.BOLD}{mode_label}{Color.ENDC}")
        if current_output_mode == OUTPUT_MODE_REPLACE:
            print(f"{Color.BOLD}{Color.FAIL}{t('当前输出模式: ', 'Current output mode: ')}{out_mode_label}{Color.ENDC}")
        else:
            print(f"{Color.OKGREEN}{t('当前输出模式: ', 'Current output mode: ')}{Color.BOLD}{out_mode_label}{Color.ENDC}")
        print(f"{Color.OKCYAN}{t('请选择操作:', 'Select an action:')}{Color.ENDC}")
        print("  {0} - {1}".format(Color.WARNING + "?" + Color.ENDC, t("帮助", "Help")))
        print("  {0} - {1}".format(Color.WARNING + "0" + Color.ENDC, t("重置默认配置", "Reset default config")))
        print("  {0} - {1}".format(Color.OKBLUE + "1" + Color.ENDC, t("切换模式", "Switch mode")))
        print("  {0} - {1}".format(Color.OKBLUE + "2" + Color.ENDC, t("查看当前投机取巧程度", "View current d")))
        print("  {0} - {1}".format(Color.OKBLUE + "3" + Color.ENDC, t("修改投机取巧程度", "Modify d")))
        print("  {0} - {1}".format(Color.OKBLUE + "4" + Color.ENDC, t("单图批量生成", "Single-image batch generation")))
        if current_mode == "lazer":
            fix_label = t("图片拉伸修复", "Stretch Repair")
        else:
            fix_label = t("修复面尾白线", "Fix Tail White Line")
        print("  {0} - {1}".format(Color.OKBLUE + "5" + Color.ENDC, fix_label))
        print("  {0} - {1}".format(Color.OKBLUE + "6" + Color.ENDC, t("调整输出模式", "Adjust output mode")))
        print("  {0} - {1}".format(Color.OKBLUE + "7" + Color.ENDC, t("调整输出/备份文件夹", "Adjust output/backup folder")))
        print("  {0} - {1}".format(Color.OKBLUE + "8" + Color.ENDC, t("更换图片", "Switch image")))
        print("  {0} - {1}".format(Color.OKBLUE + "9" + Color.ENDC, t("检查更新", "Check updates")))
        print("  {0} - {1}".format(Color.OKBLUE + "10" + Color.ENDC, t("退出", "Quit")))
        print("  {0} - {1}".format(Color.OKBLUE + "11" + Color.ENDC, t("语言 / Language", "Language / 语言")))
        print("> ", end='', flush=True)

        choice = input().strip()

        if choice in ('?', '？'):
            clear_screen()
            print_help()
            clear_screen()
        elif choice == '0':
            print(f"\n{Color.WARNING}{t('重置默认配置将恢复以下默认值:', 'Resetting restores these defaults:')}{Color.ENDC}")
            print(f"  {t('输出模式  ', 'Output mode  ')}: {output_mode_label(OUTPUT_MODE_NORMAL)}")
            print(f"  {t('输出文件夹', 'Output folder')}: {DEFAULT_CONFIG['output_dir']}")
            print(f"  {t('备份文件夹', 'Backup folder')}: {DEFAULT_CONFIG['backup_dir']}")
            print(f"  {t('语言      ', 'Language     ')}: {language_label(_entry_language(default_language))}")
            if not confirm_action(t("确认重置默认配置？", "Reset to default config?")):
                clear_screen()
                continue
            reset_default_config(default_language)
            print(f"{Color.OKGREEN}{t('配置已重置为默认值。', 'Config has been reset to defaults.')}{Color.ENDC}")
            print(f"{Color.WARNING}{t('请重启程序以使新配置生效。', 'Please restart the program for it to take effect.')}{Color.ENDC}")
            input(t("按回车键继续...", "Press Enter to continue..."))
            clear_screen()
        elif choice == '1':
            current_mode = "lazer" if current_mode == "stable" else "stable"
            switched_label = "Stable" if current_mode == "stable" else "Lazer"
            print(f"\n{Color.OKGREEN}{t('已切换到 ', 'Switched to ')}{switched_label}{t(' 模式。', ' mode.')}{Color.ENDC}")
            input(t("按回车键继续...", "Press Enter to continue..."))
            clear_screen()
        elif choice == '2':
            if current_source_type == "dir":
                print(f"\n{Color.WARNING}{t('当前为目录批处理模式，无法显示单个 d。请切换为单图或直接执行处理。', 'Current target is a directory batch, so a single d cannot be shown. Switch to a single image or process directly.')}{Color.ENDC}")
                input(t("按回车键继续...", "Press Enter to continue..."))
                clear_screen()
                continue
            try:
                d = get_current_d(current_image_path)
                if current_mode == "lazer":
                    d += 75
                print(f"\n{Color.OKGREEN}{t('当前投机取巧程度 d = ', 'Current d = ')}{d}{t('px（', 'px (')}{mode_label}{t('）', ')')}{Color.ENDC}")
            except Exception as e:
                print(f"\n{Color.FAIL}{t('获取 d 失败: ', 'Failed to read current d: ')}{e}{Color.ENDC}")
            input(t("按回车键继续...", "Press Enter to continue..."))
            clear_screen()
        elif choice == '3':
            if current_mode == "lazer":
                prompt = t("请输入新的 d 值 (整数, 最小值为75): ", "Enter new d (integer, minimum 75): ")
            else:
                prompt = t("请输入新的 d 值 (整数): ", "Enter new d (integer): ")
            print(f"\n{Color.OKBLUE}{prompt}{Color.ENDC}", end='', flush=True)
            try:
                new_d_str = input().strip()
                new_d = int(new_d_str)
            except ValueError:
                print(f"{Color.FAIL}{t('输入无效，请输入整数。', 'Invalid input. Please enter an integer.')}{Color.ENDC}")
                input(t("按回车键继续...", "Press Enter to continue..."))
                clear_screen()
                continue
            if current_mode == "lazer" and new_d < 75:
                print(f"{Color.FAIL}{t('Lazer 模式下 d 的最小值为 75。', 'Minimum d in Lazer mode is 75.')}{Color.ENDC}")
                input(t("按回车键继续...", "Press Enter to continue..."))
                clear_screen()
                continue

            active_mode = config().get("output_mode", OUTPUT_MODE_NORMAL)
            add_suffix = True
            if active_mode == OUTPUT_MODE_REPLACE:
                print(f"\n{Color.OKBLUE}{t('替换模式下输出文件名与原文件保持一致，无需选择后缀。', 'In Replace Mode the output filename stays the same, so no suffix is needed.')}{Color.ENDC}")
            else:
                print(f"\n{Color.OKBLUE}{t('是否为输出文件名添加后缀？（后缀格式: -新d值px[-模式]）', 'Add a suffix to the output filename? (suffix format: -dpx[-mode])')}{Color.ENDC}")
                print(t("  1 - 添加后缀（原文件名-新d值px-模式）", "  1 - Add suffix (original-name-dpx-mode)"))
                print(t("  2 - 不添加后缀（仅原文件名）", "  2 - No suffix (original name only)"))
                print("> ", end='', flush=True)
                suffix_choice = input().strip()
                if suffix_choice == '1':
                    add_suffix = True
                elif suffix_choice == '2':
                    add_suffix = False
                else:
                    print(f"{Color.FAIL}{t('输入无效，请输入 1 或 2。', 'Invalid input. Please enter 1 or 2.')}{Color.ENDC}")
                    input(t("按回车键继续...", "Press Enter to continue..."))
                    clear_screen()
                    continue

            timestamp = None
            if active_mode == OUTPUT_MODE_REPLACE:
                timestamp = make_timestamp()
                print(f"\n{Color.BOLD}{Color.FAIL}{t('！！！ 警告: 当前为【替换模式】，处理结果将直接覆盖所选原文件 ！！！', '!!! WARNING: Replace Mode is active - results will overwrite the selected original files !!!')}{Color.ENDC}")
                print(f"{Color.FAIL}{t('原文件会先备份到: ', 'Originals are backed up to: ')}{os.path.join(get_backup_root(), timestamp)}{Color.ENDC}")
                print(f"{Color.FAIL}{t('若不希望覆盖原文件，请先返回菜单选择 6 - 调整输出模式。', 'To avoid overwriting, go back and choose 6 - Adjust output mode first.')}{Color.ENDC}")
                confirm_prompt = t(f"确认替换 {len(current_targets)} 张原文件？",
                                   f"Replace {len(current_targets)} original file(s)?")
            else:
                suffix_label = t("添加后缀", "with suffix") if add_suffix else t("不添加后缀", "without suffix")
                if current_source_type == "dir":
                    confirm_prompt = t(f"警告: 即将处理 {len(current_targets)} 张图片（{suffix_label}），输出到 {get_output_dir()}。是否继续？",
                                       f"Warning: {len(current_targets)} images will be processed ({suffix_label}) and saved into {get_output_dir()}. Continue?")
                else:
                    confirm_prompt = t(f"即将处理 1 张图片（{suffix_label}），输出到 {get_output_dir()}。是否继续？",
                                       f"1 image will be processed ({suffix_label}) and saved into {get_output_dir()}. Continue?")
            if not confirm_action(confirm_prompt):
                clear_screen()
                continue

            try:
                success, failed, errors, last_output_path = process_targets(
                    current_targets,
                    new_d,
                    lzr=(current_mode == "lazer"),
                    suffix=add_suffix,
                    mode=active_mode,
                    timestamp=timestamp
                )

                if active_mode == OUTPUT_MODE_REPLACE:
                    backup_label = os.path.join(get_backup_root(), f"{timestamp}-replaced-file")
                    if failed == 0:
                        print(f"{Color.OKGREEN}{t('替换完成，共 ', 'Replaced ')}{success}{t(' 张。原文件已保存至 ', ' file(s). Originals saved to ')}{backup_label}{Color.ENDC}")
                    else:
                        print(f"{Color.WARNING}{t('替换结束：成功 ', 'Replace finished with partial failures: success ')}{success}{t(' 张，失败 ', ', failed ')}{failed}{t(' 张。', '.')}{Color.ENDC}")
                        for src, err in errors:
                            print(f"{Color.FAIL}{t('失败: ', 'Failed: ')}{src} -> {err}{Color.ENDC}")
                        print(f"{Color.OKGREEN}{t('原文件已保存至 ', 'Originals saved to ')}{backup_label}{Color.ENDC}")
                elif failed == 0:
                    if success == 1:
                        print(f"{Color.OKGREEN}{t('处理完成，已保存至: ', 'Done. Saved to: ')}{last_output_path}{Color.ENDC}")
                    else:
                        print(f"{Color.OKGREEN}{t('处理完成，共成功 ', 'Done. ')}{success}{t(' 张。输出目录: ', ' images processed successfully. Output directory: ')}{get_output_dir()}{Color.ENDC}")
                else:
                    print(f"{Color.WARNING}{t('处理结束：成功 ', 'Finished with partial failures: success ')}{success}{t(' 张，失败 ', ', failed ')}{failed}{t(' 张。', '.')}{Color.ENDC}")
                    for src, err in errors:
                        print(f"{Color.FAIL}{t('失败: ', 'Failed: ')}{src} -> {err}{Color.ENDC}")
                    print(f"{Color.OKGREEN}{t('成功输出目录: ', 'Successful outputs are in: ')}{get_output_dir()}{Color.ENDC}")
            except Exception as e:
                print(f"{Color.FAIL}{t('处理失败: ', 'Processing failed: ')}{e}{Color.ENDC}")
            input(t("按回车键继续...", "Press Enter to continue..."))
            clear_screen()
        elif choice == '4':
            if current_source_type != "file":
                print(f"{Color.FAIL}{t('该功能仅支持单个图片。请先选择单图。', 'This feature supports only a single image target. Please switch image first.')}{Color.ENDC}")
                input(t("按回车键继续...", "Press Enter to continue..."))
                clear_screen()
                continue

            print(f"\n{Color.OKBLUE}{t('请输入起始值（非负整数）:', 'Enter start value (non-negative integer):')}{Color.ENDC}", end='', flush=True)
            start_str = input().strip()
            print(f"{Color.OKBLUE}{t('请输入终止值（非负整数）:', 'Enter end value (non-negative integer):')}{Color.ENDC}", end='', flush=True)
            end_str = input().strip()
            print(f"{Color.OKBLUE}{t('请输入步长（非负整数，且不能为0）:', 'Enter step (non-negative integer, must not be 0):')}{Color.ENDC}", end='', flush=True)
            step_str = input().strip()

            try:
                start_value = int(start_str)
                end_value = int(end_str)
                step = int(step_str)
                if start_value < 0 or end_value < 0 or step < 0:
                    raise LNImageError(t("起始值、终止值、步长必须都是非负整数。", "Start, end, and step must all be non-negative integers."))
                if step == 0:
                    raise LNImageError(t("步长不能为 0。", "Step cannot be 0."))
                d_values = build_d_values(start_value, end_value, step)
                if not d_values:
                    raise LNImageError(t("生成列表为空，请检查参数。", "Generated list is empty. Please check your inputs."))
                if current_mode == "lazer" and min(d_values) < 75:
                    raise LNImageError(t("Lazer 模式下 d 的最小值为 75。", "Minimum d in Lazer mode is 75."))
            except Exception as e:
                print(f"{Color.FAIL}{t('输入无效: ', 'Invalid input: ')}{e}{Color.ENDC}")
                input(t("按回车键继续...", "Press Enter to continue..."))
                clear_screen()
                continue

            total = len(d_values)
            active_mode = config().get("output_mode", OUTPUT_MODE_NORMAL)
            batch_timestamp = make_timestamp() if active_mode == OUTPUT_MODE_REPLACE else None
            print(f"{Color.OKCYAN}{t('本次将使用列表: ', 'This run will use d list: ')}{d_values}{Color.ENDC}")
            if active_mode == OUTPUT_MODE_REPLACE:
                print(f"{Color.BOLD}{Color.FAIL}{t('！！！ 警告: 当前为【替换模式】，本次生成的结果会覆盖原文件 ！！！', '!!! WARNING: Replace Mode is active - these results will overwrite the original file !!!')}{Color.ENDC}")
                print(f"{Color.FAIL}{t('文件名保持不变；每张结果会覆盖上一张结果，备份只保留最初的原文件。', 'The filename stays the same; each result overwrites the previous one, and the backup keeps only the first original.')}{Color.ENDC}")
                print(f"{Color.FAIL}{t('备份位置: ', 'Backup location: ')}{os.path.join(get_backup_root(), batch_timestamp)}{Color.ENDC}")
            if not confirm_action(t(f"警告: 将基于当前单图生成 {total} 张结果图。是否继续？",
                                   f"Warning: {total} images will be generated from the current source image. Continue?")):
                clear_screen()
                continue
            if total > 10:
                if not confirm_action(t(f"再次警告: 本次将生成 {total} 张图片，可能需要一些时间。是否继续？",
                                       f"Warning again: this will generate {total} images and may take time. Continue?")):
                    clear_screen()
                    continue

            success = 0
            failed = 0
            errors = []
            for d_value in d_values:
                s, f, err_list, _ = process_targets(
                    current_targets,
                    d_value,
                    lzr=(current_mode == "lazer"),
                    mode=active_mode,
                    timestamp=batch_timestamp
                )
                success += s
                failed += f
                errors.extend(err_list)

            backup_label = os.path.join(get_backup_root(), f"{batch_timestamp}-replaced-file")
            if failed == 0:
                if active_mode == OUTPUT_MODE_REPLACE:
                    print(f"{Color.OKGREEN}{t('批量生成完成，共 ', 'Batch generation completed. ')}{success}{t(' 张。原文件已保存至 ', ' result(s) written. Originals saved to ')}{backup_label}{Color.ENDC}")
                else:
                    print(f"{Color.OKGREEN}{t('批量生成完成，共成功 ', 'Batch generation completed. Successful outputs: ')}{success}{t(' 张。输出目录: ', '. Output directory: ')}{get_output_dir()}{Color.ENDC}")
            else:
                print(f"{Color.WARNING}{t('批量生成结束：成功 ', 'Batch generation completed with partial failures: success ')}{success}{t(' 张，失败 ', ', failed ')}{failed}{t(' 张。', '.')}{Color.ENDC}")
                for src, err in errors:
                    print(f"{Color.FAIL}{t('失败: ', 'Failed: ')}{src} -> {err}{Color.ENDC}")
                if active_mode == OUTPUT_MODE_REPLACE:
                    print(f"{Color.OKGREEN}{t('原文件备份位置: ', 'Originals saved to ')}{backup_label}{Color.ENDC}")
                else:
                    print(f"{Color.OKGREEN}{t('已成功输出部分结果到: ', 'Successful outputs are in: ')}{get_output_dir()}{Color.ENDC}")

            input(t("按回车键继续...", "Press Enter to continue..."))
            clear_screen()
        elif choice == '5':
            if current_mode == "lazer":
                fix_label = t("图片拉伸修复", "Stretch Repair")
                mode_is_lazer = True
            else:
                fix_label = t("修复面尾白线", "Fix Tail White Line")
                mode_is_lazer = False

            active_mode = config().get("output_mode", OUTPUT_MODE_NORMAL)
            fix_timestamp = make_timestamp() if active_mode == OUTPUT_MODE_REPLACE else None

            if active_mode == OUTPUT_MODE_REPLACE:
                print(f"\n{Color.BOLD}{Color.FAIL}{t('！！！ 警告: 当前为【替换模式】，“', '!!! WARNING: Replace Mode is active - "')}{fix_label}{t('”结果将覆盖所选原文件 ！！！', '" will overwrite the selected original files !!!')}{Color.ENDC}")
                print(f"{Color.FAIL}{t('原文件会先备份到: ', 'Originals are backed up to: ')}{os.path.join(get_backup_root(), fix_timestamp)}{Color.ENDC}")
                if not confirm_action(t(f"确认对 {len(current_targets)} 张原文件执行“{fix_label}”并替换？",
                                       f"Run '{fix_label}' on {len(current_targets)} original file(s) and replace them?")):
                    clear_screen()
                    continue
            elif current_source_type == "dir":
                if not confirm_action(t(f"警告: 即将对 {len(current_targets)} 张图片执行“{fix_label}”，输出到 {get_output_dir()}。是否继续？",
                                       f"Warning: {len(current_targets)} images will run '{fix_label}' and be saved to {get_output_dir()}. Continue?")):
                    clear_screen()
                    continue

            try:
                success, failed, errors, last_output_path = process_normalize_targets(
                    current_targets,
                    lzr=mode_is_lazer,
                    mode=active_mode,
                    timestamp=fix_timestamp
                )

                backup_label = os.path.join(get_backup_root(), f"{fix_timestamp}-replaced-file")
                if active_mode == OUTPUT_MODE_REPLACE:
                    if failed == 0:
                        print(f"{Color.OKGREEN}{fix_label}{t('完成，共 ', ' completed on ')}{success}{t(' 张。原文件已保存至 ', ' file(s). Originals saved to ')}{backup_label}{Color.ENDC}")
                    else:
                        print(f"{Color.WARNING}{fix_label}{t('结束：成功 ', ' finished with partial failures: success ')}{success}{t(' 张，失败 ', ', failed ')}{failed}{t(' 张。', '.')}{Color.ENDC}")
                        for src, err in errors:
                            print(f"{Color.FAIL}{t('失败: ', 'Failed: ')}{src} -> {err}{Color.ENDC}")
                        print(f"{Color.OKGREEN}{t('原文件已保存至 ', 'Originals saved to ')}{backup_label}{Color.ENDC}")
                elif failed == 0:
                    if success == 1:
                        print(f"{Color.OKGREEN}{fix_label}{t('完成，已保存至: ', ' completed. Saved to: ')}{last_output_path}{Color.ENDC}")
                    else:
                        print(f"{Color.OKGREEN}{fix_label}{t('完成，共成功 ', ' completed. Successful: ')}{success}{t(' 张。输出目录: ', '. Output directory: ')}{get_output_dir()}{Color.ENDC}")
                else:
                    print(f"{Color.WARNING}{fix_label}{t('结束：成功 ', ' finished with partial failures: success ')}{success}{t(' 张，失败 ', ', failed ')}{failed}{t(' 张。', '.')}{Color.ENDC}")
                    for src, err in errors:
                        print(f"{Color.FAIL}{t('失败: ', 'Failed: ')}{src} -> {err}{Color.ENDC}")
                    print(f"{Color.OKGREEN}{t('成功输出目录: ', 'Successful outputs are in: ')}{get_output_dir()}{Color.ENDC}")
            except Exception as e:
                print(f"{Color.FAIL}{fix_label}{t('失败: ', ' failed: ')}{e}{Color.ENDC}")
            input(t("按回车键继续...", "Press Enter to continue..."))
            clear_screen()
        elif choice == '6':
            active_mode = config().get("output_mode", OUTPUT_MODE_NORMAL)
            print(f"\n{Color.OKCYAN}{t('【输出模式说明】', '[Output Mode Explanation]')}{Color.ENDC}")
            print(t("  1 - 常规模式 : 处理结果输出到输出文件夹，不改动原文件。",
                    "  1 - Normal Mode : results are written to the output folder; originals are untouched."))
            print(t("  2 - 替换模式 : 处理前先把原文件备份到备份文件夹下的 [备份时间戳] 子文件夹，",
                    "  2 - Replace Mode: originals are copied into the backup folder under a [timestamp]"))
            print(t("                随后用处理结果替换原文件。",
                    "                    subfolder first, then results replace the original files."))
            print(f"\n{t('当前输出模式: ', 'Current output mode: ')}{Color.BOLD}{output_mode_label(active_mode)}{Color.ENDC}")
            print(t("请选择 (1/2): ", "Select (1/2): "), end='', flush=True)
            ans = input().strip()
            if ans == '1':
                new_mode = OUTPUT_MODE_NORMAL
            elif ans == '2':
                new_mode = OUTPUT_MODE_REPLACE
            else:
                print(f"{Color.FAIL}{t('输入无效，请输入 1 或 2。', 'Invalid input. Please enter 1 or 2.')}{Color.ENDC}")
                input(t("按回车键继续...", "Press Enter to continue..."))
                clear_screen()
                continue
            cfg_now = config()
            cfg_now["output_mode"] = new_mode
            save_config(cfg_now)
            print(f"{Color.OKGREEN}{t('输出模式已切换为: ', 'Output mode switched to: ')}{output_mode_label(new_mode)}{Color.ENDC}")
            if new_mode == OUTPUT_MODE_REPLACE:
                print(f"{Color.FAIL}{t('注意: 替换模式会覆盖原文件，原文件将备份到 ', 'Note: Replace Mode overwrites originals; they are backed up to ')}{get_backup_root()}{Color.ENDC}")
            else:
                print(f"{Color.OKGREEN}{t('处理结果将输出到: ', 'Results will be written to: ')}{get_output_dir()}{Color.ENDC}")
            input(t("按回车键继续...", "Press Enter to continue..."))
            clear_screen()
        elif choice == '7':
            cfg_now = config()
            print(f"\n{Color.OKBLUE}{t('请选择要调整的文件夹:', 'Choose which folder to adjust:')}{Color.ENDC}")
            print(f"  1 - {t('输出文件夹', 'Output folder')} ({t('当前', 'current')}: {cfg_now.get('output_dir')} -> {resolve_dir(cfg_now.get('output_dir'))})")
            print(f"  2 - {t('备份文件夹', 'Backup folder')} ({t('当前', 'current')}: {cfg_now.get('backup_dir')} -> {resolve_dir(cfg_now.get('backup_dir'))})")
            print("> ", end='', flush=True)
            sel = input().strip()
            if sel == '1':
                folder_key = 'output_dir'
                folder_label = t('输出文件夹', 'Output folder')
            elif sel == '2':
                folder_key = 'backup_dir'
                folder_label = t('备份文件夹', 'Backup folder')
            else:
                print(f"{Color.FAIL}{t('输入无效，请输入 1 或 2。', 'Invalid input. Please enter 1 or 2.')}{Color.ENDC}")
                input(t("按回车键继续...", "Press Enter to continue..."))
                clear_screen()
                continue
            print(f"{Color.OKBLUE}{t('请输入新的', 'Enter the new ')}{folder_label}{t('路径（以 / 开头表示相对程序运行目录，留空取消）:', ' path (a leading / means relative to the program directory, empty cancels):')}{Color.ENDC}", end='', flush=True)
            new_folder = normalize_input_path(input().strip())
            if not new_folder:
                print(f"{Color.WARNING}{t('已取消，未做修改。', 'Cancelled. Nothing was changed.')}{Color.ENDC}")
                input(t("按回车键继续...", "Press Enter to continue..."))
                clear_screen()
                continue
            cfg_now[folder_key] = new_folder
            save_config(cfg_now)
            print(f"{Color.OKGREEN}{folder_label}{t('已更新为: ', ' updated to: ')}{new_folder}{Color.ENDC}")
            print(f"{Color.OKGREEN}{t('实际路径: ', 'Resolved path: ')}{resolve_dir(new_folder)}{Color.ENDC}")
            input(t("按回车键继续...", "Press Enter to continue..."))
            clear_screen()
        elif choice == '8':
            current_image_path = None
            current_targets = []
            current_source_type = "file"
            clear_screen()
        elif choice == '9':
            print(f"\n{Color.OKBLUE}{t('正在检查更新...', 'Checking for updates...')}{Color.ENDC}")
            has, latest = check_update(VERSION)
            if not latest:
                print(f"{Color.FAIL}{t('错误: 无法获取最新版本信息。', 'Error: Unable to fetch latest version information.')}{Color.ENDC}")
            else:
                if has:
                    print(f"{Color.OKGREEN}{t('检测到新版本：', 'New version detected: ')}{latest}{t('（当前：', ' (current: ')}{VERSION}{t('）', ')')}{Color.ENDC}")
                    print(f"{t('请访问发布页面下载最新版本： ', 'Please visit releases page: ')}https://github.com/{_OWNER}/{_REPO}/releases/latest")
                else:
                    print(f"{Color.OKGREEN}{t('已是最新版本：', 'You are already on the latest version: ')}{VERSION}{Color.ENDC}")
            input(t("按回车键继续...", "Press Enter to continue..."))
            clear_screen()
        elif choice == '10':
            save_config(config())
            print(f"{Color.OKGREEN}{t('配置已保存，程序退出。', 'Config saved. Program exited.')}{Color.ENDC}")
            break
        elif choice == '11':
            current_lang = config().get("language", DEFAULT_LANGUAGE)
            print(f"\n{Color.OKCYAN}{t('【语言 / Language】', '[Language / 语言]')}{Color.ENDC}")
            print("  1 - 中文")
            print("  2 - English")
            print(f"{t('当前语言: ', 'Current language: ')}{Color.BOLD}{language_label(current_lang)}{Color.ENDC}")
            print("> ", end='', flush=True)
            sel = input().strip()
            if sel == '1':
                new_lang = "zh"
            elif sel == '2':
                new_lang = "en"
            else:
                print(f"{Color.FAIL}{t('输入无效，请输入 1 或 2。', 'Invalid input. Please enter 1 or 2.')}{Color.ENDC}")
                input(t("按回车键继续...", "Press Enter to continue..."))
                clear_screen()
                continue
            cfg_now = config()
            cfg_now["language"] = new_lang
            save_config(cfg_now)
            LANG = new_lang
            print(f"{Color.OKGREEN}{t('语言已切换为: ', 'Language switched to: ')}{language_label(new_lang)}{Color.ENDC}")
            print(f"{Color.OKGREEN}{t('界面已即时生效，并已保存到配置文件。', 'The interface takes effect immediately and the choice was saved to the config file.')}{Color.ENDC}")
            input(t("按回车键继续...", "Press Enter to continue..."))
            clear_screen()
        else:
            print(f"{Color.WARNING}{t('无效选项，请重试。', 'Invalid option. Please try again.')}{Color.ENDC}")
            input(t("按回车键继续...", "Press Enter to continue..."))
            clear_screen()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Color.WARNING}{t('用户中断，程序退出。', 'Interrupted by user. Program exited.')}{Color.ENDC}")
    finally:
        # 应用关闭时保存配置
        try:
            if _CONFIG is not None:
                save_config(_CONFIG)
        except Exception:
            pass