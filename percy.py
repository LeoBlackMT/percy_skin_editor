import json
import os
import re
import shutil
import sys
from datetime import datetime

import requests
from packaging.version import parse as parse_version
from PIL import Image

VERSION = "1.5.0"

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


def detect_system_language():
    """还没有配置文件时，按系统界面语言决定默认语言。

    之后一律以配置文件为准；用户也可以用菜单 L 随时切换。
    """
    if os.name == 'nt':
        try:
            import ctypes
            # 主语言 ID 位于低 10 位；0x04 表示中文（简体/繁体均属此主语言）
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "zh" if (lang_id & 0x3FF) == 0x04 else "en"
        except Exception:
            return DEFAULT_LANGUAGE
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return "zh" if value.lower().startswith("zh") else "en"
    return DEFAULT_LANGUAGE

# ---------------- 配置持久化 ----------------

CONFIG_FILENAME = "percy_config.json"

OUTPUT_MODE_NORMAL = "normal"
OUTPUT_MODE_REPLACE = "replace"

MIN_IMAGE_HEIGHT = 1000

DEFAULT_CONFIG = {
    "output_mode": OUTPUT_MODE_NORMAL,
    # /output 这种带前导斜杠的写法是「相对程序目录」的约定，只有 Windows 适用；
    # 在 POSIX 上 /output 会被当成根目录下的绝对路径，所以改用相对目录名。
    "output_dir": "/output" if os.name == "nt" else "output",
    "backup_dir": "/backup-archive" if os.name == "nt" else "backup-archive",
    "language": DEFAULT_LANGUAGE,
}

_CONFIG = None


