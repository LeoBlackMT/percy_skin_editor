import os
import sys
import requests
from packaging.version import parse as parse_version
from PIL import Image

VERSION = "1.2.0"

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

def normalize_height(img, target_h, bg):
    w, h = img.size
    if h == target_h:
        return img
    if h > target_h:
        return img.crop((0, 0, w, target_h))
    else:
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

    if y > a_true:
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
        new_img = normalize_height(new_img, 32800, bg)

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
{Color.OKCYAN}【注意事项】{Color.ENDC}
  0. 处理或覆盖前请备份原图片。
  1. 仅支持 PNG 图片（RGBA 模式），背景色以左上角第一个像素为准。
  2. 图片高度不得小于 1000 像素，否则可能无法正确识别结构。
  3. 处理后的图片默认保存在当前目录，命名格式为：
        output-原文件名-新d值px.png     （Stable模式）
        output-原文件名-新d值px-lzr.png （Lazer 模式）
  4. 如果原图不符合预期结构（例如找不到面尾/面身），程序会报错并返回菜单。
  5. 本程序暂不支持渐变颜色面身、非单一颜色或含有图案面身的皮肤。
  6. 如果你遇到任何问题，请在GitHub仓库上提交issue或联系作者。
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
    current_mode = "stable"

    while True:
        if current_image_path is None:
            print(f"\n\n{Color.OKCYAN}[提示: 如何找到面身文件]{Color.ENDC}")
            print(f"\n对于Stable:\n游戏设置 - 皮肤 - 打开皮肤文件夹 - 找到skin.ini - 找到你想修改的key数(如Keys: 4) - 找到NoteImage*L,*是轨道序号 - 其对应的目录就是图片路径")
            print(f"\n对于Lazer:\n游戏设置 - 皮肤 - 打开皮肤编辑器 - 左上角文件 - 打开外部编辑 - 找到skin.ini -> 后续与Stable相同")
            print(f"\n如果未在skin.ini中找到NoteImage*L, 那么图片应该直接在皮肤目录下，名称为mania-note*L.png\n")
            print(f"\n你可以随时使用 Ctrl+C 退出程序。\n")
            print(f"\n{Color.OKBLUE}请输入图片绝对/相对路径（或直接拖拽图片，输入 q 退出）:{Color.ENDC}")
            path = input().strip()
            if path.lower() == 'q':
                break
            if path.startswith('"') and path.endswith('"'):
                path = path[1:-1]
            elif path.startswith("'") and path.endswith("'"):
                path = path[1:-1]
            if not os.path.isfile(path):
                print(f"{Color.FAIL}文件不存在，请重新输入。{Color.ENDC}")
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext != '.png':
                print(f"{Color.FAIL}仅支持 PNG 格式图片。{Color.ENDC}")
                continue
            try:
                with Image.open(path) as tmp:
                    if tmp.height < 1000:
                        print(f"{Color.FAIL}图片高度小于 1000 像素，可能无法正确处理。{Color.ENDC}")
                        continue
            except Exception as e:
                print(f"{Color.FAIL}无法打开图片: {e}{Color.ENDC}")
                continue
            current_image_path = path
            
        clear_screen()
        print(f"\n{Color.OKGREEN}当前图片: {Color.BOLD}{current_image_path}{Color.ENDC}")
        mode_label = "Stable" if current_mode == "stable" else "Lazer"
        print(f"{Color.OKGREEN}当前模式: {Color.BOLD}{mode_label}{Color.ENDC}")
        print(f"{Color.OKCYAN}请选择操作:{Color.ENDC}")
        print("  {0} - 帮助".format(Color.WARNING + "0" + Color.ENDC))
        print("  {0} - 切换模式".format(Color.OKBLUE + "1" + Color.ENDC))
        print("  {0} - 查看当前投机取巧程度".format(Color.OKBLUE + "2" + Color.ENDC))
        print("  {0} - 修改投机取巧程度".format(Color.OKBLUE + "3" + Color.ENDC))
        print("  {0} - 更换图片".format(Color.OKBLUE + "4" + Color.ENDC))
        print("  {0} - 检查更新".format(Color.OKBLUE + "5" + Color.ENDC))
        print("  {0} - 退出".format(Color.OKBLUE + "6" + Color.ENDC))
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
                base = os.path.basename(current_image_path)
                name, _ = os.path.splitext(base)
                if current_mode == "lazer":
                    output_name = f"output-{name}-{new_d}px-lzr.png"
                else:
                    output_name = f"output-{name}-{new_d}px.png"
                output_path = os.path.join(os.getcwd(), output_name)
                process_ln_image(current_image_path, new_d, lzr=(current_mode == "lazer"), output_path=output_path)
                print(f"{Color.OKGREEN}处理完成，已保存至: {output_path}{Color.ENDC}")
            except Exception as e:
                print(f"{Color.FAIL}处理失败: {e}{Color.ENDC}")
            input("按回车键继续...")
            clear_screen()
        elif choice == '4':
            current_image_path = None
            clear_screen()
        elif choice == '5':
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
        elif choice == '6':
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