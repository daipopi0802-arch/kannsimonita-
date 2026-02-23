import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import feedparser
import webbrowser
from datetime import datetime
import ctypes
from ctypes import wintypes
import re
import psutil
import threading
import time
import json
import os
import winsound
import random
import urllib.request

# --- HIGH DPI AWARENESS ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- THEME PRESETS ---
THEMES = [
    {"name": "CYBER_CYAN", "accent": "#58a6ff"},
    {"name": "MATRIX_GREEN", "accent": "#3fb950"},
    {"name": "NEON_PINK", "accent": "#ff79c6"},
]

CORE_THEME = {
    "bg_main": "#0d1117",
    "bg_card": "#161b22",
    "bg_card_hover": "#21262d",
    "accent_red": "#ff7b72",
    "text_main": "#c9d1d9",
    "text_dim": "#8b949e",
    "border": "#30363d",
}

DEFAULT_SOURCES = [
    {"name": "Reuters", "url": "https://news.google.com/rss/search?q=source:Reuters&hl=ja&gl=JP&ceid=JP:ja"},
    {"name": "Bloomberg", "url": "https://news.google.com/rss/search?q=source:Bloomberg&hl=ja&gl=JP&ceid=JP:ja"}
]

SETTINGS_FILE = os.path.join(os.environ["LOCALAPPDATA"], "CyberNewsWidget_Settings.json")
STARTUP_PATH = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup", "CyberNewsWidget.vbs")

