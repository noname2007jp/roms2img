# roms2img

Windows GUI tool that downloads SNES artwork as PNG, using Libretro thumbnails first and TheGamesDB as a fallback.

## Features
- Recursively scans a selected ROM folder.
- Searches Libretro thumbnails in this order: `Named_Boxarts`, `Named_Snaps`, `Named_Titles`.
- Tries the exact ROM filename first (including tags such as `(Japan)`), then filename variants; falls back to TheGamesDB if Libretro has no match.
- Asks you to confirm the Libretro system folder name before starting. The default for SNES is `Nintendo - Super Nintendo Entertainment System`; this is independent of the local ROM folder name.
- The Libretro thumbnail directory follows the system/playlist naming convention documented by [Libretro](https://docs.libretro.com/guides/roms-playlists-thumbnails/).
- Saves images to a separate output folder as `ROM filename.png`.
- Skips existing PNGs so a run can be resumed.
- Writes `download_report.csv` with success, missing, failed, skipped, and filename-collision records.
- GitHub Actions builds a standalone Windows executable.

## Download the EXE
Open the repository's **Actions** tab, select the latest successful **Build Windows EXE** run, then download the `roms2img-windows-exe` artifact. Extract the ZIP and run `roms2img.exe`.

## Run from source
Python 3.10+ on Windows, with Pillow installed:
```powershell
python -m pip install pillow
python src/roms2img.py
```

## Notes
- Internet access to TheGamesDB is required.
- Before searching, removes the ROM extension and a trailing parenthesized/bracketed tag such as `(Japan)` or `[Rev 1]`. TheGamesDB search results can include multiple platforms or editions, so check the downloaded images and `download_report.csv`.
- Since all images go into one flat output folder, ROMs with duplicate base filenames in different subfolders are reported as collisions and are not overwritten.
- This tool retrieves images from [TheGamesDB](https://thegamesdb.net/). JPEG artwork is converted to PNG using Pillow. Follow TheGamesDB's terms and rights notices.
