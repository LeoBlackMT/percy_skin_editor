import os
import sys
import requests
from packaging.version import parse as parse_version
from PIL import Image

VERSION = "1.3.0"

_OWNER = "LeoBlackMT"
_REPO = "percy_skin_editor"
_GITHUB_API = "https://api.github.com"

def getch():
    """Return a single character from keyboard input (without Enter)."""
    if os.name == 'nt':
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

def collect_png_targets(path):
    if os.path.isfile(path):
        if os.path.splitext(path)[1].lower() != '.png':
            raise LNImageError("Only PNG images are supported.")
        return [path], "file"
    if os.path.isdir(path):
        pngs = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if os.path.isfile(full) and os.path.splitext(name)[1].lower() == '.png':
                pngs.append(full)
        if not pngs:
            raise LNImageError("No PNG files found in this directory.")
        return pngs, "dir"
    raise LNImageError("Path does not exist. Please try again.")

def validate_image_height(path):
    try:
        with Image.open(path) as tmp:
            if tmp.height < 1000:
                raise LNImageError(f"Image height is less than 1000 pixels and cannot be processed: {path}")
    except LNImageError:
        raise
    except Exception as e:
        raise LNImageError(f"Cannot open image {path}: {e}")

def confirm_action(prompt):
    print(f"{Color.WARNING}{prompt}{Color.ENDC}")
    ans = input("Type y to confirm, any other key to cancel: ").strip().lower()
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

def build_d_values(start_value, end_value, step):
    if step == 0:
        raise LNImageError("Step cannot be 0.")
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
    """Custom exception"""
    pass

