import os
import sys
import requests
from packaging.version import parse as parse_version
from PIL import Image

VERSION = "1.4.0"

_OWNER = "LeoBlackMT"
_REPO = "percy_skin_editor"
_GITHUB_API = "https://api.github.com"

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

def get_output_dir():
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def build_output_path(source_path, d_value, lzr=False):
    base = os.path.basename(source_path)
    name, _ = os.path.splitext(base)
    if lzr:
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
            raise LNImageError("仅支持 PNG 格式图片。")
        return [path], "file"
    if os.path.isdir(path):
        pngs = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if os.path.isfile(full) and os.path.splitext(name)[1].lower() == '.png':
                pngs.append(full)
        if not pngs:
            raise LNImageError("目录下未找到 PNG 文件。")
        return pngs, "dir"
    raise LNImageError("路径不存在，请重新输入。")

def validate_image_height(path):
    try:
        with Image.open(path) as tmp:
            if tmp.height < 1000:
                raise LNImageError(f"图片高度小于 1000 像素，无法处理: {path}")
    except LNImageError:
        raise
    except Exception as e:
        raise LNImageError(f"无法打开图片 {path}: {e}")

def confirm_action(prompt):
    print(f"{Color.WARNING}{prompt}{Color.ENDC}")
    ans = input("输入 y 确认，其他任意键取消: ").strip().lower()
    return ans == 'y'

def process_targets(targets, d_value, lzr=False):
    success = 0
    failed = 0
    errors = []
    last_output_path = ""
    for src in targets:
        try:
            output_path = build_output_path(src, d_value, lzr=lzr)
            process_ln_image(src, d_value, lzr=lzr, output_path=output_path)
            success += 1
            last_output_path = output_path
        except Exception as e:
            failed += 1
            errors.append((src, str(e)))
    return success, failed, errors, last_output_path

def process_normalize_targets(targets, lzr=False):
    success = 0
    failed = 0
    errors = []
    last_output_path = ""
    for src in targets:
        try:
            output_path = build_normalize_output_path(src, lzr=lzr)
            normalize_image_file(src, lzr=lzr, output_path=output_path)
            success += 1
            last_output_path = output_path
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

def get_current_d(image_path):
    """返回当前图片的投机取巧程度 d"""
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size
    bg = img.getpixel((0, 0))
    a_true = None
    for y in range(h):
        for x in range(w):
            if img.getpixel((x, y)) != bg:
                a_true = y
                break
        if a_true is not None:
            break
    if a_true is None:
        raise LNImageError("未找到非背景色像素，图片可能全为背景。")
    mid_y = h // 2
    x1 = None
    for x in range(w):
        if img.getpixel((x, mid_y)) != bg:
            x1 = x
            break
    if x1 is None:
        raise LNImageError("在左侧中点未能找到非背景色像素。")
    x2 = None
    for x in range(w-1, -1, -1):
        if img.getpixel((x, mid_y)) != bg:
            x2 = x
            break
    if x2 is None:
        raise LNImageError("在右侧中点未能找到非背景色像素。")
    def find_background_upwards(col, start_y):
        for y in range(start_y, -1, -1):
            px = img.getpixel((col, y))
            if px == bg or px[3] == 0:
                return y
        raise LNImageError(f"在列 {col} 从 y={start_y} 向上未找到背景色像素。")
    y1 = find_background_upwards(x1, mid_y)
    y2 = find_background_upwards(x2, mid_y)
    y = max(y1, y2)

    if y > a_true:
        return a_true
    else:
        return a_true

