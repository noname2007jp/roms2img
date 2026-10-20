import csv, json, os, re, threading, time, urllib.parse, urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

REPO = "libretro-thumbnails/Nintendo_-_Super_Nintendo_Entertainment_System"
BRANCH = "master"
API = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"
EXTS = ".sfc,.smc,.fig,.swc,.zip,.7z,.bin"
UA = "roms2img/1.0"

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
        ttk.Checkbutton(f, text="既存PNGをスキップして再開", variable=self.skip).grid(row=3, column=1, sticky="w", padx=6, pady=5)
        ttk.Label(f, text="画像の取得順：パッケージ画像 → なければタイトル画面。ROMファイル名.png で保存します。").grid(row=4, column=0, columnspan=3, sticky="w", padx=6, pady=5)
        self.bar = ttk.Progressbar(f, mode="determinate"); self.bar.grid(row=5, column=0, columnspan=3, sticky="ew", padx=6, pady=5)
        ttk.Label(f, textvariable=self.status).grid(row=6, column=0, columnspan=3, sticky="w", padx=6, pady=5)
        self.log = tk.Text(f, height=19, wrap="word", state="disabled"); self.log.grid(row=7, column=0, columnspan=3, sticky="nsew", padx=6, pady=5)
        buttons = ttk.Frame(f); buttons.grid(row=8, column=0, columnspan=3, sticky="w", padx=6, pady=5)
        self.start_btn = ttk.Button(buttons, text="開始", command=self.start); self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(buttons, text="停止", command=self.stop, state="disabled"); self.stop_btn.pack(side="left", padx=8)
        ttk.Button(buttons, text="保存先を開く", command=self.open_output).pack(side="left")
        f.columnconfigure(1, weight=1); f.rowconfigure(7, weight=1)

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
        threading.Thread(target=self.worker, args=(rom, out, self.exts.get(), self.skip.get()), daemon=True).start()

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

    def worker(self, rom_dir, out_dir, ext_text, skip_existing):
        rows = []
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            exts = {"." + x.strip().lower().lstrip(".") for x in ext_text.split(",") if x.strip()}
            roms = sorted(p for p in rom_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts)
            if not roms:
                self.set_status("対象ROMがありません。拡張子設定を確認してください。"); return
            counts = {}
            for p in roms: counts[p.stem.casefold()] = counts.get(p.stem.casefold(), 0) + 1
            self.bar.configure(maximum=len(roms)); self.bar["value"] = 0
            self.set_status(f"{len(roms)}件を検出。GitHubの画像一覧を取得しています...")
            tree = json.loads(get_bytes(API).decode("utf-8"))
            paths = [x["path"] for x in tree.get("tree", []) if x.get("type") == "blob"]
            indexes = {}
            for folder, label in [("Named_Boxarts", "パッケージ画像"), ("Named_Titles", "タイトル画面")]:
                idx = {}
                for path in paths:
                    if path.startswith(folder + "/") and path.lower().endswith(".png"):
                        idx.setdefault(norm(Path(path).name), path)
                indexes[folder] = idx
            ok = missing = failed = skipped = collisions = 0
            for i, rom in enumerate(roms, 1):
                if self.stop_event.is_set():
                    rows.append([str(rom), "停止", "", "", "利用者が停止"]); break
                dest = out_dir / (rom.stem + ".png")
                if counts[rom.stem.casefold()] > 1:
                    collisions += 1; rows.append([str(rom), "同名衝突", "", str(dest), "保存先に同名ファイルを作れないため未処理"])
                    self.log_line("[同名衝突] " + rom.name); continue
                if skip_existing and dest.exists() and dest.stat().st_size:
                    skipped += 1; rows.append([str(rom), "スキップ", "", str(dest), "既存PNG"]); self.bar["value"] = i; continue
                found = None; art = ""
                for key in keys(rom.name):
                    for folder, label in [("Named_Boxarts", "パッケージ画像"), ("Named_Titles", "タイトル画面")]:
                        if key in indexes[folder]:
                            found, art = indexes[folder][key], label; break
                    if found: break
                if not found:
                    # Conservative fuzzy match: accept only a unique prefix/substring candidate.
                    for key in keys(rom.name):
                        for folder, label in [("Named_Boxarts", "パッケージ画像"), ("Named_Titles", "タイトル画面")]:
                            candidates = [p for k, p in indexes[folder].items() if len(key) >= 8 and (k.startswith(key) or key.startswith(k))]
                            if len(candidates) == 1: found, art = candidates[0], label; break
                        if found: break
                if not found:
                    missing += 1; rows.append([str(rom), "未発見", "", "", "一致する画像がありません"])
                    self.log_line("[未発見] " + rom.name); self.bar["value"] = i; continue
                url = RAW + urllib.parse.quote(found, safe="/")
                try:
                    data = get_bytes(url)
                    # Reject Git LFS pointers / text placeholders rather than saving a fake PNG.
                    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise ValueError("配布ファイルがPNG画像ではありません")
                    tmp = dest.with_name(dest.name + ".part")
                    tmp.write_bytes(data); tmp.replace(dest)
                    ok += 1; rows.append([str(rom), "成功", art, str(dest), found])
                    self.log_line(f"[成功] {rom.name} ← {art}")
                except Exception as e:
                    failed += 1; rows.append([str(rom), "失敗", art, str(dest), str(e)])
                    self.log_line(f"[失敗] {rom.name}: {e}")
                self.bar["value"] = i
                self.set_status(f"{i}/{len(roms)} | 成功 {ok} | 未発見 {missing} | 失敗 {failed} | スキップ {skipped}")
                time.sleep(0.05)
            report = out_dir / "download_report.csv"; write_report(report, rows)
            self.set_status(f"終了 | 成功 {ok} | 未発見 {missing} | 失敗 {failed} | スキップ {skipped} | 同名衝突 {collisions}")
            self.log_line("結果CSV: " + str(report))
            self.after(0, lambda: messagebox.showinfo("処理終了", f"成功: {ok}\n未発見: {missing}\n失敗: {failed}\nスキップ: {skipped}\n同名衝突: {collisions}\n\n{report}"))
        except Exception as e:
            self.log_line("[エラー] " + str(e)); self.set_status("エラー: " + str(e))
            self.after(0, lambda: messagebox.showerror("エラー", str(e)))
        finally: self.finish()

if __name__ == "__main__":
    App().mainloop()
