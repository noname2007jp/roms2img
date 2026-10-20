import csv, json, os, re, threading, time, urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

REPO = "libretro-thumbnails/Nintendo_-_Super_Nintendo_Entertainment_System"
BRANCH = "master"
API = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"
EXTS = ".sfc,.smc,.fig,.swc,.zip,.7z,.bin"
UA = "roms2img/1.0"
LIBRETRO_BASE = "https://thumbnails.libretro.com/"
DEFAULT_SYSTEM = "Nintendo - Super Nintendo Entertainment System"
THUMB_TYPES = [("Named_Boxarts", "パッケージ画像"), ("Named_Snaps", "ゲーム画面"), ("Named_Titles", "タイトル画面")]
_THUMB_INDEX = {}

def get_bytes(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def norm(s):
    s = Path(s).stem.replace("_", " ").replace("&", "_")
    s = re.sub(r"\s+", " ", s).strip().casefold()
    return s

def keys(filename):
    stem = Path(filename).stem
    variants = [stem]
    # Common region/revision suffixes are fallback candidates, never the first choice.
    variants.append(re.sub(r"\s*[\[(][^\])]*[\])]\s*", " ", stem))
    variants.append(re.sub(r"\s*\((?:USA|Europe|Japan|World|En|Rev\s*\d+)[^)]*\)", "", stem, flags=re.I))
    result = []
    for v in variants:
        k = norm(v)
        if k and k not in result:
            result.append(k)
    return result


SEARCH_BASE = "https://thegamesdb.net/search.php"
def search_term(filename):
    # Remove extension, then remove trailing region/revision tags such as (Japan) or [Rev 1].
    stem = Path(filename).stem
    stem = re.sub(r"\s*[\[(][^\])]*[\])]\s*$", "", stem).strip()
    return re.sub(r"\s+", " ", stem)

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.links = []
        self._img_context = None
        self._anchor = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "img":
            src = a.get("data-src") or a.get("src") or a.get("data-original")
            if src:
                self.images.append((src, a.get("alt", ""), a.get("title", "")))
        elif tag == "a":
            href = a.get("href", "")
            if href:
                self._anchor = {"href": href, "text": ""}
    def handle_data(self, data):
        if self._anchor is not None:
            self._anchor["text"] += data
    def handle_endtag(self, tag):
        if tag == "a" and self._anchor is not None:
            self.links.append(self._anchor)
            self._anchor = None

def page_parser(url):
    data = get_bytes(url, timeout=30)
    parser = PageParser()
    parser.feed(data.decode("utf-8", errors="replace"))
    return parser

def image_candidates(parser, base_url):
    # Prefer cover/box-art images, ignore UI icons and tiny site assets.
    items = []
    for src, alt, title in parser.images:
        full = urllib.parse.urljoin(base_url, src)
        low = full.lower()
        if not low.startswith(("http://", "https://")):
            continue
        if any(x in low for x in ("logo", "avatar", "icon", "flag", "spinner", "favicon")):
            continue
        score = 0
        if "boxart" in low or "box-art" in low or "box_art" in low: score += 10
        if "cover" in low or "front" in low: score += 5
        if any(x in low for x in (".png", ".jpg", ".jpeg", ".webp")): score += 2
        if "thegamesdb" in low: score += 1
        items.append((score, full))
    return [u for _, u in sorted(items, key=lambda x: x[0], reverse=True)]

def find_thegamesdb_image(filename):
    term = search_term(filename)
    if not term:
        raise ValueError("検索用ファイル名が空です")
    query = urllib.parse.urlencode([("name", term), ("platform_id[]", "0")])
    search_url = SEARCH_BASE + "?" + query
    parser = page_parser(search_url)
    candidates = image_candidates(parser, search_url)
    if candidates:
        return candidates[0], search_url
    # Search result pages may not include cover images; inspect matching game detail pages.
    game_links = []
    for link in parser.links:
        href = link["href"]
        if "game.php" in href and "id=" in href:
            full = urllib.parse.urljoin(search_url, href)
            if full not in game_links:
                game_links.append(full)
    last_error = None
    for detail_url in game_links[:8]:
        try:
            detail = page_parser(detail_url)
            candidates = image_candidates(detail, detail_url)
            if candidates:
                return candidates[0], detail_url
        except Exception as e:
            last_error = e
    if last_error:
        raise ValueError(f"検索結果から画像を取得できませんでした: {last_error}")
    raise ValueError("検索結果に画像がありませんでした")

def libretro_system_url(system_name, thumb_type):
    # URL path is based on the Libretro playlist/system name, not the local ROM folder.
    return LIBRETRO_BASE + urllib.parse.quote(system_name, safe="") + "/" + thumb_type + "/"

def listing_names(url):
    if url in _THUMB_INDEX:
        return _THUMB_INDEX[url]
    parser = page_parser(url)
    names = set()
    for link in parser.links:
        href = link.get("href", "")
        name = urllib.parse.unquote(href.rsplit("/", 1)[-1])
        if name.lower().endswith(".png") and "/" not in name and name not in (".", ".."):
            names.add(name)
    _THUMB_INDEX[url] = names
    return names

def libretro_candidates(filename):
    # Try the exact ROM basename first, including region tags such as (Japan).
    # Then try common filename variants. Keep image type priority explicit.
    stem = Path(filename).stem
    variants = [stem]
    variants.append(re.sub(r"[&*/:< >?\\\\|]", "_", stem))
    variants.extend([Path(v).stem for v in keys(filename)])
    seen = set()
    for thumb_type, label in THUMB_TYPES:
        folder_url = libretro_system_url(system_name_for_run, thumb_type)
        names = listing_names(folder_url)
        names_by_fold = {name.casefold(): name for name in names}
        for variant in variants:
            candidate = variant + ".png"
            actual_name = names_by_fold.get(candidate.casefold())
            if actual_name and actual_name.casefold() not in seen:
                seen.add(actual_name.casefold())
                return urllib.parse.urljoin(folder_url, urllib.parse.quote(actual_name, safe="")), label, folder_url
    return None

def write_report(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ROM", "結果", "画像種別", "保存先", "詳細"])
        w.writerows(rows)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("roms2img - SNES画像一括ダウンローダー")
        self.geometry("850x610")
        self.minsize(760, 540)
        self.rom_dir = tk.StringVar()
        self.out_dir = tk.StringVar()
        self.exts = tk.StringVar(value=EXTS)
        self.system_name = tk.StringVar(value=DEFAULT_SYSTEM)
        self.skip = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="ROMフォルダと画像保存先を指定してください。")
        self.stop_event = threading.Event()
        self.busy = False
        self.build()

    def build(self):
        f = ttk.Frame(self, padding=10); f.pack(fill="both", expand=True)
        ttk.Label(f, text="ROMフォルダ").grid(row=0, column=0, sticky="w", padx=6, pady=5)
        ttk.Entry(f, textvariable=self.rom_dir).grid(row=0, column=1, sticky="ew", padx=6, pady=5)
        ttk.Button(f, text="参照...", command=self.choose_rom).grid(row=0, column=2, padx=6, pady=5)
        ttk.Label(f, text="画像保存先").grid(row=1, column=0, sticky="w", padx=6, pady=5)
        ttk.Entry(f, textvariable=self.out_dir).grid(row=1, column=1, sticky="ew", padx=6, pady=5)
        ttk.Button(f, text="参照...", command=self.choose_out).grid(row=1, column=2, padx=6, pady=5)
        ttk.Label(f, text="対象拡張子").grid(row=2, column=0, sticky="w", padx=6, pady=5)
        ttk.Entry(f, textvariable=self.exts).grid(row=2, column=1, sticky="ew", padx=6, pady=5)
        ttk.Label(f, text="Libretroシステム名").grid(row=3, column=0, sticky="w", padx=6, pady=5)
        ttk.Entry(f, textvariable=self.system_name).grid(row=3, column=1, sticky="ew", padx=6, pady=5)
        ttk.Checkbutton(f, text="既存PNGをスキップして再開", variable=self.skip).grid(row=4, column=1, sticky="w", padx=6, pady=5)
        ttk.Label(f, text="取得順：Libretroのパッケージ画像 → ゲーム画面 → タイトル画面 → TheGamesDB。").grid(row=5, column=0, columnspan=3, sticky="w", padx=6, pady=5)
        self.bar = ttk.Progressbar(f, mode="determinate"); self.bar.grid(row=6, column=0, columnspan=3, sticky="ew", padx=6, pady=5)
        ttk.Label(f, textvariable=self.status).grid(row=7, column=0, columnspan=3, sticky="w", padx=6, pady=5)
        self.log = tk.Text(f, height=19, wrap="word", state="disabled"); self.log.grid(row=8, column=0, columnspan=3, sticky="nsew", padx=6, pady=5)
        buttons = ttk.Frame(f); buttons.grid(row=9, column=0, columnspan=3, sticky="w", padx=6, pady=5)
        self.start_btn = ttk.Button(buttons, text="開始", command=self.start); self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(buttons, text="停止", command=self.stop, state="disabled"); self.stop_btn.pack(side="left", padx=8)
        ttk.Button(buttons, text="保存先を開く", command=self.open_output).pack(side="left")
        f.columnconfigure(1, weight=1); f.rowconfigure(8, weight=1)

    def choose_rom(self):
        p = filedialog.askdirectory(title="SNES ROMフォルダ")
        if p:
            self.rom_dir.set(p)
            if not self.out_dir.get(): self.out_dir.set(str(Path(p).parent / "snes_images"))

    def choose_out(self):
        p = filedialog.askdirectory(title="画像保存先フォルダ")
        if p: self.out_dir.set(p)

    def log_line(self, s):
        def update():
            self.log.configure(state="normal"); self.log.insert("end", s + "\n")
            self.log.see("end"); self.log.configure(state="disabled")
        self.after(0, update)

    def set_status(self, s): self.after(0, lambda: self.status.set(s))

    def start(self):
        if self.busy: return
        rom = Path(self.rom_dir.get().strip())
        out = Path(self.out_dir.get().strip())
        if not rom.is_dir():
            messagebox.showerror("入力エラー", "有効なROMフォルダを選択してください。"); return
        if not self.out_dir.get().strip():
            messagebox.showerror("入力エラー", "画像保存先を指定してください。"); return
        self.busy = True; self.stop_event.clear()
        self.start_btn.configure(state="disabled"); self.stop_btn.configure(state="normal")
        self.log.configure(state="normal"); self.log.delete("1.0", "end"); self.log.configure(state="disabled")
        system_name = self.system_name.get().strip()
        if not system_name:
            messagebox.showerror("入力エラー", "Libretroシステム名を入力してください。"); self.busy = False; self.start_btn.configure(state="normal"); self.stop_btn.configure(state="disabled"); return
        if not messagebox.askyesno("システム名の確認", f"Libretroの画像フォルダ名を次の名前として検索します。\n\n{system_name}\n\nROMフォルダ名とは異なる場合があります。正しいですか？\n\n画像フォルダ例：{system_name}/Named_Boxarts/"):
            self.busy = False; self.start_btn.configure(state="normal"); self.stop_btn.configure(state="disabled"); return
        threading.Thread(target=self.worker, args=(rom, out, self.exts.get(), self.skip.get(), system_name), daemon=True).start()

    def stop(self):
        self.stop_event.set(); self.set_status("停止要求を受け付けました。処理中の通信が終わると停止します。")

    def open_output(self):
        p = self.out_dir.get().strip()
        if p and Path(p).exists(): os.startfile(p)
        else: messagebox.showinfo("案内", "保存先フォルダはまだありません。")

    def finish(self):
        self.busy = False
        self.after(0, lambda: self.start_btn.configure(state="normal"))
        self.after(0, lambda: self.stop_btn.configure(state="disabled"))

    def worker(self, rom_dir, out_dir, ext_text, skip_existing, system_name):
        global system_name_for_run
        system_name_for_run = system_name
        rows = []
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            exts = {"." + x.strip().lower().lstrip(".") for x in ext_text.split(",") if x.strip()}
            roms = sorted(p for p in rom_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts)
            if not roms:
                self.set_status("対象ROMがありません。拡張子設定を確認してください。")
                return
            counts = {}
            for p in roms:
                counts[p.stem.casefold()] = counts.get(p.stem.casefold(), 0) + 1
            self.after(0, lambda: self.bar.configure(maximum=len(roms), value=0))
            self.set_status(f"{len(roms)}件を検出。Libretroの画像を検索しています...")
            ok = missing = failed = skipped = collisions = 0
            for i, rom in enumerate(roms, 1):
                if self.stop_event.is_set():
                    rows.append([str(rom), "停止", "", "", "利用者が停止"])
                    break
                dest = out_dir / (rom.stem + ".png")
                if counts[rom.stem.casefold()] > 1:
                    collisions += 1
                    rows.append([str(rom), "同名衝突", "", str(dest), "保存先に同名ファイルを作れないため未処理"])
                    self.log_line("[同名衝突] " + rom.name)
                    self.after(0, lambda value=i: self.bar.configure(value=value))
                    continue
                if skip_existing and dest.exists() and dest.stat().st_size:
                    skipped += 1
                    rows.append([str(rom), "スキップ", "", str(dest), "既存PNG"])
                    self.after(0, lambda value=i: self.bar.configure(value=value))
                    continue
                try:
                    libretro_error = None
                    try:
                        libretro = libretro_candidates(rom.name)
                    except Exception as e:
                        libretro = None
                        libretro_error = str(e)
                    if libretro:
                        image_url, image_kind, source_page = libretro
                        source_name = "Libretro/" + image_kind
                    else:
                        image_url, source_page = find_thegamesdb_image(rom.name)
                        image_kind = "TheGamesDB"
                        source_name = "TheGamesDB"
                        if libretro_error:
                            source_page += " | Libretro lookup error: " + libretro_error
                    data = get_bytes(image_url)
                    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                        # TheGamesDB may serve JPEG artwork. Convert to PNG when Pillow is available.
                        try:
                            from PIL import Image
                            import io
                            img = Image.open(io.BytesIO(data)).convert("RGBA")
                            tmp = dest.with_name(dest.name + ".part")
                            img.save(tmp, format="PNG")
                            tmp.replace(dest)
                        except ImportError:
                            raise ValueError("画像がPNG形式ではありません。PNG変換にはPillowが必要です")
                    else:
                        tmp = dest.with_name(dest.name + ".part")
                        tmp.write_bytes(data)
                        tmp.replace(dest)
                    ok += 1
                    rows.append([str(rom), "成功", source_name, str(dest), source_page + " | " + image_url])
                    self.log_line(f"[成功] {rom.name} ← {source_name}")
                except Exception as e:
                    missing += 1
                    rows.append([str(rom), "未取得", "", "", str(e)])
                    self.log_line(f"[未取得] {rom.name}: {e}")
                self.after(0, lambda value=i: self.bar.configure(value=value))
                self.set_status(f"{i}/{len(roms)} | 成功 {ok} | 未取得 {missing} | 失敗 {failed} | スキップ {skipped}")
                time.sleep(0.15)
            report = out_dir / "download_report.csv"
            write_report(report, rows)
            self.set_status(f"終了 | 成功 {ok} | 未取得 {missing} | 失敗 {failed} | スキップ {skipped} | 同名衝突 {collisions}")
            self.log_line("結果CSV: " + str(report))
            self.after(0, lambda: messagebox.showinfo("処理終了", f"成功: {ok}\n未取得: {missing}\n失敗: {failed}\nスキップ: {skipped}\n同名衝突: {collisions}\n\n{report}"))
        except Exception as e:
            self.log_line("[エラー] " + str(e))
            self.set_status("エラー: " + str(e))
            self.after(0, lambda msg=str(e): messagebox.showerror("エラー", msg))
        finally:
            self.finish()

if __name__ == "__main__":
    App().mainloop()
