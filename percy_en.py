import os
import sys
import requests
from packaging.version import parse as parse_version
from PIL import Image

VERSION = "1.1.0"

_OWNER = "LeoBlackMT"
_REPO = "percy_skin_editor"
_GITHUB_API = "https://api.github.com"

def getch():
    """Return the single character pressed by the user (no need to wait for Enter)"""
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
    """Custom exception"""
    pass

def check_update(current_version: str):
    """
    Check for updates on GitHub Releases.
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
    """Return the current cut-off pixels of the image"""
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
        raise LNImageError("No non-background pixels found. Image may be entirely background color.")
    mid_y = h // 2
    x1 = None
    for x in range(w):
        if img.getpixel((x, mid_y)) != bg:
            x1 = x
            break
    if x1 is None:
        raise LNImageError("No non-background pixels found at left mid-point.")
    x2 = None
    for x in range(w-1, -1, -1):
        if img.getpixel((x, mid_y)) != bg:
            x2 = x
            break
    if x2 is None:
        raise LNImageError("No non-background pixels found at right mid-point.")
    def find_background_upwards(col, start_y):
        for y in range(start_y, -1, -1):
            if img.getpixel((col, y)) == bg:
                return y
        raise LNImageError(f"No background pixels found in column {col} from y={start_y} upwards.")
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
        raise LNImageError("No non-background pixels found. Image may be entirely background color.")

    mid_y = h // 2
    x1 = None
    for x in range(w):
        if img.getpixel((x, mid_y)) != bg:
            x1 = x
            break
    if x1 is None:
        raise LNImageError("No non-background pixels found at left mid-point.")
    x2 = None
    for x in range(w-1, -1, -1):
        if img.getpixel((x, mid_y)) != bg:
            x2 = x
            break
    if x2 is None:
        raise LNImageError("No non-background pixels found at right mid-point.")

    def find_background_upwards(col, start_y):
        for y in range(start_y, -1, -1):
            if img.getpixel((col, y)) == bg:
                return y
        raise LNImageError(f"No background pixels found in column {col} from y={start_y} upwards.")
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
                raise LNImageError("Need to fill the gap, but note body does not exist.")
            if gap > body_h:
                raise LNImageError("The gap to be filled is larger than the note body height.")
            fill_region = body_region.crop((0, body_h - gap, x2 - x1 + 1, body_h))
            if body_h - gap > 0:
                body_new = body_region.crop((0, 0, x2 - x1 + 1, body_h - gap))
            else:
                body_new = None
        elif y_target > y:
            overlap = y_target - y
            if body_h == 0:
                raise LNImageError("Need to remove overlapping part, but note body does not exist.")
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
{Color.BOLD}{Color.OKGREEN}========== Help Information =========={Color.ENDC}
{Color.OKCYAN}【What Is a Percy Skin】{Color.ENDC}
    • A percy skin stretches the note body to tens of thousands of pixels, then creates a
        short-tail visual effect by cutting from the top.
    • In high-density LN charts, players often use percy skins for better visual feedback
        and playability.
    • Percy skins can significantly reduce reading pressure, but cannot precisely locate
        the release point.
    • We define "cut off by x pixels" as the distance from the first non-background pixel
        to the top of the image.
    • In this program, we use d to represent this value.
{Color.OKCYAN}【Mode Explanation】{Color.ENDC}
    • Stable Mode: Directly sets a new d value. The program automatically adjusts the
        note tail and body.
    • Lazer Mode: Based on current measurements, the Lazer version in early 2026 may
        incorrectly stretch non-percy skins by about 75px.
        Therefore, any input in this mode is reduced by 75px, with a minimum of 0.
        To prevent excessive stretching, all images are normalized to a fixed height of 32800px.
{Color.OKCYAN}【Important Notes】{Color.ENDC}
    0. Back up the original image before processing or overwriting.
  1. Only supports PNG images (RGBA mode). Background color is determined by the
     first pixel in the top-left corner.
  2. Image height must be at least 1000 pixels, otherwise structure detection may fail.
  3. Processed images are saved in the current directory with the naming format:
        output-filename-Xpx.png     (Stable mode)
        output-filename-Xpx-lzr.png (Lazer mode)
  4. If the original image doesn't match the expected structure (e.g., note tail/body
     not found), the program will report an error and return to the menu.
    5. This program currently does not support gradient, patterned, or other complex
         non-uniform note bodies.
    6. If you encounter any issue, please open an issue on GitHub or contact the author.
{Color.BOLD}{Color.OKGREEN}=====================================
{Color.ENDC}
"""
    print(help_text)
    input(f"{Color.WARNING}Press Enter to return to menu...{Color.ENDC}")