def process_ln_image(image_path, user_d, lzr=False, output_path=None):
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size
    bg = img.getpixel((0, 0))

    a_true = None
    for y in range(h):
        for x in range(w):
            if img.getpixel((x, y)) != bg:
                a_true = y
                break
        if a_true is not None:
            break
    if a_true is None:
        raise LNImageError("未找到非背景色像素，图片可能全为背景。")

    mid_y = h // 2
    x1 = None
    for x in range(w):
        if img.getpixel((x, mid_y)) != bg:
            x1 = x
            break
    if x1 is None:
        raise LNImageError("在左侧中点未能找到非背景色像素。")
    x2 = None
    for x in range(w-1, -1, -1):
        if img.getpixel((x, mid_y)) != bg:
            x2 = x
            break
    if x2 is None:
        raise LNImageError("在右侧中点未能找到非背景色像素。")

    def find_background_upwards(col, start_y):
        for y in range(start_y, -1, -1):
            px = img.getpixel((col, y))
            if px == bg or px[3] == 0:
                return y
        raise LNImageError(f"在列 {col} 从 y={start_y} 向上未找到背景色像素。")
    y1 = find_background_upwards(x1, mid_y)
    y2 = find_background_upwards(x2, mid_y)
    y = max(y1, y2)

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
                raise LNImageError("需要填充间隙，但面身不存在，无法截取。")
            if gap > body_h:
                raise LNImageError("需要填充的间隙大于面身高度，无法单次截取。")
            fill_region = body_region.crop((0, 0, x2 - x1 + 1, gap))
            if body_h - gap > 0:
                body_new = body_region.crop((0, gap, x2 - x1 + 1, body_h))
            else:
                body_new = None
        elif y_target > y:
            overlap = y_target - y
            if body_h == 0:
                raise LNImageError("需要丢弃重叠部分，但面身不存在。")
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
                body_new = None
                new_img_h = new_top + gap
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
                new_img = Image.new("RGBA", (w, 0), bg)
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
{Color.OKCYAN}【菜单说明】{Color.ENDC}
  • 0 - 帮助 : 显示本说明页。
  • 1 - 切换模式 : 在 Stable 和 Lazer 之间切换。注意 Lazer 模式下 d 最小为 75。
  • 2 - 查看当前投机取巧程度 : 仅单图模式可用；目录批处理模式下不可用。
  • 3 - 修改投机取巧程度 :
        单图模式会输出 1 张结果图；目录模式会对该目录下所有 PNG 进行同一 d 的批处理。
        结果统一输出到 output 文件夹。
  • 4 - 单图批量生成 :
        仅单图模式可用。输入起始值、终止值、步长生成列表后，会按其逐个生成多张图。
        步长不能为 0；若数量较多会再次提示确认。
  • 5 - 模式修复功能 :
      Lazer 模式显示为“图片拉伸修复”，会执行 Lazer 标准化（固定到 32800px）。
      Stable 模式显示为“修复面尾白线”，会执行 Stable 标准化（超过 32767px 时裁切并清空末行）。
  • 6 - 更换图片 : 重新选择单个 PNG 或文件夹路径。
  • 7 - 检查更新 : 从 GitHub 获取最新发布版本信息。
  • 8 - 退出 : 关闭程序。
{Color.OKCYAN}【注意事项】{Color.ENDC}
  0. 处理或覆盖前请备份原图片。
  1. 仅支持 PNG 图片（RGBA 模式），背景色以左上角第一个像素为准。
  2. 图片高度不得小于 1000 像素，否则可能无法正确识别结构。
  3. 处理后的图片默认保存在当前目录下的 output 文件夹，命名格式为：
      原文件名-新d值px.png      （Stable模式）
      原文件名-新d值px-lzr.png  （Lazer 模式）
  4. 如果原图不符合预期结构（例如找不到面尾/面身），程序会报错并返回菜单。
  5. 本程序暂不支持渐变颜色面身、非单一颜色或含有图案面身的皮肤。
  6. 输入文件夹路径时会批处理该目录下所有 .png 文件（不递归子目录）。
  7. 如果你遇到任何问题，请在GitHub仓库上提交issue或联系作者。
{Color.BOLD}{Color.OKGREEN}=============================={Color.ENDC}
"""
    print(help_text)
    input(f"{Color.WARNING}按回车键返回菜单...{Color.ENDC}")



def main():
    clear_screen()
    print(f"{Color.BOLD}{Color.HEADER}osu!mania 投皮调整工具 - v{VERSION}{Color.ENDC}")
    print(f"{Color.BOLD}{Color.HEADER}作者: Leo_Black{Color.ENDC}")
    print(f"{Color.BOLD}{Color.HEADER}Github: LeoBlackMT/percy_skin_editor{Color.ENDC}")
    current_image_path = None
    current_targets = []
    current_source_type = "file"
    current_mode = "stable"

    while True:
        if current_image_path is None:
            print(f"\n\n{Color.OKCYAN}[提示: 如何找到面身文件]{Color.ENDC}")
            print(f"\n对于Stable:\n游戏设置 - 皮肤 - 打开皮肤文件夹 - 找到skin.ini - 找到你想修改的key数(如Keys: 4) - 找到NoteImage*L,*是轨道序号 - 其对应的目录就是图片路径")
            print(f"\n对于Lazer:\n游戏设置 - 皮肤 - 打开皮肤编辑器 - 左上角文件 - 打开外部编辑 - 找到skin.ini -> 后续与Stable相同")
            print(f"\n如果未在skin.ini中找到NoteImage*L, 那么图片应该直接在皮肤目录下，名称为mania-note*L.png\n")
            print(f"\n你可以随时使用 Ctrl+C 退出程序。\n")
            print(f"\n{Color.OKBLUE}请输入图片或文件夹绝对/相对路径（或直接拖拽，输入 q 退出）:{Color.ENDC}")
            path = input().strip()
            if path.lower() == 'q':
                break
            path = normalize_input_path(path)
            try:
                targets, source_type = collect_png_targets(path)
                if source_type == "dir":
                    if not confirm_action(f"警告: 检测到文件夹，将批处理该目录下 {len(targets)} 个 .png 文件。是否继续？"):
                        clear_screen()
                        continue
                for t in targets:
                    validate_image_height(t)
            except Exception as e:
                print(f"{Color.FAIL}{e}{Color.ENDC}")
                continue
            current_image_path = path
            current_targets = targets
            current_source_type = source_type
            
        clear_screen()
        if current_source_type == "dir":
            print(f"\n{Color.OKGREEN}当前目录: {Color.BOLD}{current_image_path}{Color.ENDC}")
            print(f"{Color.OKGREEN}待处理图片数量: {Color.BOLD}{len(current_targets)}{Color.ENDC}")
        else:
            print(f"\n{Color.OKGREEN}当前图片: {Color.BOLD}{current_image_path}{Color.ENDC}")
        mode_label = "Stable" if current_mode == "stable" else "Lazer"
        print(f"{Color.OKGREEN}当前模式: {Color.BOLD}{mode_label}{Color.ENDC}")
        print(f"{Color.OKCYAN}请选择操作:{Color.ENDC}")
        print("  {0} - 帮助".format(Color.WARNING + "0" + Color.ENDC))
        print("  {0} - 切换模式".format(Color.OKBLUE + "1" + Color.ENDC))
        print("  {0} - 查看当前投机取巧程度".format(Color.OKBLUE + "2" + Color.ENDC))
        print("  {0} - 修改投机取巧程度".format(Color.OKBLUE + "3" + Color.ENDC))
        print("  {0} - 单图批量生成".format(Color.OKBLUE + "4" + Color.ENDC))
        if current_mode == "lazer":
            fix_label = "图片拉伸修复"
        else:
            fix_label = "修复面尾白线"
        print("  {0} - {1}".format(Color.OKBLUE + "5" + Color.ENDC, fix_label))
        print("  {0} - 更换图片".format(Color.OKBLUE + "6" + Color.ENDC))
        print("  {0} - 检查更新".format(Color.OKBLUE + "7" + Color.ENDC))
        print("  {0} - 退出".format(Color.OKBLUE + "8" + Color.ENDC))
        print("> ", end='', flush=True)

        choice = getch()
        print(choice)

        if choice == '0':
            clear_screen()
            print_help()
            clear_screen()
        elif choice == '1':
            current_mode = "lazer" if current_mode == "stable" else "stable"
            switched_label = "Stable" if current_mode == "stable" else "Lazer"
            print(f"\n{Color.OKGREEN}已切换到 {switched_label} 模式。{Color.ENDC}")
            input("按回车键继续...")
            clear_screen()
        elif choice == '2':
            if current_source_type == "dir":
                print(f"\n{Color.WARNING}当前为目录批处理模式，无法显示单个 d。请切换为单图或直接执行处理。{Color.ENDC}")
                input("按回车键继续...")
                clear_screen()
                continue
            try:
                d = get_current_d(current_image_path)
                if current_mode == "lazer":
                    d += 75
                print(f"\n{Color.OKGREEN}当前投机取巧程度 d = {d}px（{mode_label}）{Color.ENDC}")
            except Exception as e:
                print(f"\n{Color.FAIL}获取 d 失败: {e}{Color.ENDC}")
            input("按回车键继续...")
            clear_screen()
        elif choice == '3':
            if current_mode == "lazer":
                prompt = "请输入新的 d 值 (整数, 最小值为75): "
            else:
                prompt = "请输入新的 d 值 (整数): "
            print(f"\n{Color.OKBLUE}{prompt}{Color.ENDC}", end='', flush=True)
            try:
                new_d_str = input().strip()
                new_d = int(new_d_str)
            except ValueError:
                print(f"{Color.FAIL}输入无效，请输入整数。{Color.ENDC}")
                input("按回车键继续...")
                clear_screen()
                continue
            if current_mode == "lazer" and new_d < 75:
                print(f"{Color.FAIL}Lazer 模式下 d 的最小值为 75。{Color.ENDC}")
                input("按回车键继续...")
                clear_screen()
                continue
            try:
                if current_source_type == "dir":
                    if not confirm_action(f"警告: 即将处理 {len(current_targets)} 张图片，输出到 output 文件夹。是否继续？"):
                        clear_screen()
                        continue

                success, failed, errors, last_output_path = process_targets(
                    current_targets,
                    new_d,
                    lzr=(current_mode == "lazer")
                )

                if failed == 0:
                    if success == 1:
                        print(f"{Color.OKGREEN}处理完成，已保存至: {last_output_path}{Color.ENDC}")
                    else:
                        print(f"{Color.OKGREEN}处理完成，共成功 {success} 张。输出目录: {get_output_dir()}{Color.ENDC}")
                else:
                    print(f"{Color.WARNING}处理结束：成功 {success} 张，失败 {failed} 张。{Color.ENDC}")
                    for src, err in errors:
                        print(f"{Color.FAIL}失败: {src} -> {err}{Color.ENDC}")
                    print(f"{Color.OKGREEN}成功输出目录: {get_output_dir()}{Color.ENDC}")
            except Exception as e:
                print(f"{Color.FAIL}处理失败: {e}{Color.ENDC}")
            input("按回车键继续...")
            clear_screen()
        elif choice == '4':
            if current_source_type != "file":
                print(f"{Color.FAIL}该功能仅支持单个图片。请先选择单图。{Color.ENDC}")
                input("按回车键继续...")
                clear_screen()
                continue

            print(f"\n{Color.OKBLUE}请输入起始值（非负整数）:{Color.ENDC}", end='', flush=True)
            start_str = input().strip()
            print(f"{Color.OKBLUE}请输入终止值（非负整数）:{Color.ENDC}", end='', flush=True)
            end_str = input().strip()
            print(f"{Color.OKBLUE}请输入步长（非负整数，且不能为0）:{Color.ENDC}", end='', flush=True)
            step_str = input().strip()

            try:
                start_value = int(start_str)
                end_value = int(end_str)
                step = int(step_str)
                if start_value < 0 or end_value < 0 or step < 0:
                    raise LNImageError("起始值、终止值、步长必须都是非负整数。")
                if step == 0:
                    raise LNImageError("步长不能为 0。")
                d_values = build_d_values(start_value, end_value, step)
                if not d_values:
                    raise LNImageError("生成列表为空，请检查参数。")
                if current_mode == "lazer" and min(d_values) < 75:
                    raise LNImageError("Lazer 模式下 d 的最小值为 75。")
            except Exception as e:
                print(f"{Color.FAIL}输入无效: {e}{Color.ENDC}")
                input("按回车键继续...")
                clear_screen()
                continue

            total = len(d_values)
            print(f"{Color.OKCYAN}本次将使用列表: {d_values}{Color.ENDC}")
            if not confirm_action(f"警告: 将基于当前单图生成 {total} 张结果图。是否继续？"):
                clear_screen()
                continue
            if total > 10:
                if not confirm_action(f"再次警告: 本次将生成 {total} 张图片，可能需要一些时间。是否继续？"):
                    clear_screen()
                    continue

            success = 0
            failed = 0
            errors = []
            for d_value in d_values:
                s, f, err_list, _ = process_targets(
                    current_targets,
                    d_value,
                    lzr=(current_mode == "lazer")
                )
                success += s
                failed += f
                errors.extend(err_list)

            if failed == 0:
                print(f"{Color.OKGREEN}批量生成完成，共成功 {success} 张。输出目录: {get_output_dir()}{Color.ENDC}")
            else:
                print(f"{Color.WARNING}批量生成结束：成功 {success} 张，失败 {failed} 张。{Color.ENDC}")
                for src, err in errors:
                    print(f"{Color.FAIL}失败: {src} -> {err}{Color.ENDC}")
                print(f"{Color.OKGREEN}已成功输出部分结果到: {get_output_dir()}{Color.ENDC}")

            input("按回车键继续...")
            clear_screen()
        elif choice == '5':
            if current_mode == "lazer":
                fix_label = "图片拉伸修复"
                mode_is_lazer = True
            else:
                fix_label = "修复面尾白线"
                mode_is_lazer = False

            try:
                if current_source_type == "dir":
                    if not confirm_action(f"警告: 即将对 {len(current_targets)} 张图片执行“{fix_label}”，输出到 output 文件夹。是否继续？"):
                        clear_screen()
                        continue

                success, failed, errors, last_output_path = process_normalize_targets(
                    current_targets,
                    lzr=mode_is_lazer
                )

                if failed == 0:
                    if success == 1:
                        print(f"{Color.OKGREEN}{fix_label}完成，已保存至: {last_output_path}{Color.ENDC}")
                    else:
                        print(f"{Color.OKGREEN}{fix_label}完成，共成功 {success} 张。输出目录: {get_output_dir()}{Color.ENDC}")
                else:
                    print(f"{Color.WARNING}{fix_label}结束：成功 {success} 张，失败 {failed} 张。{Color.ENDC}")
                    for src, err in errors:
                        print(f"{Color.FAIL}失败: {src} -> {err}{Color.ENDC}")
                    print(f"{Color.OKGREEN}成功输出目录: {get_output_dir()}{Color.ENDC}")
            except Exception as e:
                print(f"{Color.FAIL}{fix_label}失败: {e}{Color.ENDC}")
            input("按回车键继续...")
            clear_screen()
        elif choice == '6':
            current_image_path = None
            current_targets = []
            current_source_type = "file"
            clear_screen()
        elif choice == '7':
            print(f"\n{Color.OKBLUE}正在检查更新...{Color.ENDC}")
            has, latest = check_update(VERSION)
            if not latest:
                print(f"{Color.FAIL}错误: 无法获取最新版本信息。{Color.ENDC}")
            else:
                if has:
                    print(f"{Color.OKGREEN}检测到新版本：{latest}（当前：{VERSION}）{Color.ENDC}")
                    print(f"请访问发布页面下载最新版本： https://github.com/{_OWNER}/{_REPO}/releases/latest")
                else:
                    print(f"{Color.OKGREEN}已是最新版本：{VERSION}{Color.ENDC}")
            input("按回车键继续...")
            clear_screen()
        elif choice == '8':
            print(f"{Color.OKGREEN}程序退出。{Color.ENDC}")
            break
        else:
            print(f"{Color.WARNING}无效选项，请重试。{Color.ENDC}")
            input("按回车键继续...")
            clear_screen()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Color.WARNING}用户中断，程序退出。{Color.ENDC}")
        sys.exit(0)