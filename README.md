# roms2img

Windows GUI tool that downloads SNES thumbnail PNGs from the Libretro Thumbnails repository.

## Features
- Recursively scans a selected ROM folder.
- Tries `Named_Boxarts` first, then `Named_Titles`.
- Saves images to a separate output folder as `ROM filename.png`.
- Skips existing PNGs so a run can be resumed.
- Writes `download_report.csv` with success, missing, failed, skipped, and filename-collision records.
- GitHub Actions builds a standalone Windows executable.

## Download the EXE
Open the repository's **Actions** tab, select the latest successful **Build Windows EXE** run, then download the `roms2img-windows-exe` artifact. Extract the ZIP and run `roms2img.exe`.

## Run from source
Python 3.10+ on Windows:
```powershell
python src/roms2img.py
```

## Notes
- Internet access to GitHub is required.
- Matching depends on the official thumbnail filenames. Unmatched ROMs are listed in the CSV; a conservative fallback avoids many incorrect fuzzy matches.
- Since all images go into one flat output folder, ROMs with duplicate base filenames in different subfolders are reported as collisions and are not overwritten.
- This tool downloads PNGs from [Libretro Thumbnails](https://github.com/libretro-thumbnails/Nintendo_-_Super_Nintendo_Entertainment_System). Follow the source project's terms and rights notices.