def check_update(current_version: str):
    """Check for updates."""
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
    """Return current cut-off value d of the image."""
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
        raise LNImageError("No non-background pixels found. Image may be all background.")
    mid_y = h // 2
    x1 = None
    for x in range(w):
        if img.getpixel((x, mid_y)) != bg:
            x1 = x
            break
    if x1 is None:
        raise LNImageError("Cannot find a non-background pixel near the left middle.")
    x2 = None
    for x in range(w - 1, -1, -1):
        if img.getpixel((x, mid_y)) != bg:
            x2 = x
            break
    if x2 is None:
        raise LNImageError("Cannot find a non-background pixel near the right middle.")

    def find_background_upwards(col, start_y):
        for y in range(start_y, -1, -1):
            px = img.getpixel((col, y))
            if px == bg or px[3] == 0:
                return y
        raise LNImageError(f"Cannot find a background pixel in column {col} from y={start_y} upwards.")

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
        raise LNImageError("No non-background pixels found. Image may be all background.")

    mid_y = h // 2
    x1 = None
    for x in range(w):
        if img.getpixel((x, mid_y)) != bg:
            x1 = x
            break
    if x1 is None:
        raise LNImageError("Cannot find a non-background pixel near the left middle.")
    x2 = None
    for x in range(w - 1, -1, -1):
        if img.getpixel((x, mid_y)) != bg:
            x2 = x
            break
    if x2 is None:
        raise LNImageError("Cannot find a non-background pixel near the right middle.")

    def find_background_upwards(col, start_y):
        for y in range(start_y, -1, -1):
            px = img.getpixel((col, y))
            if px == bg or px[3] == 0:
                return y
        raise LNImageError(f"Cannot find a background pixel in column {col} from y={start_y} upwards.")

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
                raise LNImageError("Gap fill is required, but note body does not exist.")
            if gap > body_h:
                raise LNImageError("Gap to fill is larger than note body height.")
            fill_region = body_region.crop((0, 0, x2 - x1 + 1, gap))
            if body_h - gap > 0:
                body_new = body_region.crop((0, gap, x2 - x1 + 1, body_h))
            else:
                body_new = None
        elif y_target > y:
            overlap = y_target - y
            if body_h == 0:
                raise LNImageError("Overlap removal is required, but note body does not exist.")
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
{Color.OKCYAN}[Menu Description]{Color.ENDC}
  - 0 - Help: Show this help page.
  - 1 - Switch Mode: Toggle between Stable and Lazer.
    Note: In Lazer mode, the minimum d is 75.
  - 2 - View Current d: Available only in single-image mode.
    Not available in directory batch mode.
  - 3 - Modify d:
    Single-image mode outputs one image.
    Directory mode applies the same d to all PNG files in that directory.
    All outputs are written to the output folder.
  - 4 - Single-Image Batch Generation:
    Only available in single-image mode.
    Input start, end, and step to generate a d list, then output one image per d.
    Step cannot be 0; for large counts there is an extra confirmation.
  - 5 - Switch Image: Select a new PNG or directory path.
  - 6 - Check Updates: Query latest release info from GitHub.
  - 7 - Quit: Exit the program.
{Color.OKCYAN}[Notes]{Color.ENDC}
  0. Back up your original image before processing.
  1. PNG only (RGBA). Background color is the top-left pixel.
  2. Height must be at least 1000px.
  3. Output is always saved in ./output with filename format:
      original-name-dpx.png       (Stable)
      original-name-dpx-lzr.png   (Lazer)
  4. If the image structure is invalid (e.g., tail/body not found), the tool returns to menu.
  5. Gradient or patterned note bodies are not supported currently.
  6. Inputting a directory path will batch all .png files in that folder (non-recursive).
  7. If you encounter issues, open an issue on GitHub or contact the author.
{Color.BOLD}{Color.OKGREEN}======================================{Color.ENDC}
"""
    print(help_text)
    input(f"{Color.WARNING}Press Enter to return to menu...{Color.ENDC}")


def main():
    clear_screen()
    print(f"{Color.BOLD}{Color.HEADER}osu!mania Percy Skin Editor - v{VERSION}{Color.ENDC}")
    print(f"{Color.BOLD}{Color.HEADER}Author: Leo_Black{Color.ENDC}")
    print(f"{Color.BOLD}{Color.HEADER}GitHub: LeoBlackMT/percy_skin_editor{Color.ENDC}")
    current_image_path = None
    current_targets = []
    current_source_type = "file"
    current_mode = "stable"

    while True:
        if current_image_path is None:
            print(f"\n\n{Color.OKCYAN}[Tip: How to locate note body files]{Color.ENDC}")
            print("\nFor Stable:\nGame Settings -> Skin -> Open Skin Folder -> find skin.ini -> find target key count (e.g. Keys: 4) -> find NoteImage*L (* is lane index) -> the referenced path is your image path")
            print("\nFor Lazer:\nGame Settings -> Skin -> Open Skin Editor -> top-left File -> Open External Editor -> find skin.ini -> then same process as Stable")
            print("\nIf NoteImage*L is not in skin.ini, image files are usually in skin root as mania-note*L.png\n")
            print("\nYou can press Ctrl+C to exit at any time.\n")
            print(f"\n{Color.OKBLUE}Enter an absolute/relative image or directory path (or drag-and-drop path, q to quit):{Color.ENDC}")
            path = input().strip()
            if path.lower() == 'q':
                break
            path = normalize_input_path(path)
            try:
                targets, source_type = collect_png_targets(path)
                if source_type == "dir":
                    if not confirm_action(f"Warning: directory detected. {len(targets)} .png files will be batch processed. Continue?"):
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
            print(f"\n{Color.OKGREEN}Current directory: {Color.BOLD}{current_image_path}{Color.ENDC}")
            print(f"{Color.OKGREEN}PNG files to process: {Color.BOLD}{len(current_targets)}{Color.ENDC}")
        else:
            print(f"\n{Color.OKGREEN}Current image: {Color.BOLD}{current_image_path}{Color.ENDC}")
        mode_label = "Stable" if current_mode == "stable" else "Lazer"
        print(f"{Color.OKGREEN}Current mode: {Color.BOLD}{mode_label}{Color.ENDC}")
        print(f"{Color.OKCYAN}Select an action:{Color.ENDC}")
        print("  {0} - Help".format(Color.WARNING + "0" + Color.ENDC))
        print("  {0} - Switch mode".format(Color.OKBLUE + "1" + Color.ENDC))
        print("  {0} - View current d".format(Color.OKBLUE + "2" + Color.ENDC))
        print("  {0} - Modify d".format(Color.OKBLUE + "3" + Color.ENDC))
        print("  {0} - Single-image batch generation".format(Color.OKBLUE + "4" + Color.ENDC))
        print("  {0} - Switch image".format(Color.OKBLUE + "5" + Color.ENDC))
        print("  {0} - Check updates".format(Color.OKBLUE + "6" + Color.ENDC))
        print("  {0} - Quit".format(Color.OKBLUE + "7" + Color.ENDC))
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
            print(f"\n{Color.OKGREEN}Switched to {switched_label} mode.{Color.ENDC}")
            input("Press Enter to continue...")
            clear_screen()
        elif choice == '2':
            if current_source_type == "dir":
                print(f"\n{Color.WARNING}Current target is a directory batch, so a single d cannot be shown. Switch to a single image or process directly.{Color.ENDC}")
                input("Press Enter to continue...")
                clear_screen()
                continue
            try:
                d = get_current_d(current_image_path)
                if current_mode == "lazer":
                    d += 75
                print(f"\n{Color.OKGREEN}Current d = {d}px ({mode_label}){Color.ENDC}")
            except Exception as e:
                print(f"\n{Color.FAIL}Failed to read current d: {e}{Color.ENDC}")
            input("Press Enter to continue...")
            clear_screen()
        elif choice == '3':
            if current_mode == "lazer":
                prompt = "Enter new d (integer, minimum 75): "
            else:
                prompt = "Enter new d (integer): "
            print(f"\n{Color.OKBLUE}{prompt}{Color.ENDC}", end='', flush=True)
            try:
                new_d_str = input().strip()
                new_d = int(new_d_str)
            except ValueError:
                print(f"{Color.FAIL}Invalid input. Please enter an integer.{Color.ENDC}")
                input("Press Enter to continue...")
                clear_screen()
                continue
            if current_mode == "lazer" and new_d < 75:
                print(f"{Color.FAIL}Minimum d in Lazer mode is 75.{Color.ENDC}")
                input("Press Enter to continue...")
                clear_screen()
                continue
            try:
                if current_source_type == "dir":
                    if not confirm_action(f"Warning: {len(current_targets)} images will be processed and saved into output. Continue?"):
                        clear_screen()
                        continue

                success, failed, errors, last_output_path = process_targets(
                    current_targets,
                    new_d,
                    lzr=(current_mode == "lazer")
                )

                if failed == 0:
                    if success == 1:
                        print(f"{Color.OKGREEN}Done. Saved to: {last_output_path}{Color.ENDC}")
                    else:
                        print(f"{Color.OKGREEN}Done. {success} images processed successfully. Output directory: {get_output_dir()}{Color.ENDC}")
                else:
                    print(f"{Color.WARNING}Finished with partial failures: success {success}, failed {failed}.{Color.ENDC}")
                    for src, err in errors:
                        print(f"{Color.FAIL}Failed: {src} -> {err}{Color.ENDC}")
                    print(f"{Color.OKGREEN}Successful outputs are in: {get_output_dir()}{Color.ENDC}")
            except Exception as e:
                print(f"{Color.FAIL}Processing failed: {e}{Color.ENDC}")
            input("Press Enter to continue...")
            clear_screen()
        elif choice == '4':
            if current_source_type != "file":
                print(f"{Color.FAIL}This feature supports only a single image target. Please switch image first.{Color.ENDC}")
                input("Press Enter to continue...")
                clear_screen()
                continue

            print(f"\n{Color.OKBLUE}Enter start value (non-negative integer):{Color.ENDC}", end='', flush=True)
            start_str = input().strip()
            print(f"{Color.OKBLUE}Enter end value (non-negative integer):{Color.ENDC}", end='', flush=True)
            end_str = input().strip()
            print(f"{Color.OKBLUE}Enter step (non-negative integer, must not be 0):{Color.ENDC}", end='', flush=True)
            step_str = input().strip()

            try:
                start_value = int(start_str)
                end_value = int(end_str)
                step = int(step_str)
                if start_value < 0 or end_value < 0 or step < 0:
                    raise LNImageError("Start, end, and step must all be non-negative integers.")
                if step == 0:
                    raise LNImageError("Step cannot be 0.")
                d_values = build_d_values(start_value, end_value, step)
                if not d_values:
                    raise LNImageError("Generated list is empty. Please check your inputs.")
                if current_mode == "lazer" and min(d_values) < 75:
                    raise LNImageError("Minimum d in Lazer mode is 75.")
            except Exception as e:
                print(f"{Color.FAIL}Invalid input: {e}{Color.ENDC}")
                input("Press Enter to continue...")
                clear_screen()
                continue

            total = len(d_values)
            print(f"{Color.OKCYAN}This run will use d list: {d_values}{Color.ENDC}")
            if not confirm_action(f"Warning: {total} images will be generated from the current source image. Continue?"):
                clear_screen()
                continue
            if total > 10:
                if not confirm_action(f"Warning again: this will generate {total} images and may take time. Continue?"):
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
                print(f"{Color.OKGREEN}Batch generation completed. Successful outputs: {success}. Output directory: {get_output_dir()}{Color.ENDC}")
            else:
                print(f"{Color.WARNING}Batch generation completed with partial failures: success {success}, failed {failed}.{Color.ENDC}")
                for src, err in errors:
                    print(f"{Color.FAIL}Failed: {src} -> {err}{Color.ENDC}")
                print(f"{Color.OKGREEN}Successful outputs are in: {get_output_dir()}{Color.ENDC}")

            input("Press Enter to continue...")
            clear_screen()
        elif choice == '5':
            current_image_path = None
            current_targets = []
            current_source_type = "file"
            clear_screen()
        elif choice == '6':
            print(f"\n{Color.OKBLUE}Checking for updates...{Color.ENDC}")
            has, latest = check_update(VERSION)
            if not latest:
                print(f"{Color.FAIL}Error: Unable to fetch latest version information.{Color.ENDC}")
            else:
                if has:
                    print(f"{Color.OKGREEN}New version detected: {latest} (current: {VERSION}){Color.ENDC}")
                    print(f"Please visit releases page: https://github.com/{_OWNER}/{_REPO}/releases/latest")
                else:
                    print(f"{Color.OKGREEN}You are already on the latest version: {VERSION}{Color.ENDC}")
            input("Press Enter to continue...")
            clear_screen()
        elif choice == '7':
            print(f"{Color.OKGREEN}Program exited.{Color.ENDC}")
            break
        else:
            print(f"{Color.WARNING}Invalid option. Please try again.{Color.ENDC}")
            input("Press Enter to continue...")
            clear_screen()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Color.WARNING}Interrupted by user. Program exited.{Color.ENDC}")
        sys.exit(0)