def main():
    clear_screen()
    print(f"{Color.BOLD}{Color.HEADER}osu!mania Percy Skin Editor{Color.ENDC}")
    print(f"{Color.BOLD}{Color.HEADER}Author: Leo_Black{Color.ENDC}")
    print(f"{Color.BOLD}{Color.HEADER}Github: LeoBlackMT/percy_skin_editor{Color.ENDC}")
    current_image_path = None

    while True:
        if current_image_path is None:
            print(f"\n\n{Color.OKCYAN}[Tip: How to find the note body file]{Color.ENDC}")
            print(f"\nFor Stable:\nGame Settings - Skins - Open Skin Folder - Find skin.ini - Find your desired key mode (e.g., Keys: 4) - Find NoteImage*L (* is the track number) - The corresponding directory is the image path")
            print(f"\nFor Lazer:\nGame Settings - Skins - Open Skin Editor - Top-left File menu - Edit Externally - Find skin.ini -> Then follow the same steps as Stable")
            print(f"\nIf 'NoteImage*L' is not found in skin.ini, the image should be directly in the skin folder named 'mania-note*L.png'\n")
            print(f"\n{Color.OKBLUE}Enter the absolute/relative path to the image (or drag the image directly, input 'q' to quit):{Color.ENDC}")
            path = input().strip()
            if path.lower() == 'q':
                break
            if path.startswith('"') and path.endswith('"'):
                path = path[1:-1]
            elif path.startswith("'") and path.endswith("'"):
                path = path[1:-1]
            if not os.path.isfile(path):
                print(f"{Color.FAIL}File not found. Please try again.{Color.ENDC}")
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext != '.png':
                print(f"{Color.FAIL}Only PNG format images are supported.{Color.ENDC}")
                continue
            try:
                with Image.open(path) as tmp:
                    if tmp.height < 1000:
                        print(f"{Color.FAIL}Image height is less than 1000 pixels, processing may fail.{Color.ENDC}")
                        continue
            except Exception as e:
                print(f"{Color.FAIL}Cannot open image: {e}{Color.ENDC}")
                continue
            current_image_path = path
            
        clear_screen()
        print(f"\n{Color.OKGREEN}Current image: {Color.BOLD}{current_image_path}{Color.ENDC}")
        print(f"{Color.OKCYAN}Please select an operation:{Color.ENDC}")
        print("  {0} - Help".format(Color.WARNING + "0" + Color.ENDC))
        print("  {0} - View current cut-off value".format(Color.OKBLUE + "1" + Color.ENDC))
        print("  {0} - Stable Mode: Adjust cut-off value".format(Color.OKBLUE + "2" + Color.ENDC))
        print("  {0} - Lazer Mode: Adjust cut-off value".format(Color.OKBLUE + "3" + Color.ENDC))
        print("  {0} - Switch image".format(Color.OKBLUE + "4" + Color.ENDC))
        print("  {0} - Check updates".format(Color.OKBLUE + "5" + Color.ENDC))
        print("  {0} - Quit".format(Color.OKBLUE + "6" + Color.ENDC))
        print("> ", end='', flush=True)

        choice = getch()
        print(choice)

        if choice == '0':
            clear_screen()
            print_help()
            clear_screen()
        elif choice == '1':
            try:
                d = get_current_d(current_image_path)
                print(f"\n{Color.OKGREEN}Current cut-off value: d = {d}px{Color.ENDC}")
            except Exception as e:
                print(f"\n{Color.FAIL}Failed to get cut-off value: {e}{Color.ENDC}")
            input("Press Enter to continue...")
            clear_screen()
        elif choice == '2':
            print(f"\n{Color.OKBLUE}Enter new cut-off value (integer): {Color.ENDC}", end='', flush=True)
            try:
                new_d_str = input().strip()
                new_d = int(new_d_str)
            except ValueError:
                print(f"{Color.FAIL}Invalid input. Please enter an integer.{Color.ENDC}")
                input("Press Enter to continue...")
                clear_screen()
                continue
            try:
                base = os.path.basename(current_image_path)
                name, _ = os.path.splitext(base)
                output_name = f"output-{name}-{new_d}px.png"
                output_path = os.path.join(os.getcwd(), output_name)
                process_ln_image(current_image_path, new_d, lzr=False, output_path=output_path)
                print(f"{Color.OKGREEN}Processing complete. Saved to: {output_path}{Color.ENDC}")
            except Exception as e:
                print(f"{Color.FAIL}Processing failed: {e}{Color.ENDC}")
            input("Press Enter to continue...")
            clear_screen()
        elif choice == '3':
            print(f"\n{Color.OKBLUE}Enter new cut-off value (integer, minimum 75): {Color.ENDC}", end='', flush=True)
            try:
                new_d_str = input().strip()
                new_d = int(new_d_str)
            except ValueError:
                print(f"{Color.FAIL}Invalid input. Please enter an integer.{Color.ENDC}")
                input("Press Enter to continue...")
                clear_screen()
                continue
            try:
                base = os.path.basename(current_image_path)
                name, _ = os.path.splitext(base)
                output_name = f"output-{name}-{new_d}px-lzr.png"
                output_path = os.path.join(os.getcwd(), output_name)
                process_ln_image(current_image_path, new_d, lzr=True, output_path=output_path)
                print(f"{Color.OKGREEN}Processing complete. Saved to: {output_path}{Color.ENDC}")
            except Exception as e:
                print(f"{Color.FAIL}Processing failed: {e}{Color.ENDC}")
            input("Press Enter to continue...")
            clear_screen()
        elif choice == '4':
            current_image_path = None
            clear_screen()
        elif choice == '5':
            print(f"\n{Color.OKBLUE}Checking for updates...{Color.ENDC}")
            has, latest = check_update(VERSION)
            if not latest:
                print(f"{Color.FAIL}Error: Could not fetch latest version info.{Color.ENDC}")
            else:
                if has:
                    print(f"{Color.OKGREEN}New version detected: {latest} (current: {VERSION}){Color.ENDC}")
                    print(f"Please visit the releases page to download the latest build: https://github.com/{_OWNER}/{_REPO}/releases")
                else:
                    print(f"{Color.OKGREEN}You are already on the latest version: {VERSION}{Color.ENDC}")
            input("Press Enter to continue...")
            clear_screen()
        elif choice == '6':
            print(f"{Color.OKGREEN}Exiting program.{Color.ENDC}")
            break
        else:
            print(f"{Color.WARNING}Invalid option. Please try again.{Color.ENDC}")
            input("Press Enter to continue...")
            clear_screen()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Color.WARNING}User interrupted. Program exiting.{Color.ENDC}")
        sys.exit(0)
