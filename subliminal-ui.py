import os
import threading
import warnings
import importlib.metadata as metadata
import customtkinter as ctk
from tkinter import filedialog
from datetime import datetime
import webbrowser
from PIL import Image
import pystray
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from babelfish import Language


def configure_subliminal():
    try:
        chardet_version = metadata.version("chardet")
    except metadata.PackageNotFoundError:
        chardet_version = None

    if chardet_version:
        warnings.filterwarnings(
            "ignore",
            message=r".*doesn't match a supported version.*",
            category=Warning,
            module="requests",
        )

    from subliminal import download_best_subtitles, save_subtitles, scan_video, region

    region.configure("dogpile.cache.dbm", arguments={"filename": "subliminal_cache.dbm"})
    return download_best_subtitles, save_subtitles, scan_video


download_best_subtitles, save_subtitles, scan_video = configure_subliminal()

# === SABİTLER ===
BG_DARK = "#0f0f0f"
ENTRY_BG = "#1c1c1c"
TEXT_COLOR = "#eeeeee"
HIGHLIGHT = "#26a69a"
HIGHLIGHT_HOVER = "#00897b"
PROGRESS_BG = "#333333"
LOG_BG = "#121212"
ICON_PATH = "icon.png"
video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm']

ctk.set_appearance_mode("dark")

class SubtitleDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🎬 Subliminal Altyazı İndirici")
        self.geometry("780x610")
        self.folder_path = ""
        self.language_code = "tur"
        self.downloading = False
        self.observer = None

        self.configure(bg_color=BG_DARK)
        self.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.lang_menu = ctk.CTkOptionMenu(
            self,
            values=["Türkçe", "İngilizce", "Almanca", "Fransızca", "Rusça", "İtalyanca", "İspanyolca", "Yunanca"],
            command=self.set_language,
            width=180,
            fg_color=HIGHLIGHT,
            button_color=HIGHLIGHT_HOVER,
            text_color="white"
        )
        self.lang_menu.set("Türkçe")
        self.lang_menu.pack(pady=(15, 5), padx=20, anchor="w")

        self.path_frame = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=8)
        self.path_frame.pack(padx=20, pady=(5, 10), fill="x")

        self.path_entry = ctk.CTkEntry(
            self.path_frame,
            placeholder_text="📁 Klasör seçilmedi.",
            text_color=TEXT_COLOR,
            fg_color=ENTRY_BG,
            border_color="#333333",
            height=36
        )
        self.path_entry.pack(side="left", padx=10, pady=10, fill="x", expand=True)
        self.path_entry.configure(state="readonly")

        self.browse_button = ctk.CTkButton(
            self.path_frame,
            text="📂 Gözat",
            width=80,
            fg_color=HIGHLIGHT,
            hover_color=HIGHLIGHT_HOVER,
            text_color="white",
            command=self.browse_folder
        )
        self.browse_button.pack(side="left", padx=(5, 5))

        self.open_button = ctk.CTkButton(
            self.path_frame,
            text="🗁 Aç",
            width=60,
            fg_color=HIGHLIGHT,
            hover_color=HIGHLIGHT_HOVER,
            text_color="white",
            command=self.open_folder
        )
        self.open_button.pack(side="left", padx=(0, 10))

        self.progress = ctk.CTkProgressBar(self, width=720, progress_color="#00e676", fg_color=PROGRESS_BG)
        self.progress.set(0)
        self.progress.pack(pady=(10, 5))

        self.log_box = ctk.CTkScrollableFrame(self, width=740, height=350, fg_color=LOG_BG)
        self.log_box.pack(pady=10)
        self.log_lines = []

        self.ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.ctrl_frame.pack(pady=10)

        self.start_button = ctk.CTkButton(
            self.ctrl_frame,
            text="▶️ Başlat",
            fg_color=HIGHLIGHT,
            hover_color=HIGHLIGHT_HOVER,
            text_color="white",
            command=self.start_download
        )
        self.start_button.pack(side="left", padx=10)

        self.stop_button = ctk.CTkButton(
            self.ctrl_frame,
            text="⏹️ Durdur",
            fg_color="#e53935",
            hover_color="#c62828",
            text_color="white",
            command=self.stop_download,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=10)

    def set_language(self, selection):
        lang_map = {
            "Türkçe": "tur",
            "İngilizce": "eng",
            "Almanca": "deu",
            "Fransızca": "fra",
            "Rusça": "rus",
            "İtalyanca": "ita",
            "İspanyolca": "spa",
            "Yunanca": "ell"
        }
        self.language_code = lang_map.get(selection, "tur")
        self.log(f"🌐 Altyazı dili: {selection} ({self.language_code})", "#90caf9")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path = folder
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder)
            self.path_entry.configure(state="readonly")
            self.start_watching()

    def open_folder(self):
        if os.path.isdir(self.folder_path):
            webbrowser.open(self.folder_path)

    def log(self, text, color="#cccccc"):
        timestamp = datetime.now().strftime("[%H:%M]")
        label = ctk.CTkLabel(self.log_box, text=f"{timestamp} {text}", text_color=color, font=("Consolas", 11), anchor="w")
        label.pack(anchor="w", padx=10)
        self.log_lines.append(label)
        self.log_box._parent_canvas.yview_moveto(1.0)

    def start_download(self):
        if not self.folder_path:
            self.log("❗ Lütfen önce bir klasör seçin.", "#ff6f61")
            return
        self.downloading = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        for line in self.log_lines:
            line.destroy()
        self.log_lines.clear()
        threading.Thread(target=self.download_worker).start()

    def stop_download(self):
        self.downloading = False
        self.log("⛔ İndirme iptal edildi.", "#ffa726")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    def download_worker(self):
        self.log(f"🚀 Başlıyor: {self.folder_path}", "#81c784")
        files = []
        for root, _, filenames in os.walk(self.folder_path):
            for fname in filenames:
                if os.path.splitext(fname)[1].lower() in video_extensions:
                    files.append(os.path.join(root, fname))

        total = len(files)
        for idx, file in enumerate(files, start=1):
            if not self.downloading:
                break
            self.try_download(file)
            self.progress.set(idx / total)

        if self.downloading:
            self.log("✔️ Tüm işlemler tamamlandı.", "#00e676")

        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.downloading = False

    def try_download(self, file):
        srt_path = os.path.splitext(file)[0] + ".srt"
        name = os.path.basename(file)
        if os.path.exists(srt_path):
            self.log(f"✅ Zaten var: {name}", "#aed581")
            return
        self.log(f"⬇️ İndiriliyor: {name}", "#64b5f6")
        try:
            video = scan_video(file)
            subtitles = download_best_subtitles([video], {Language(self.language_code)})
            if subtitles.get(video):
                save_subtitles(video, subtitles[video])
                self.log(f"📄 Kaydedildi: {name}", "#a5d6a7")
            else:
                self.log(f"⚠️ Altyazı bulunamadı: {name}", "#ffd54f")
        except Exception as e:
            self.log(f"❌ Hata: {str(e)}", "#ef5350")

    def start_watching(self):
        if self.observer:
            self.observer.stop()
        handler = NewVideoHandler(self)
        self.observer = Observer()
        self.observer.schedule(handler, self.folder_path, recursive=True)
        self.observer.start()
        self.log("👀 Klasör izleniyor...", "#ffd54f")

    def hide_window(self):
        self.withdraw()

class NewVideoHandler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app

    def on_created(self, event):
        if not event.is_directory:
            ext = os.path.splitext(event.src_path)[1].lower()
            if ext in video_extensions:
                self.app.after(0, lambda: self.app.log(f"🆕 Yeni dosya bulundu: {os.path.basename(event.src_path)}", "#4fc3f7"))
                self.app.after(1000, lambda: self.app.try_download(event.src_path))

def create_tray(app):
    def on_show_hide(icon, item):
        app.after(0, lambda: app.deiconify() if not app.winfo_viewable() else app.withdraw())
    def on_exit(icon, item):
        icon.stop()
        app.after(0, app.destroy)
    try:
        icon_image = Image.open(ICON_PATH)
    except:
        icon_image = Image.new("RGB", (32, 32), color="gray")
    menu = pystray.Menu(
        pystray.MenuItem("Göster/Gizle", on_show_hide),
        pystray.MenuItem("Çıkış", on_exit)
    )
    pystray.Icon("subwatch", icon_image, "Subliminal Altyazı", menu).run_detached()

if __name__ == "__main__":
    app = SubtitleDownloaderApp()
    create_tray(app)
    app.mainloop()
