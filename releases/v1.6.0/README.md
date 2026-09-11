# Packaged Windows builds

Prebuilt single-file executables produced with PyInstaller.

## v1.6.0

| File | Default UI language |
|---|---|
| `percy.exe` | 中文 |
| `percy_en.exe` | English |

Both executables run the **same** program; `percy_en.exe` is only a thin launcher
that selects English as the default. Either one can be switched at runtime from
menu `11 - Language / 语言`, and the choice is saved to `percy_config.json`.

**Source commit:** `036c956e2967f8800f8c4580472cb66c8a35e8fc`
**Built with:** PyInstaller 6.22.2, Python 3.14.7 (64-bit)

Built with exactly the commands used by `.github/workflows/python-app.yml`:

```
pyinstaller --clean --noconfirm --onefile --name percy percy.py
pyinstaller --clean --noconfirm --onefile --name percy_en percy_en.py
```

## SHA-256

```
014AB3496AA14918...  percy.exe
AEB52EECB96E321F...  percy_en.exe
```

Run `Get-FileHash <file> -Algorithm SHA256` to verify the full digest.

## Usage notes

- Run the executables from a real terminal window (or double-click). They read
  menu input from stdin, so piping or redirecting stdin will not drive the menu.
- Console text is written in the console codepage (GBK on a Chinese Windows),
  which is the correct behaviour for a console application on that system.
- The output folder is resolved relative to the **current working directory**.
  Double-clicking puts outputs in `output/` next to the executable.
- Replace mode (`6 - 调整输出模式` → `2`) overwrites originals, but copies them
  into `backup-archive/<timestamp>/` first.

## Why these are committed here

The CI workflow uploads the same artifacts to every workflow run, and GitHub
Releases are the better distribution channel. They are committed into this
folder only as a convenience so the binaries are reachable without a release.
Note that they add roughly 38 MB to the repository; consider removing them once
a proper release exists.
