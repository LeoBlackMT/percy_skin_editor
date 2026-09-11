# Packaged Windows builds

Prebuilt single-file executables produced with PyInstaller.

## v1.6.0

| File | Default UI language |
|---|---|
| `percy.exe` | 中文 |
| `percy_en.exe` | English |

Both executables run the **same** program; `percy_en.exe` is only a thin launcher
that selects English as the default. Either one can be switched at runtime from
menu `L - Language / 语言`, and the choice is saved to `percy_config.json`.

**Source commit:** `b240ee0` (single-key menu, folder scope picker, per-file d)
**Built with:** PyInstaller 6.22.2, Python 3.14.7 (64-bit)

Built with exactly the commands used by `.github/workflows/python-app.yml`:

```
pyinstaller --clean --noconfirm --onefile --name percy percy.py
pyinstaller --clean --noconfirm --onefile --name percy_en percy_en.py
```

## SHA-256

```
0178C4A20A3CDC132BD3F9BB685601834BF5651A62FF9FCA3E3D51018036BB0A  percy.exe
1AB44503AF1834ACAEC7E19D1B70F52522D3B47C57369CD00F58A2CABA75AEA7  percy_en.exe
```

Run `Get-FileHash <file> -Algorithm SHA256` to verify the full digest.

## Usage notes

- Run the executables from a real terminal window (or double-click). In a real
  console the menu responds to a **single keypress** (no Enter needed). When stdin
  is piped — for scripting or automated tests — each line's first character is
  used as the key, and an empty line means Enter.
- Console text is written in the console codepage (GBK on a Chinese Windows),
  which is the correct behaviour for a console application on that system.
- The output folder is resolved relative to the **current working directory**.
  Double-clicking puts outputs in `output/` next to the executable.
- Replace mode (`6 - 调整输出模式` → `2`) overwrites originals, but copies them
  into `backup-archive/<timestamp>/` first.
- Menus `7` (folders) and `L` (language) return to the parent menu when left empty.

## Why these are committed here

The CI workflow uploads the same artifacts to every workflow run, and GitHub
Releases are the better distribution channel. They are committed into this
folder only as a convenience so the binaries are reachable without a release.
Note that they add roughly 38 MB to the repository; consider removing them once
a proper release exists.
