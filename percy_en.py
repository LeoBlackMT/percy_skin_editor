"""English entry point for Percy Skin Editor.

All of the program logic now lives in percy.py — this file is only a thin
launcher that selects English as the *default* interface language, so the
packaged percy_en.exe starts in English out of the box.

The language can still be switched at runtime from menu
"11 - Language / 语言", and the choice is stored in percy_config.json. Once a
config file exists, the stored choice wins over the default set here.
"""

import percy

if __name__ == "__main__":
    percy.main(default_language="en")