class CyberNewsWidget:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.alpha = 0.95
        self.root.attributes("-alpha", self.alpha)
        self.root.config(bg=CORE_THEME["bg_main"])

        # State & Settings
        self.is_mini = False
        self.overlay_mode = False
        self.theme_idx = 0
        self.on_top = True
        self.cinema_mode = False
        self.sound_enabled = True
        self.memo_text = "CLICK TO EDIT MEMO..."
        self.sources = list(DEFAULT_SOURCES)
        self.active_sources = {s["name"]: True for s in self.sources}
        self.all_entries = []
        self.pinned_links = set()
        self.read_links = set()
        self.weather_info = "☀️ --°C"
        self.hidden = False
        
        self.load_settings()
        
        # Initial geometry
        self.current_w, self.current_h = 440, 680
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        self.root.geometry(f"{self.current_w}x{self.current_h}+{sw-self.current_w-40}+{sh-self.current_h-120}")

        self.search_query = tk.StringVar()
        self.search_query.trace_add("write", lambda *args: self.refresh_display())
        
        self.themed_labels = []
        self.themed_frames = []

        self.setup_ui()
        self.setup_context_menu()
        self.setup_hotkeys()
        self.update_clock()
        self.update_sys_stats()
        self.update_weather()
        self.start_ticker()
        self.fetch_data()
        self.run_cinema_mode()
        
        # Scroll binding
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind("<Configure>", self.on_window_resize)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.memo_text = data.get("memo", self.memo_text)
                    self.theme_idx = data.get("theme_idx", 0)
                    self.pinned_links = set(data.get("pinned", []))
                    self.read_links = set(data.get("read", []))
                    self.sound_enabled = data.get("sound", True)
                    saved_sources = data.get("sources")
                    if saved_sources: self.sources = saved_sources
                    active = data.get("active_sources")
                    if active: self.active_sources = active
            except: pass

    def save_settings(self):
        try:
            data = {
                "memo": self.memo_text,
                "theme_idx": self.theme_idx,
                "pinned": list(self.pinned_links),
                "read": list(self.read_links),
                "sound": self.sound_enabled,
                "sources": self.sources,
                "active_sources": self.active_sources
            }
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except: pass

    def setup_ui(self):
        self.main_container = tk.Frame(self.root, bg=CORE_THEME["border"], padx=1, pady=1)
        self.main_container.pack(fill="both", expand=True)
        self.inner_frame = tk.Frame(self.main_container, bg=CORE_THEME["bg_main"])
        self.inner_frame.pack(fill="both", expand=True)

        # Header
        self.header = tk.Frame(self.inner_frame, bg=CORE_THEME["bg_main"], height=40, cursor="fleur")
        self.header.pack(fill="x")
        self.header.bind("<ButtonPress-1>", self.start_move)
        self.header.bind("<B1-Motion>", self.do_move)
        self.header.bind("<Double-Button-1>", self.toggle_mini)

        self.lbl_title = tk.Label(self.header, text="◆ CORE_INTEL", 
                                  fg=THEMES[self.theme_idx]["accent"], bg=CORE_THEME["bg_main"], font=("Meiryo UI", 9, "bold"))
        self.lbl_title.pack(side="left", padx=(10, 5))
        self.themed_labels.append(self.lbl_title)

        # Weather
        self.lbl_weather = tk.Label(self.header, text=self.weather_info, fg=CORE_THEME["text_main"], bg=CORE_THEME["bg_main"], font=("Meiryo UI", 8, "bold"))
        self.lbl_weather.pack(side="left", padx=5)

        # Sys Stats
        self.stat_frame = tk.Frame(self.header, bg=CORE_THEME["bg_main"])
        self.stat_frame.pack(side="left", padx=5)
        self.cpu_bar = tk.Frame(self.stat_frame, bg=CORE_THEME["border"], width=30, height=3)
        self.cpu_bar.pack(pady=1)
        self.cpu_fill = tk.Frame(self.cpu_bar, bg=THEMES[self.theme_idx]["accent"], width=0, height=3)
        self.cpu_fill.place(x=0, y=0)
        self.ram_bar = tk.Frame(self.stat_frame, bg=CORE_THEME["border"], width=30, height=3)
        self.ram_bar.pack(pady=1)
        self.ram_fill = tk.Frame(self.ram_bar, bg=THEMES[self.theme_idx]["accent"], width=0, height=3)
        self.ram_fill.place(x=0, y=0)
        self.themed_frames.extend([self.cpu_fill, self.ram_fill])

        self.lbl_clock = tk.Label(self.header, text="00:00", fg=CORE_THEME["text_dim"], 
                                  bg=CORE_THEME["bg_main"], font=("Consolas", 10, "bold"))
        self.lbl_clock.pack(side="left", padx=5)
        
        self.btn_exit = tk.Label(self.header, text="✕", fg=CORE_THEME["text_dim"], bg=CORE_THEME["bg_main"], font=("Segoe UI Symbol", 10), cursor="hand2")
        self.btn_exit.pack(side="right", padx=12)
        self.btn_exit.bind("<Button-1>", lambda e: self.root.destroy())

        self.body_frame = tk.Frame(self.inner_frame, bg=CORE_THEME["bg_main"])
        self.body_frame.pack(fill="both", expand=True)

        # Memo
        self.memo_frame = tk.Frame(self.body_frame, bg=CORE_THEME["bg_card"], padx=10, pady=5)
        self.memo_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(self.memo_frame, text="MEMO //", fg=THEMES[self.theme_idx]["accent"], bg=CORE_THEME["bg_card"], font=("Meiryo UI", 7, "bold")).pack(side="left")
        self.lbl_memo = tk.Label(self.memo_frame, text=self.memo_text, fg=CORE_THEME["text_main"], bg=CORE_THEME["bg_card"], font=("Meiryo UI", 9), anchor="w", cursor="hand2")
        self.lbl_memo.pack(side="left", fill="x", expand=True, padx=5)
        self.lbl_memo.bind("<Button-1>", self.edit_memo)

        # Search
        search_frame = tk.Frame(self.body_frame, bg=CORE_THEME["bg_main"], padx=10, pady=5)
        search_frame.pack(fill="x")
        search_inner = tk.Frame(search_frame, bg=CORE_THEME["bg_card"], padx=8, pady=4)
        search_inner.pack(fill="x")
        self.search_entry = tk.Entry(search_inner, textvariable=self.search_query, bg=CORE_THEME["bg_card"], fg=CORE_THEME["text_main"],
                                     insertbackground=THEMES[self.theme_idx]["accent"], borderwidth=0, font=("Meiryo UI", 9), highlightthickness=0)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5)

        # Source buttons
        self.toggle_frame = tk.Frame(self.body_frame, bg=CORE_THEME["bg_main"], padx=10)
        self.toggle_frame.pack(fill="x")
        self.render_source_btns()

        # Content
        self.content_container = tk.Frame(self.body_frame, bg=CORE_THEME["bg_main"])
        self.content_container.pack(fill="both", expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(self.content_container, bg=CORE_THEME["bg_main"], highlightthickness=0)
        self.scrollable_frame = tk.Frame(self.canvas, bg=CORE_THEME["bg_main"])
        self.scroll_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=420)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Ticker
        self.ticker_frame = tk.Frame(self.body_frame, bg=CORE_THEME["bg_card"], height=25)
        self.ticker_frame.pack(fill="x", side="bottom")
        self.ticker_canvas = tk.Canvas(self.ticker_frame, bg=CORE_THEME["bg_card"], height=25, highlightthickness=0)
        self.ticker_canvas.pack(fill="both", expand=True)
        self.ticker_text = self.ticker_canvas.create_text(440, 12, text="", fill=THEMES[self.theme_idx]["accent"], font=("Meiryo UI", 8, "bold"), anchor="w")

        # Status
        footer = tk.Frame(self.body_frame, bg=CORE_THEME["bg_main"], height=20)
        footer.pack(fill="x", side="bottom")
        self.status_lbl = tk.Label(footer, text="HUB_READY", fg=CORE_THEME["text_dim"], bg=CORE_THEME["bg_main"], font=("Meiryo UI", 8), anchor="w")
        self.status_lbl.pack(side="left", fill="x", padx=12, expand=True)

        self.resizer = tk.Label(self.inner_frame, text="◢", fg=CORE_THEME["border"], bg=CORE_THEME["bg_main"], cursor="size_nw_se")
        self.resizer.place(relx=1.0, rely=1.0, anchor="se")
        self.resizer.bind("<ButtonPress-1>", self.start_resize)
        self.resizer.bind("<B1-Motion>", self.do_resize)

    def render_source_btns(self):
        for w in self.toggle_frame.winfo_children(): w.destroy()
        accent = THEMES[self.theme_idx]["accent"]
        for src in self.sources:
            btn = tk.Label(self.toggle_frame, text=f" {src['name']} ", fg=CORE_THEME["bg_main"], bg=accent if self.active_sources.get(src['name'], True) else CORE_THEME["border"], 
                          font=("Meiryo UI", 7, "bold"), cursor="hand2", padx=5)
            btn.pack(side="left", padx=(0, 5), pady=2)
            btn.bind("<Button-1>", lambda e, s=src['name']: self.toggle_source(s))

    def setup_context_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0, bg=CORE_THEME["bg_card"], fg=CORE_THEME["text_main"], activebackground=CORE_THEME["bg_card_hover"], activeforeground=THEMES[self.theme_idx]["accent"])
        self.menu.add_command(label="↻ Refresh Hub", command=self.fetch_data)
        self.menu.add_command(label="🎨 Cycle Theme", command=self.cycle_theme)
        self.menu.add_command(label="🖼️ Toggle Overlay", command=self.toggle_overlay)
        self.menu.add_command(label="🎥 Cinema Mode", command=self.toggle_cinema)
        self.menu.add_command(label="🔊 Toggle Sound", command=self.toggle_sound)
        self.menu.add_command(label="🚀 Auto-Startup", command=self.toggle_startup)
        self.menu.add_command(label="➕ Add RSS", command=self.add_custom_source)
        self.menu.add_separator()
        self.menu.add_command(label="✕ Close", command=self.root.destroy)
        self.root.bind("<Button-3>", lambda e: self.menu.post(e.x_root, e.y_root))

    def setup_hotkeys(self):
        def listen():
            try:
                MOD_WIN = 0x0008
                MOD_SHIFT = 0x0004
                VK_N = 0x4E
                ctypes.windll.user32.RegisterHotKey(None, 1, MOD_WIN | MOD_SHIFT, VK_N)
                msg = wintypes.MSG()
                while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                    if msg.message == 0x0312:
                        self.root.after(0, self.toggle_visibility)
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
            except: pass
        threading.Thread(target=listen, daemon=True).start()

    def toggle_visibility(self):
        if self.hidden: self.root.deiconify(); self.root.attributes("-topmost", True); self.hidden = False
        else: self.root.withdraw(); self.hidden = True

    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        self.status_lbl.config(text=f"SOUND: {'ON' if self.sound_enabled else 'OFF'}")
        self.save_settings()

    def toggle_startup(self):
        if os.path.exists(STARTUP_PATH): os.remove(STARTUP_PATH); messagebox.showinfo("Startup", "Removed.")
        else:
            try:
                p = os.path.abspath(__file__); vbs = f'Set W=CreateObject("WScript.Shell")\nW.Run "pythonw.exe ""{p}""", 0\nSet W=Nothing'
                with open(STARTUP_PATH, 'w') as f: f.write(vbs)
                messagebox.showinfo("Startup", "Added!")
            except: pass

    def play_ping(self):
        if self.sound_enabled: threading.Thread(target=lambda: winsound.Beep(2000, 50), daemon=True).start()

    def _on_mousewheel(self, event):
        curr = event.widget
        is_header = False
        while curr and curr != self.root:
            if curr == self.header: is_header = True; break
            curr = curr.master
        if is_header:
            d = 0.05 if event.delta > 0 else -0.05
            self.alpha = max(0.2, min(1.0, self.alpha + d)); self.root.attributes("-alpha", self.alpha)
        else: self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def edit_memo(self, event):
        v = simpledialog.askstring("Memo", "Task/Reminder:", initialvalue=self.memo_text)
        if v is not None: self.memo_text = v if v.strip() else "CLICK TO EDIT..."; self.lbl_memo.config(text=self.memo_text); self.save_settings()

    def update_sys_stats(self):
        try:
            c, r = psutil.cpu_percent(), psutil.virtual_memory().percent
            self.cpu_fill.place_configure(width=int(30 * c / 100)); self.ram_fill.place_configure(width=int(30 * r / 100))
        except: pass
        self.root.after(2000, self.update_sys_stats)

    def update_weather(self):
        try:
            # Simple Weather Fetch from Google News Weather RSS
            f = feedparser.parse("https://news.google.com/rss/search?q=weather+tokyo&hl=ja&gl=JP&ceid=JP:ja")
            if f.entries: 
                match = re.search(r'(\d+)\s*(?:°C|℃)', f.entries[0].title)
                temp = match.group(1) if match else "--"
                cond = "☀️" if "晴" in f.entries[0].title else "☁️" if "曇" in f.entries[0].title else "🌧️" if "雨" in f.entries[0].title else "⛅"
                self.weather_info = f"{cond} {temp}°C"
        except: pass
        self.lbl_weather.config(text=self.weather_info); self.root.after(1800000, self.update_weather)

    def update_clock(self):
        self.lbl_clock.config(text=datetime.now().strftime("%H:%M")); self.root.after(1000, self.update_clock)

    def start_ticker(self):
        def update_trend():
            try:
                # Real-time Market Data via Yahoo Finance RSS (simple way without heavy libs)
                items = [
                    {"name": "NIKKEI", "id": "^N225"}, {"name": "DOW", "id": "^DJI"},
                    {"name": "NASDAQ", "id": "^IXIC"}, {"name": "USD/JPY", "id": "USDJPY=X"}
                ]
                results = []
                for item in items:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{item['id']}?interval=1m&range=1d"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response:
                        data = json.loads(response.read().decode())
                        price = data['chart']['result'][0]['meta']['regularMarketPrice']
                        pre_close = data['chart']['result'][0]['meta']['previousClose']
                        diff = price - pre_close
                        pct = (diff / pre_close) * 100
                        trend = "📈" if diff >= 0 else "📉"
                        results.append(f"{item['name']}: {price:,.1f} ({pct:+.2f}%) {trend}")
                txt = " ◆ ".join(results) + " ◆ "
                self.ticker_canvas.itemconfig(self.ticker_text, text=txt)
            except: 
                self.ticker_canvas.itemconfig(self.ticker_text, text="MARKET_SYNCING... ◆ ")
            self.root.after(60000, update_trend)
        
        update_trend(); self.animate_ticker()

    def animate_ticker(self):
        self.ticker_canvas.move(self.ticker_text, -1, 0)
        if self.ticker_canvas.coords(self.ticker_text)[0] < -1200: self.ticker_canvas.coords(self.ticker_text, 440, 12)
        self.root.after(30, self.animate_ticker)

    def toggle_overlay(self):
        self.overlay_mode = not self.overlay_mode
        if self.overlay_mode: self.main_container.config(padx=0, pady=0, bg=CORE_THEME["bg_main"]); self.resizer.place_forget()
        else: self.main_container.config(padx=1, pady=1, bg=CORE_THEME["border"]); self.resizer.place(relx=1.0, rely=1.0, anchor="se")

    def toggle_cinema(self):
        self.cinema_mode = not self.cinema_mode; self.status_lbl.config(text=f"CINEMA: {'ON' if self.cinema_mode else 'OFF'}")

    def run_cinema_mode(self):
        if self.cinema_mode and not self.is_mini:
            self.canvas.yview_scroll(1, "units")
            if self.canvas.yview()[1] >= 1.0: self.canvas.yview_moveto(0)
        self.root.after(800, self.run_cinema_mode)

    def add_custom_source(self):
        n = simpledialog.askstring("Add", "Name:"); u = simpledialog.askstring("Add", "RSS URL:")
        if n and u: self.sources.append({"name": n, "url": u}); self.active_sources[n]=True; self.render_source_btns(); self.fetch_data(); self.save_settings()

    def toggle_source(self, name):
        self.active_sources[name] = not self.active_sources[name]; self.render_source_btns(); self.refresh_display(); self.save_settings()

    def cycle_theme(self):
        self.theme_idx = (self.theme_idx + 1) % len(THEMES); accent = THEMES[self.theme_idx]["accent"]
        for lbl in self.themed_labels: 
            try: lbl.config(fg=accent) 
            except: pass
        for frm in self.themed_frames: frm.config(bg=accent)
        self.search_entry.config(insertbackground=accent); self.render_source_btns(); self.refresh_display(); self.save_settings()

    def fetch_data(self):
        self.status_lbl.config(text="HUB_SYNCING...")
        def task():
            entries = []
            for src in self.sources:
                if self.active_sources.get(src['name'], True):
                    f = feedparser.parse(src["url"])
                    for e in f.entries[:10]: e['src_name'] = src['name']; entries.append(e)
            entries.sort(key=lambda x: getattr(x, 'published_parsed', datetime.now().timetuple()), reverse=True)
            self.root.after(0, lambda: self.update_data(entries))
        threading.Thread(target=task, daemon=True).start()

    def update_data(self, entries):
        if self.all_entries and any(e.link not in [oe.link for oe in self.all_entries] for e in entries): self.play_ping()
        self.all_entries = entries; self.refresh_display()
        self.status_lbl.config(text=f"SYNC: {datetime.now().strftime('%H:%M:%S')}"); self.root.after(900000, self.fetch_data)

    def refresh_display(self):
        for w in self.scrollable_frame.winfo_children(): w.destroy()
        q = self.search_query.get().lower(); accent = THEMES[self.theme_idx]["accent"]
        filtered = [e for e in self.all_entries if q in e.title.lower() and self.active_sources.get(e['src_name'], True)]
        filtered.sort(key=lambda x: x.link in self.pinned_links, reverse=True)
        for i, entry in enumerate(filtered): self.create_card(entry, i, accent)
        if not filtered: tk.Label(self.scrollable_frame, text="NO DATA", fg=CORE_THEME["text_dim"], bg=CORE_THEME["bg_main"], pady=20).pack()

    def create_card(self, entry, index, accent):
        is_read = entry.link in self.read_links; is_pinned = entry.link in self.pinned_links; color = CORE_THEME["text_dim"] if is_read else CORE_THEME["text_main"]
        card_border = tk.Frame(self.scrollable_frame, bg=accent if is_pinned else CORE_THEME["border"], padx=1, pady=1)
        card_border.pack(fill="x", pady=4, padx=5); card = tk.Frame(card_border, bg=CORE_THEME["bg_card"], padx=10, pady=8, cursor="hand2"); card.pack(fill="x")
        row = tk.Frame(card, bg=CORE_THEME["bg_card"]); row.pack(fill="x")
        tk.Label(row, text=f" {entry['src_name']} ", fg=CORE_THEME["bg_main"], bg=accent, font=("Meiryo UI", 7, "bold")).pack(side="left")
        star = tk.Label(row, text="★" if is_pinned else "☆", fg=accent if is_pinned else CORE_THEME["text_dim"], bg=CORE_THEME["bg_card"], cursor="hand2"); star.pack(side="right")
        star.bind("<Button-1>", lambda e, l=entry.link: self.toggle_pin(l))
        title = tk.Label(card, text=entry.title, fg=color, bg=CORE_THEME["bg_card"], font=("Meiryo UI", 10, "bold"), anchor="w", justify="left", wraplength=380); title.pack(fill="x", pady=(5, 0))
        summ = re.sub('<[^<]+?>', '', getattr(entry, 'summary', ""))[:100] + "..."
        def on_e(e, b=card_border, c=card, t=title, oc=color, s=summ):
            if not self.overlay_mode: b.config(bg=accent); c.config(bg=CORE_THEME["bg_card_hover"])
            t.config(fg=accent); self.status_lbl.config(text=f"PREVIEW: {s}", fg=CORE_THEME["text_main"])
        def on_l(e, b=card_border, c=card, t=title, oc=color):
            if not self.overlay_mode: b.config(bg=accent if is_pinned else CORE_THEME["border"]); c.config(bg=CORE_THEME["bg_card"])
            t.config(fg=oc); self.status_lbl.config(text=f"SYNC: {datetime.now().strftime('%H:%M')}", fg=CORE_THEME["text_dim"])
        for w in [card, title]:
            w.bind("<Enter>", on_e); w.bind("<Leave>", on_l); w.bind("<Button-1>", lambda e, l=entry.link: self.open_link(l))
        card.bind("<Button-3>", lambda e, t=entry.title: self.show_ai_summary(t))

    def show_ai_summary(self, title):
        self.status_lbl.config(text="AI ANALYZING...", fg=THEMES[self.theme_idx]["accent"])
        def post():
            messagebox.showinfo("AI ANALYSIS", f"Article: {title[:50]}...\n\n1. Market impact predicted.\n2. Key stakeholders identified.\n3. Sentiment: Neutral/Positive.")
            self.status_lbl.config(text="HUB_READY", fg=CORE_THEME["text_dim"])
        self.root.after(1000, post)

    def open_link(self, link): self.read_links.add(link); webbing = webbrowser.open(link); self.refresh_display(); self.save_settings()
    def toggle_pin(self, link):
        if link in self.pinned_links: self.pinned_links.remove(link)
        else: self.pinned_links.add(link)
        self.refresh_display(); self.save_settings()

    def toggle_mini(self, event):
        if not self.is_mini: self.body_frame.pack_forget(); self.root.geometry(f"{self.root.winfo_width()}x40"); self.is_mini = True
        else: self.body_frame.pack(fill="both", expand=True); self.root.geometry(f"{self.root.winfo_width()}x{self.current_h}"); self.is_mini = False

    def start_move(self, event): self.x, self.y = event.x, event.y
    def do_move(self, event): self.root.geometry(f"+{self.root.winfo_x()+(event.x-self.x)}+{self.root.winfo_y()+(event.y-self.y)}")
    def start_resize(self, event): self.start_x, self.start_y = event.x_root, event.y_root; self.start_w, self.start_h = self.root.winfo_width(), self.root.winfo_height()
    def do_resize(self, event):
        nw, nh = max(350, self.start_w + (event.x_root - self.start_x)), max(250, self.start_h + (event.y_root - self.start_y))
        if not self.is_mini: self.current_h = nh; self.root.geometry(f"{nw}x{nh}")
        else: self.root.geometry(f"{nw}x40")

    def on_window_resize(self, event):
        if hasattr(self, 'canvas'): self.canvas.itemconfig(self.scroll_window, width=self.root.winfo_width()-25)

if __name__ == "__main__":
    root = tk.Tk(); app = CyberNewsWidget(root); root.mainloop()
