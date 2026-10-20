# roms2img

Windows GUI tool that searches TheGamesDB by ROM filename and downloads available game artwork as PNG.

## Features
- Recursively scans a selected ROM folder.
- Searches `https://thegamesdb.net/search.php?name=%s&platform_id[]=0` and tries to retrieve artwork from the search result or game detail page.
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