def get_base_dir():
    """程序运行目录：配置文件与默认输出/备份目录的基准。

    冻结成 exe 时取 exe 所在目录，直接跑源码时取脚本所在目录。
    这样从任意工作目录启动都能读到同一份配置，设置才能跨启动留存。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


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


def load_config():
    """读取配置；若程序运行目录下不存在配置文件则自动创建默认配置文件。"""
    cfg = default_config()
    cfg["language"] = detect_system_language()
    path = get_config_path()
    if not os.path.isfile(path):
        save_config(cfg)
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # 配置损坏时先保留一份 .bak，避免用户的设置被无痕清空
        try:
            os.replace(path, path + ".bak")
        except OSError:
            pass
        save_config(cfg)
        return cfg
    if isinstance(data, dict):
        for key in cfg:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                cfg[key] = value.strip()
    else:
        # 能解析成 JSON 但不是对象（数组 / 字符串 / 数字）：同样先留一份 .bak，
        # 否则退出时写回默认配置会把用户原来的内容静默覆盖掉。
        try:
            os.replace(path, path + ".bak")
        except OSError:
            pass
        save_config(cfg)
        return cfg
    if cfg["output_mode"] not in (OUTPUT_MODE_NORMAL, OUTPUT_MODE_REPLACE):
        cfg["output_mode"] = OUTPUT_MODE_NORMAL
    if cfg["language"] not in LANGUAGES:
        cfg["language"] = detect_system_language()
    return cfg


def config():
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_config()
    return _CONFIG


def set_config(cfg):
    global _CONFIG
    _CONFIG = cfg


def reset_default_config():
    """重置为默认配置并立即写回配置文件。"""
    cfg = default_config()
    cfg["language"] = detect_system_language()
    save_config(cfg)
    set_config(cfg)
    return cfg


def output_mode_label(mode=None):
    if mode is None:
        mode = config().get("output_mode", OUTPUT_MODE_NORMAL)
    return t("替换模式", "Replace Mode") if mode == OUTPUT_MODE_REPLACE else t("常规模式", "Normal Mode")


def resolve_dir(path):
    """解析目录配置。

    单个前导 / 或 \\ 表示相对程序所在目录 —— 这是本程序的约定，只在 Windows 上
    成立（那里 "/output" 不是有效的绝对路径）。其他平台上 / 开头就是普通的绝对
    路径，不能再改写，否则 /home/me/out 会被悄悄变成 <程序目录>/home/me/out。
    """
    if not path or not str(path).strip():
        return get_base_dir()
    p = str(path).strip()
    if os.name == "nt" and len(p) > 1 and p[0] in "/\\" and p[1] not in "/\\":
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


_USED_TIMESTAMPS = set()


def make_timestamp():
    """批次备份文件夹名。

    精确到微秒：只用秒级精度时，同一秒内的两次替换会落进同一个文件夹，而
    backup_file 是「目标已存在就跳过」，于是第二次被覆盖的那一版不会留下备份。
    批次内的文件仍然共用一个时间戳（整个批次只调用一次）。

    有些平台 datetime.now() 的时钟粒度较粗，可能连续返回同一个值，所以再记一份
    本进程已用过的名字兜底。
    """
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    if stamp in _USED_TIMESTAMPS:
        base = stamp
        seq = 2
        while stamp in _USED_TIMESTAMPS:
            stamp = "%s-%d" % (base, seq)
            seq += 1
    _USED_TIMESTAMPS.add(stamp)
    return stamp


def backup_dir_for(timestamp):
    d = os.path.join(get_backup_root(), timestamp)
    os.makedirs(d, exist_ok=True)
    return d


def backup_path_for(src, timestamp):
    """src 在 备份根/[备份时间戳]/ 下对应的备份文件路径。"""
    return os.path.join(backup_dir_for(timestamp), os.path.basename(src))


def backup_file(src, timestamp):
    """把原文件复制到 备份根/[备份时间戳]/ 下，返回备份文件路径。

    同一批次内若目标已存在则不重复覆盖，保证一批备份只保留最初的原文件；
    因此返回值在整个批次里始终指向最初的原文件。
    """
    target = backup_path_for(src, timestamp)
    if not os.path.exists(target):
        shutil.copy2(src, target)
    return target

def _read_key_from_pipe():
    """标准输入被重定向时，按行读取并取首个字符。

    空行返回 ''，与"直接回车"语义一致，便于脚本化驱动与自动化测试。
    输入耗尽时抛出 EOFError（与 input() 行为一致），避免菜单空转。
    """
    line = sys.stdin.readline()
    if not line:
        raise EOFError("standard input exhausted")
    line = line.rstrip('\r\n')
    return line[0] if line else ''

def read_key():
    """读取单个按键，不等待回车；按回车返回 ''。

    Windows 下使用 msvcrt.getwch()，它按字符（而非字节）读取，
    因此全角 "？" 也能被正确识别，不需要整行输入。
    """
    if os.name == 'nt':
        import msvcrt
        if sys.stdin is not None and not sys.stdin.isatty():
            return _read_key_from_pipe()
        ch = msvcrt.getwch()
        if ch in ('\x00', '\xe0'):   # 方向键/功能键：吞掉后续字节并忽略
            msvcrt.getwch()
            return ''
        if ch in ('\r', '\n'):
            return ''
        if ch == '\x03':             # getwch 下 Ctrl+C 不产生 SIGINT，需手动抛出
            raise KeyboardInterrupt
        return ch

    import termios
    import tty
    if sys.stdin is not None and not sys.stdin.isatty():
        return _read_key_from_pipe()
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    if ch in ('\r', '\n'):
        return ''
    if ch == '\x03':                 # raw 模式下同样收不到 SIGINT，需手动抛出
        raise KeyboardInterrupt
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

# 皮肤中常见的 LN 面身命名：mania-note<数字>L 与 NoteImage*L
_LN_NAME_PATTERNS = (
    re.compile(r"^mania-note\d+L$", re.IGNORECASE),
    re.compile(r"^NoteImage.*L$", re.IGNORECASE),
)

def is_ln_note_image(path):
    """文件名是否符合 mania-note[数字]L 或 NoteImage*L。"""
    stem = os.path.splitext(os.path.basename(path))[0]
    return any(pattern.match(stem) for pattern in _LN_NAME_PATTERNS)

def split_ln_targets(pngs):
    """把 PNG 列表拆成 (匹配 LN 面身命名的, 其余)。"""
    matched = [p for p in pngs if is_ln_note_image(p)]
    return matched, [p for p in pngs if not is_ln_note_image(p)]

def choose_dir_targets(pngs):
    """目录模式下列出匹配的 LN 面身文件，并让用户确认修改范围。

    返回 (targets, proceed)；proceed 为 False 表示返回上一级路径输入。
    """
    matched = split_ln_targets(pngs)[0]
    print(f"\n{Color.OKCYAN}{t('【目录扫描结果】', '[Directory scan]')}{Color.ENDC}")
    if matched:
        print(t(f"匹配到 {len(matched)} 个 LN 面身文件（mania-note[数字]L / NoteImage*L）:",
                f"Matched {len(matched)} LN note-body file(s) (mania-note<digit>L / NoteImage*L):"))
        for p in matched:
            print(f"  {Color.BOLD}- {os.path.basename(p)}{Color.ENDC}")
    else:
        print(f"{Color.WARNING}"
              + t("未匹配到 mania-note[数字]L 或 NoteImage*L 命名的文件。",
                  "No files named mania-note<digit>L or NoteImage*L were found.")
              + f"{Color.ENDC}")
    print(f"{Color.HEADER}{t('该目录下 PNG 总数: ', 'Total PNG files: ')}"
          f"{Color.BOLD}{len(pngs)}{Color.ENDC}")

    all_key = '2' if matched else '1'
    print(f"\n{Color.OKCYAN}"
          + t("请选择修改范围（直接回车返回上级）:", "Choose the scope (Enter to go back):")
          + f"{Color.ENDC}")
    if matched:
        print(t(f"  1 - 仅修改上面列出的 {len(matched)} 个匹配文件",
                f"  1 - Only the {len(matched)} matched file(s) listed above"))
    print(t(f"  {all_key} - 修改该目录下全部 {len(pngs)} 个图片文件",
            f"  {all_key} - All {len(pngs)} image file(s) in this directory"))
    print("> ", end='', flush=True)

    key = read_key().strip()
    print(key)
    if key == '':
        print(f"{Color.WARNING}{t('已返回上级。', 'Going back.')}{Color.ENDC}")
        return [], False
    if matched and key == '1':
        return matched, True
    if key == all_key:
        return pngs, True
    print(f"{Color.FAIL}{t('输入无效，已返回上级。', 'Invalid input; going back.')}{Color.ENDC}")
    return [], False

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
    """返回高度小于 MIN_IMAGE_HEIGHT 的图片路径列表。

    打不开的文件不在这里报错：它们会在处理阶段被逐文件捕获并计入失败，
    这样一个损坏的 PNG 不会像以前那样把整批选择作废。
    """
    undersized = []
    for path in targets:
        try:
            with Image.open(path) as tmp:
                if tmp.height < MIN_IMAGE_HEIGHT:
                    undersized.append(path)
        except Exception:
            continue
    return undersized


def report_undersized(undersized):
    """提示高度不足的图片——它们不在本程序的处理范围内。

    高度小于 MIN_IMAGE_HEIGHT 的图片通常是另一种面尾结构，而不是使用 Repeat
    模式的面身文件。对这类图片做纵向复制并不能产生有效结果，所以这里只把它们
    列出来并从本次处理中排除，不做任何改动。
    """
    print(f"\n{Color.WARNING}"
          + t(f"以下 {len(undersized)} 张图片高度小于 {MIN_IMAGE_HEIGHT}px，不属于本程序的处理范围：",
              f"The {len(undersized)} image(s) below are shorter than {MIN_IMAGE_HEIGHT}px "
              f"and are outside this tool's scope:")
          + f"{Color.ENDC}")
    for path in undersized:
        print(f"  {Color.BOLD}- {os.path.basename(path)}{Color.ENDC}")
    print(t("  这类图片通常是另一种面尾结构，并不是使用 Repeat 模式的面身文件；",
            "  They are usually a different tail structure rather than a Repeat-mode note body;"))
    print(t("  本程序只处理 Repeat 模式的面身文件，因此会把它们跳过，不做任何改动。",
            "  this tool only handles Repeat-mode note bodies, so they are skipped and left untouched."))

def confirm_action(prompt):
    """单键确认：按 y 确认，其他任意键（含回车）取消。"""
    print(f"{Color.WARNING}{prompt}{Color.ENDC}")
    print(t("按 y 确认，其他任意键取消: ", "Press y to confirm, any other key to cancel: "),
          end='', flush=True)
    key = read_key()
    print(key)
    return key.strip().lower() == 'y'

def pause():
    """按任意键继续（单键触发，无需回车）。"""
    print(t("按任意键继续...", "Press any key to continue..."), end='', flush=True)
    read_key()

def emit_output(src, mode, timestamp, build_path, produce):
    """按输出模式写出结果，返回结果文件路径。

    常规模式：写到 build_path() 指定的输出路径。
    替换模式：先把原文件备份到 备份根/[备份时间戳]/，再用结果替换原文件。

    produce(out_path, in_path) 负责真正生成图片。替换模式下以**备份文件**作为输入：
    批量生成（菜单 4）同一批次会对同一个 src 走多次 emit_output，若以 src 为输入，
    第 N 个 d 就会作用在第 N-1 个 d 的结果上，变换复合使面身被逐次吃掉；备份始终保存
    最初的原文件，所以每个 d 都从最初的原图开始。这样同时也省掉一次整图回拷，
    并且 src 只经由 os.replace 原子替换，不会出现写到一半损坏原图的情况。
    """
    if mode == OUTPUT_MODE_REPLACE:
        original = backup_file(src, timestamp)
        tmp_path = src + ".percy-tmp.png"
        try:
            produce(tmp_path, original)
            os.replace(tmp_path, src)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        return src
    output_path = build_path()
    # normcase 而非仅 abspath：Windows 文件系统大小写不敏感，只比较 abspath 会
    # 让 "C:\Skin" 与 "c:\skin\note1L.png" 这类只在大小写上不同的路径绕过守卫。
    if os.path.normcase(os.path.abspath(output_path)) == os.path.normcase(os.path.abspath(src)):
        raise LNImageError(t(
            "输出路径与原文件相同（输出文件夹指向源目录且未加文件名后缀）；"
            "常规模式不会覆盖原文件，已跳过该文件。",
            "Output path equals the source file (the output folder points at the source "
            "directory and no filename suffix is used); Normal Mode never overwrites "
            "originals, so this file was skipped."))
    produce(output_path, src)
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
                lambda p, i: process_ln_image(i, d_value, lzr=lzr, output_path=p),
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
                lambda p, i: normalize_image_file(i, lzr=lzr, output_path=p),
            )
            success += 1
        except Exception as e:
            failed += 1
            errors.append((src, str(e)))
    return success, failed, errors, last_output_path

def build_d_values(start_value, end_value, step):
    if step == 0:
        raise LNImageError(t("步长不能为 0。", "Step cannot be 0."))
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

# 帮助页正文：每项是一对 (中文, English) 的逻辑块，渲染时逐块交给 t() 选择。
# 两种语言的折行位置不同，所以按逻辑块（小节 / 菜单项）配对而不是硬凑成一一对应的
# 物理行 —— 那样得为对齐塞进大量空行，反而更难维护。
HELP_TEXT = (
    # 标题 + 什么是投皮
    (
        f"""{Color.BOLD}{Color.OKGREEN}========== 帮助信息 =========={Color.ENDC}
{Color.OKCYAN}【什么是投皮】{Color.ENDC}
  • 投皮是一个将面身拉伸到上万像素长，随后通过顶部截断的方式来制造视觉上的短尾效果。
  • 在高密度LN中，玩家通常会使用投皮来获得更好的视觉反馈和操作体验。
  • 投皮往往能够大幅减轻读谱压力，但是无法精确地找到松手位置。
  • 我们约定，一个皮肤顶部截断了多少像素(即第一个非背景色像素到顶部的距离)，称为"投机取巧程度"或"投了多少像素"。
  • 在本程序中，使用 d 来代替这个值。""",
        f"""{Color.BOLD}{Color.OKGREEN}========== Help Information =========={Color.ENDC}
{Color.OKCYAN}[What Is Percy]{Color.ENDC}
  - Percy stretches a note body to an extremely long image, then creates a short-tail
    visual effect by clipping from the top.
  - In high-density LN charts, many players use percy skins for better readability.
  - Percy can reduce reading pressure, but cannot provide precise release timing.
  - We define the distance from the first non-background pixel to the top as the
    cut-off amount, also called d in this program.""",
    ),
    # 模式说明
    (
        f"""{Color.OKCYAN}【模式说明】{Color.ENDC}
  • Stable 模式 : 直接设置新的 d 值，程序自动移动面尾和面身。
  • Lazer 模式 : 根据我的测定，26年初的lazer版本会使皮肤错误拉伸。大致为stb+75px。
                因此，该模式下输入的任何数据都会被-75px，下限为0.
                另外，为防止过度拉伸，所有图片长度将被固定在32800px。""",
        f"""{Color.OKCYAN}[Mode Explanation]{Color.ENDC}
  - Stable Mode: Set a new d directly. The tool moves tail and body automatically.
  - Lazer Mode: Based on measurements, early-2026 lazer may stretch by roughly +75px.
    So in this mode, user input is converted by minus 75 (with lower bound 0).
    Also, output height is normalized to 32800px.""",
    ),
    # 输出模式说明
    (
        f"""{Color.OKCYAN}【输出模式说明】{Color.ENDC}
  • 常规模式 : 默认模式。处理结果输出到输出文件夹（默认 {DEFAULT_CONFIG['output_dir']}），不改动原文件。
  • 替换模式 : 处理前先把所选原文件复制到备份文件夹（默认 {DEFAULT_CONFIG['backup_dir']}）下的
              [备份时间戳] 子文件夹，随后用处理结果替换原文件。
              同一批处理的文件共用同一个时间戳文件夹，提示中给出的就是实际创建的路径。""",
        f"""{Color.OKCYAN}[Output Mode Explanation]{Color.ENDC}
  - Normal Mode: default. Results are written to the output folder (default {DEFAULT_CONFIG['output_dir']});
    original files are never modified.
  - Replace Mode: before processing, each selected original is copied into the backup
    folder (default {DEFAULT_CONFIG['backup_dir']}) under a [timestamp] subfolder, then the result
    replaces the original file.
    All files in the same batch share one timestamp folder, and the path reported on
    success is the folder that was actually created.""",
    ),
    # 菜单说明
    (
        f"""{Color.OKCYAN}【菜单说明】{Color.ENDC}
  菜单为单键触发：按一个键立即执行，无需回车。""",
        f"""{Color.OKCYAN}[Menu Description]{Color.ENDC}
  The menu is single-key: press one key and it runs immediately, no Enter needed.""",
    ),
    (
        "  • ? - 帮助 : 显示本说明页（半角 ? 与全角 ？ 均可触发）。",
        "  - ? - Help: Show this help page (both the half-width ? and the full-width ？ work).",
    ),
    (
        """  • 0 - 重置默认配置 : 把输出模式、输出文件夹、备份文件夹、语言恢复为默认值；
                       输出模式与文件夹立即生效，界面语言在重启后切换。""",
        """  - 0 - Reset Default Config: restore the output mode, output folder, backup folder and
    language to defaults. Output mode and folders apply immediately; the UI language
    switches after a restart.""",
    ),
    (
        "  • 1 - 切换模式 : 在 Stable 和 Lazer 之间切换。注意 Lazer 模式下 d 最小为 75。",
        """  - 1 - Switch Mode: Toggle between Stable and Lazer.
    Note: In Lazer mode, the minimum d is 75.""",
    ),
    (
        "  • 2 - 查看当前投机取巧程度 : 单图模式显示该图的 d；目录模式会逐张列出所有已选图片的 d。",
        """  - 2 - View Current d: In single-image mode it shows that image's d; in directory mode
    it lists the d of every selected image, one per line.""",
    ),
    (
        """  • 3 - 修改投机取巧程度 :
        单图模式会输出 1 张结果图；目录模式会对已选文件进行同一 d 的批处理。
        常规模式下输入 d 值后可选择是否为输出文件名添加后缀，随后会再确认一次；
        替换模式下文件名不变，因此不再询问后缀。
        替换模式在确认前会用醒目红色警告提示将覆盖原文件。""",
        """  - 3 - Modify d:
    Single-image mode outputs one image.
    Directory mode applies the same d to all selected files in that directory.
    In Normal Mode you may choose whether to add a suffix to the output filename;
    in Replace Mode the filename never changes, so no suffix is asked.
    Replace Mode shows a bold red warning that originals will be overwritten.""",
    ),
    (
        """  • 4 - 单图批量生成 :
        仅单图模式可用。输入起始值、终止值、步长生成列表后，会按其逐个生成多张图。
        步长不能为 0；若数量较多会再次提示确认。
        替换模式下多次生成共用同一个备份时间戳，备份只保留最初的原文件。""",
        """  - 4 - Single-Image Batch Generation:
    Only available in single-image mode.
    Input start, end, and step to generate a d list, then output one image per d.
    Step cannot be 0; for large counts there is an extra confirmation.
    In Replace Mode all generations share one backup timestamp, so the backup keeps
    only the very first original.""",
    ),
    (
        """  • 5 - 模式修复功能 :
      Lazer 模式显示为“图片拉伸修复”，会执行 Lazer 标准化（固定到 32800px）。
      Stable 模式显示为“修复面尾白线”，会执行 Stable 标准化（超过 32767px 时裁切并清空末行）。""",
        """  - 5 - Mode Fix Tool:
    In Lazer mode, this shows "Stretch Repair" and runs Lazer normalization (fixed to 32800px).
    In Stable mode, this shows "Fix Tail White Line" and runs Stable normalization
    (crop if over 32767px and clear the last row).""",
    ),
    (
        "  • 6 - 调整输出模式 : 在 常规模式 与 替换模式 之间切换；菜单上方始终显示当前输出模式。",
        """  - 6 - Adjust Output Mode: Switch between Normal Mode and Replace Mode. The current
    output mode is always shown above the menu.""",
    ),
    (
        """  • 7 - 调整输出/备份文件夹 : 先选择“输出文件夹”还是“备份文件夹”，再输入新路径；
       留空（直接回车）即可返回上级菜单。""",
        """  - 7 - Adjust Output/Backup Folder: Choose whether to adjust the output folder or the
    backup folder, then enter a new path. Leaving the input empty returns to the menu.""",
    ),
    (
        "  • 8 - 更换图片 : 重新选择单个 PNG 或文件夹路径。",
        "  - 8 - Switch Image: Select a new PNG or directory path.",
    ),
    (
        "  • 9 - 检查更新 : 从 GitHub 获取最新发布版本信息。",
        "  - 9 - Check Updates: Query latest release info from GitHub.",
    ),
    (
        """  • L - 语言/Language : 切换界面语言（中文 / English）；留空（直接回车）即可返回上级菜单，
        设置会保存到配置文件。""",
        """  - L - Language/语言: Switch the interface language (中文 / English). Leaving the input
    empty returns to the menu; the choice is saved to the config file.""",
    ),
    (
        "  • Q - 退出 : 保存配置并关闭程序。",
        "  - Q - Quit: Save the config and exit the program.",
    ),
    # 选择文件夹时
    (
        f"""{Color.OKCYAN}【选择文件夹时】{Color.ENDC}
  选择文件夹后，程序会先列出命名匹配 mania-note[数字]L 或 NoteImage*L 的文件，
  再让你选择修改范围：
  • 1 - 仅修改上面列出的匹配文件
  • 2 - 修改该目录下的全部图片文件
  直接回车则返回路径输入。""",
        f"""{Color.OKCYAN}[Selecting a Directory]{Color.ENDC}
  When a directory is chosen, files named like mania-note<digit>L or NoteImage*L are
  listed first, then you pick the scope:
  - 1 - Only the matched files listed above
  - 2 - All image files in that directory
  Pressing Enter returns to the path input.""",
    ),
    # 高度小于 1000px
    (
        f"""{Color.OKCYAN}【高度小于 1000px 的图片】{Color.ENDC}
  这类图片不在本程序的处理范围内：它们通常是另一种面尾结构，而不是使用 Repeat 模式的
  面身文件，对它们做纵向复制并不能产生有效结果。程序会把它们从本次处理中排除并说明原因，
  不会对任何文件做改动；若所选图片全部属于这一类，则返回路径输入重新选择。""",
        f"""{Color.OKCYAN}[Images Shorter Than 1000px]{Color.ENDC}
  Such images are outside this tool's scope. They are usually a different tail structure
  rather than a Repeat-mode note body, so tiling them vertically would not achieve
  anything. The tool excludes them from the run and explains why, leaving every file
  untouched; if every selected image is like this, it returns to the path input.""",
    ),
    # 配置文件
    (
        f"""{Color.OKCYAN}【配置文件】{Color.ENDC}
  • 配置文件为 exe（源码运行时为脚本）所在目录下的 {CONFIG_FILENAME}，启动时读取、退出时保存。
  • 若该文件不存在，启动时会自动创建默认配置文件。
  • 默认值：输出模式 常规模式，输出文件夹 {DEFAULT_CONFIG['output_dir']}，备份文件夹 {DEFAULT_CONFIG['backup_dir']}。
    界面语言在首次运行时按系统界面语言确定，之后以配置文件为准。
  • 输出文件夹、备份文件夹以 / 或 \\ 开头表示相对于程序运行目录（仅 Windows）。
  • 命令行参数 --lang zh|en 可在启动时强制界面语言，配置文件不存在时同样有效。""",
        f"""{Color.OKCYAN}[Config File]{Color.ENDC}
  - The config file is {CONFIG_FILENAME} next to the executable (or next to the script when
    run from source); it is read at startup and saved on exit.
  - If the file does not exist, a default config file is created at startup.
  - Defaults: output mode Normal Mode, output folder {DEFAULT_CONFIG['output_dir']}, backup folder {DEFAULT_CONFIG['backup_dir']}.
    The language follows the system UI language on first run, and is stored in the config
    afterwards.
  - On Windows a leading / or \\ means "relative to the program directory"; on other
    platforms a leading / is an ordinary absolute path.
  - The --lang zh|en command-line option forces the UI language at startup, even before
    a config file exists.""",
    ),
    # 注意事项
    (
        f"""{Color.OKCYAN}【注意事项】{Color.ENDC}
  1. 仅支持 PNG 图片（RGBA 模式），背景色以左上角第一个像素为准。
  2. 图片高度不得小于 1000 像素。低于该高度的是另一种面尾结构，不在处理范围内；
     程序会把它们从本次处理中排除，其余文件照常处理。
  3. 常规模式输出到输出文件夹，命名格式为：
      原文件名-新d值px.png      （Stable模式）
      原文件名-新d值px-lzr.png  （Lazer 模式）
      若选择"不添加后缀"，则仅使用 原文件名.png。
     替换模式下结果直接覆盖原文件，文件名保持不变。
  4. 使用替换模式前请确认重要文件已备份；同一批次只保留最初版本的原文件。
  5. 如果原图不符合预期结构（例如找不到面尾/面身），程序会报错并返回菜单。
  6. 本程序暂不支持渐变颜色面身、非单一颜色或含有图案面身的皮肤。
  7. 输入文件夹路径时会批处理该目录下所有 .png 文件（不递归子目录）。
  8. 如果你遇到任何问题，请在GitHub仓库上提交issue或联系作者。""",
        f"""{Color.OKCYAN}[Notes]{Color.ENDC}
  1. PNG only (RGBA). Background color is the top-left pixel.
  2. Height must be at least 1000px. Shorter images are a different tail structure and
     are out of scope; the tool excludes them and still processes the rest.
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
  8. If you encounter issues, open an issue on GitHub or contact the author.""",
    ),
    # 结尾
    (
        f"{Color.BOLD}{Color.OKGREEN}=============================={Color.ENDC}",
        f"{Color.BOLD}{Color.OKGREEN}======================================{Color.ENDC}",
    ),
)


def print_help():
    # 开头与结尾各留一个空行，保持原有的排版
    print("\n" + "\n".join(t(zh_text, en_text) for zh_text, en_text in HELP_TEXT) + "\n")
    print(f"{Color.WARNING}{t('按任意键返回菜单...', 'Press any key to return to the menu...')}{Color.ENDC}", end='', flush=True)
    read_key()



def parse_lang_arg(argv):
    """解析命令行 --lang <zh|en>（也接受 --lang=zh）。

    用于配置文件还不存在、或需要在脚本里强制界面语言的场景；设置会像菜单 L
    一样写回配置文件。未给出该参数时返回 None。
    """
    for i, arg in enumerate(argv):
        if arg == "--lang":
            value = argv[i + 1] if i + 1 < len(argv) else ""
        elif arg.startswith("--lang="):
            value = arg.split("=", 1)[1]
        else:
            continue
        value = value.strip().lower()
        if value in LANGUAGES:
            return value
        raise LNImageError(t(
            f"不支持的语言: {value or '(空)'}；可选 {', '.join(LANGUAGES)}",
            f"Unsupported language: {value or '(empty)'}; choose from {', '.join(LANGUAGES)}"))
    return None


def main():
    global LANG
    cfg = config()
    try:
        forced_lang = parse_lang_arg(sys.argv[1:])
    except LNImageError as e:
        print(f"{Color.FAIL}{e}{Color.ENDC}")
        return 1
    if forced_lang is not None:
        cfg["language"] = forced_lang
    LANG = cfg.get("language", DEFAULT_LANGUAGE)
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
                    targets, proceed = choose_dir_targets(targets)
                    if not proceed:
                        clear_screen()
                        continue
                undersized = find_undersized(targets)
            except Exception as e:
                print(f"{Color.FAIL}{e}{Color.ENDC}")
                continue
            if undersized:
                report_undersized(undersized)
                # 只把这批图片排除掉，其余照常处理；以前是整批作废、让用户
                # 重新走一遍路径输入与范围选择。
                skipped = set(undersized)
                targets = [p for p in targets if p not in skipped]
                if not targets:
                    print(f"\n{Color.WARNING}"
                          + t("所选图片全部不在处理范围内，请重新选择。",
                              "Every selected image is outside this tool's scope; please choose again.")
                          + f"{Color.ENDC}")
                    pause()
                    clear_screen()
                    continue
                print(f"\n{Color.OKCYAN}"
                      + t(f"已跳过上面 {len(undersized)} 张，继续处理其余 {len(targets)} 张。",
                          f"Skipping the {len(undersized)} image(s) above; "
                          f"continuing with the remaining {len(targets)}.")
                      + f"{Color.ENDC}")
                # 下一轮 while 一进来就会 clear_screen()，不停一下的话被跳过的
                # 文件清单会一闪而过。
                pause()
            current_image_path = path
            current_targets = targets
            current_source_type = source_type
            
        clear_screen()
        if current_source_type == "dir":
            print(f"\n{Color.OKCYAN}{t('当前目录: ', 'Current directory: ')}{Color.BOLD}{current_image_path}{Color.ENDC}")
            print(f"{Color.WARNING}{t('待处理图片数量: ', 'PNG files to process: ')}{Color.BOLD}{len(current_targets)}{Color.ENDC}")
        else:
            print(f"\n{Color.HEADER}{t('当前图片: ', 'Current image: ')}{Color.BOLD}{current_image_path}{Color.ENDC}")
        mode_label = "Stable" if current_mode == "stable" else "Lazer"
        current_output_mode = config().get("output_mode", OUTPUT_MODE_NORMAL)
        out_mode_label = output_mode_label(current_output_mode)
        print(f"{Color.OKBLUE}{t('当前模式: ', 'Current mode: ')}{Color.BOLD}{mode_label}{Color.ENDC}")
        if current_output_mode == OUTPUT_MODE_REPLACE:
            print(f"{Color.BOLD}{Color.FAIL}{t('当前输出模式: ', 'Current output mode: ')}{out_mode_label}{Color.ENDC}")
        else:
            print(f"{Color.OKGREEN}{t('当前输出模式: ', 'Current output mode: ')}{Color.BOLD}{out_mode_label}{Color.ENDC}")
        print(f"{Color.OKCYAN}{t('请选择操作（按单键即可，无需回车）:', 'Select an action (single key, no Enter needed):')}{Color.ENDC}")
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
        print("  {0} - {1}".format(Color.OKBLUE + "L" + Color.ENDC, t("语言 / Language", "Language / 语言")))
        print("  {0} - {1}".format(Color.OKBLUE + "Q" + Color.ENDC, t("退出", "Quit")))
        print("> ", end='', flush=True)

        choice = read_key().strip()
        print(choice)

        if choice in ('?', '？'):
            clear_screen()
            print_help()
            clear_screen()
        elif choice == '0':
            print(f"\n{Color.WARNING}{t('重置默认配置将恢复以下默认值:', 'Resetting restores these defaults:')}{Color.ENDC}")
            print(f"  {t('输出模式  ', 'Output mode  ')}: {output_mode_label(OUTPUT_MODE_NORMAL)}")
            print(f"  {t('输出文件夹', 'Output folder')}: {DEFAULT_CONFIG['output_dir']}")
            print(f"  {t('备份文件夹', 'Backup folder')}: {DEFAULT_CONFIG['backup_dir']}")
            print(f"  {t('语言      ', 'Language     ')}: {language_label(detect_system_language())}")
            if not confirm_action(t("确认重置默认配置？", "Reset to default config?")):
                clear_screen()
                continue
            reset_default_config()
            print(f"{Color.OKGREEN}{t('配置已重置为默认值。', 'Config has been reset to defaults.')}{Color.ENDC}")
            print(f"{Color.WARNING}"
                  + t("输出模式与文件夹已立即生效；界面语言将在重启后切换。",
                      "Output mode and folders take effect immediately; "
                      "the UI language switches after a restart.")
                  + f"{Color.ENDC}")
            pause()
            clear_screen()
        elif choice == '1':
            current_mode = "lazer" if current_mode == "stable" else "stable"
            switched_label = "Stable" if current_mode == "stable" else "Lazer"
            print(f"\n{Color.OKGREEN}{t('已切换到 ', 'Switched to ')}{switched_label}{t(' 模式。', ' mode.')}{Color.ENDC}")
            pause()
            clear_screen()
        elif choice == '2':
            if current_source_type == "dir":
                print(f"\n{Color.OKCYAN}"
                      + t(f"已选中 {len(current_targets)} 张图片，逐张读取 d 值:",
                          f"{len(current_targets)} image(s) selected; reading d for each:")
                      + f"{Color.ENDC}")
                for tgt in current_targets:
                    try:
                        d = get_current_d(tgt)
                        if current_mode == "lazer":
                            d += 75
                        print(f"  {Color.BOLD}{os.path.basename(tgt)}{Color.ENDC}"
                              f"{t(' 的投机取巧程度 d = ', ' d = ')}"
                              f"{Color.OKGREEN}{d}px{Color.ENDC}")
                    except Exception as e:
                        print(f"  {Color.BOLD}{os.path.basename(tgt)}{Color.ENDC}"
                              f"{t(' 读取失败: ', ' failed: ')}{Color.FAIL}{e}{Color.ENDC}")
            else:
                try:
                    d = get_current_d(current_image_path)
                    if current_mode == "lazer":
                        d += 75
                    print(f"\n{Color.OKGREEN}{t('当前投机取巧程度 d = ', 'Current d = ')}{d}{t('px（', 'px (')}{mode_label}{t('）', ')')}{Color.ENDC}")
                except Exception as e:
                    print(f"\n{Color.FAIL}{t('获取 d 失败: ', 'Failed to read current d: ')}{e}{Color.ENDC}")
            pause()
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
                pause()
                clear_screen()
                continue
            if current_mode == "lazer" and new_d < 75:
                print(f"{Color.FAIL}{t('Lazer 模式下 d 的最小值为 75。', 'Minimum d in Lazer mode is 75.')}{Color.ENDC}")
                pause()
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
                suffix_choice = read_key().strip()
                print(suffix_choice)
                if suffix_choice == '1':
                    add_suffix = True
                elif suffix_choice == '2':
                    add_suffix = False
                else:
                    print(f"{Color.FAIL}{t('输入无效，请输入 1 或 2。', 'Invalid input. Please enter 1 or 2.')}{Color.ENDC}")
                    pause()
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
                    backup_label = os.path.join(get_backup_root(), timestamp)
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
            pause()
            clear_screen()
        elif choice == '4':
            if current_source_type != "file":
                print(f"{Color.FAIL}{t('该功能仅支持单个图片。请先选择单图。', 'This feature supports only a single image target. Please switch image first.')}{Color.ENDC}")
                pause()
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
                pause()
                clear_screen()
                continue

            total = len(d_values)
            active_mode = config().get("output_mode", OUTPUT_MODE_NORMAL)
            batch_timestamp = make_timestamp() if active_mode == OUTPUT_MODE_REPLACE else None
            print(f"{Color.OKCYAN}{t('本次将使用列表: ', 'This run will use d list: ')}{d_values}{Color.ENDC}")
            if active_mode == OUTPUT_MODE_REPLACE:
                print(f"{Color.BOLD}{Color.FAIL}{t('！！！ 警告: 当前为【替换模式】，本次生成的结果会覆盖原文件 ！！！', '!!! WARNING: Replace Mode is active - these results will overwrite the original file !!!')}{Color.ENDC}")
                print(f"{Color.FAIL}{t('文件名保持不变；每个 d 都从最初的原文件重新生成，备份只保留最初的原文件。', 'The filename stays the same; every d is regenerated from the original file, and the backup keeps only the first original.')}{Color.ENDC}")
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

            # 只有替换模式才有备份路径。这里必须按模式求值：batch_timestamp 在常规
            # 模式下是 None，无条件 os.path.join 会抛 TypeError；而且 get_backup_root()
            # 会顺带 makedirs，常规模式也会凭空多出一个空的 backup-archive/。
            backup_label = (
                os.path.join(get_backup_root(), batch_timestamp)
                if active_mode == OUTPUT_MODE_REPLACE else None
            )
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

            pause()
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

                # 同上：常规模式下 fix_timestamp 是 None，必须在 if 之前按模式求值，
                # 否则 TypeError 会被下面的宽 except 吞掉、伪装成“修复失败”。
                backup_label = (
                    os.path.join(get_backup_root(), fix_timestamp)
                    if active_mode == OUTPUT_MODE_REPLACE else None
                )
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
                # 带上异常类型，避免程序缺陷被伪装成普通的“修复失败”
                print(f"{Color.FAIL}{fix_label}{t('失败: ', ' failed: ')}{type(e).__name__}: {e}{Color.ENDC}")
            pause()
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
            ans = read_key().strip()
            print(ans)
            if ans == '1':
                new_mode = OUTPUT_MODE_NORMAL
            elif ans == '2':
                new_mode = OUTPUT_MODE_REPLACE
            else:
                print(f"{Color.FAIL}{t('输入无效，请输入 1 或 2。', 'Invalid input. Please enter 1 or 2.')}{Color.ENDC}")
                pause()
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
            pause()
            clear_screen()
        elif choice == '7':
            cfg_now = config()
            print(f"\n{Color.OKBLUE}{t('请选择要调整的文件夹:', 'Choose which folder to adjust:')}{Color.ENDC}")
            print(f"  1 - {t('输出文件夹', 'Output folder')} ({t('当前', 'current')}: {cfg_now.get('output_dir')} -> {resolve_dir(cfg_now.get('output_dir'))})")
            print(f"  2 - {t('备份文件夹', 'Backup folder')} ({t('当前', 'current')}: {cfg_now.get('backup_dir')} -> {resolve_dir(cfg_now.get('backup_dir'))})")
            print(f"{Color.WARNING}{t('留空（直接回车）即可返回上级菜单', 'Leave empty (press Enter) to return to the menu')}{Color.ENDC}")
            print("> ", end='', flush=True)
            sel = read_key().strip()
            print(sel)
            if sel == '':
                clear_screen()
                continue
            if sel == '1':
                folder_key = 'output_dir'
                folder_label = t('输出文件夹', 'Output folder')
            elif sel == '2':
                folder_key = 'backup_dir'
                folder_label = t('备份文件夹', 'Backup folder')
            else:
                print(f"{Color.FAIL}{t('输入无效，已返回上级菜单。', 'Invalid input; returning to the menu.')}{Color.ENDC}")
                pause()
                clear_screen()
                continue
            print(f"{Color.OKBLUE}{t('请输入新的', 'Enter the new ')}{folder_label}{t('路径（以 / 开头表示相对程序运行目录）:', ' path (a leading / means relative to the program directory):')}{Color.ENDC}")
            print(f"{Color.WARNING}{t('留空（直接回车）即可返回上级菜单', 'Leave empty (press Enter) to return to the menu')}{Color.ENDC}")
            print("> ", end='', flush=True)
            new_folder = normalize_input_path(input().strip())
            if not new_folder:
                print(f"{Color.WARNING}{t('已留空，返回上级菜单。', 'Empty input; returning to the menu.')}{Color.ENDC}")
                pause()
                clear_screen()
                continue
            cfg_now[folder_key] = new_folder
            save_config(cfg_now)
            print(f"{Color.OKGREEN}{folder_label}{t('已更新为: ', ' updated to: ')}{new_folder}{Color.ENDC}")
            print(f"{Color.OKGREEN}{t('实际路径: ', 'Resolved path: ')}{resolve_dir(new_folder)}{Color.ENDC}")
            pause()
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
            pause()
            clear_screen()
        elif choice.lower() == 'l':
            current_lang = config().get("language", DEFAULT_LANGUAGE)
            print(f"\n{Color.OKCYAN}{t('【语言 / Language】', '[Language / 语言]')}{Color.ENDC}")
            print("  1 - 中文")
            print("  2 - English")
            print(f"{t('当前语言: ', 'Current language: ')}{Color.BOLD}{language_label(current_lang)}{Color.ENDC}")
            print(f"{Color.WARNING}{t('留空（直接回车）即可返回上级菜单', 'Leave empty (press Enter) to return to the menu')}{Color.ENDC}")
            print("> ", end='', flush=True)
            sel = read_key().strip()
            print(sel)
            if sel == '':
                clear_screen()
                continue
            if sel == '1':
                new_lang = "zh"
            elif sel == '2':
                new_lang = "en"
            else:
                print(f"{Color.FAIL}{t('输入无效，已返回上级菜单。', 'Invalid input; returning to the menu.')}{Color.ENDC}")
                pause()
                clear_screen()
                continue
            cfg_now = config()
            cfg_now["language"] = new_lang
            save_config(cfg_now)
            LANG = new_lang
            print(f"{Color.OKGREEN}{t('语言已切换为: ', 'Language switched to: ')}{language_label(new_lang)}{Color.ENDC}")
            print(f"{Color.OKGREEN}{t('界面已即时生效，并已保存到配置文件。', 'The interface takes effect immediately and the choice was saved to the config file.')}{Color.ENDC}")
            pause()
            clear_screen()
        elif choice.lower() == 'q':
            save_config(config())
            print(f"{Color.OKGREEN}{t('配置已保存，程序退出。', 'Config saved. Program exited.')}{Color.ENDC}")
            break
        else:
            if choice == '':
                clear_screen()
                continue
            print(f"{Color.WARNING}{t('无效选项，请重试。', 'Invalid option. Please try again.')}{Color.ENDC}")
            pause()
            clear_screen()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Color.WARNING}{t('用户中断，程序退出。', 'Interrupted by user. Program exited.')}{Color.ENDC}")
    finally:
        # 应用关闭时保存配置
        try:
            if _CONFIG is not None:
                save_config(_CONFIG)
        except Exception:
            pass