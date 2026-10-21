# roms2img

Windows GUI tool that downloads game artwork as PNG, using Libretro thumbnails by default. TheGamesDB lookup is optional.

## Features
- Recursively scans a selected ROM folder.
- Searches Libretro thumbnail folders in this order: `Named_Snaps` (gameplay screenshots), `Named_Titles` (title screens), `Named_Logos` (logos), then `Named_Boxarts` (box art).
- Matches filenames by token overlap: more matching words are preferred; if candidates match the same number of words, the candidate with fewer extra words wins. For example, `Bio Hazard.png` is preferred over `Bio Hazard 2.png` for `Bio Hazard.zip`.
- When a gameplay screenshot is selected, attempts to find matching `Named_Boxarts` artwork and composites a reduced version on the left side of the screenshot.
- TheGamesDB lookup is disabled by default. Enable **“Libretroで見つからない場合、TheGamesDBでも検索する（誤画像に注意）”** to use it as a fallback when Libretro has no match.
- Provides an editable, searchable dropdown of common Libretro system folder names. Type part of a system name to filter the list; custom names can also be entered. The default for SNES is `Nintendo - Super Nintendo Entertainment System`.
- Asks you to confirm the selected Libretro system folder name before starting; this is independent of the local ROM folder name.
- The Libretro thumbnail directory follows the system/playlist naming convention documented by [Libretro](https://docs.libretro.com/guides/roms-playlists-thumbnails/).
- Saves images to a separate output folder as `ROM filename.png`.
- Skips existing PNGs so a run can be resumed. No CSV report is generated.
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
- Internet access to Libretro thumbnails is required. Internet access to TheGamesDB is needed only when its fallback option is enabled.
- TheGamesDB results can include unrelated editions or platforms; enable this fallback only if you want to try it, and review the downloaded images.
- Since all images go into one flat output folder, ROMs with duplicate base filenames in different subfolders are skipped as filename collisions and are not overwritten.
- Image processing and conversion use Pillow. Follow the image providers' terms and rights notices.
