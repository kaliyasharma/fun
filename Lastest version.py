#!/usr/bin/env python3
"""
Playinmatch GUI:
- Password protection with specific game launching
- Fixed stop betting functionality
- Load users directly in GUI
- Auto-update start volume after betting
- One Time Trigger option for simultaneous betting
- NEW: Dynamic Teams & Runner Name assignment with CSV loading
- NEW: Teams Loader tab for managing team entries

Usage: python gui_app.py
"""

import asyncio
import threading
import queue
import csv
import aiohttp
from bs4 import BeautifulSoup
import re
import pathlib
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Optional
from urllib.parse import parse_qsl, urlencode, unquote_plus, quote
import os
import subprocess
import sys

# ---------------- APPLICATION PASSWORDS ----------------
PASSWORDS = {
    "JumboKing247@": "Launch Playinmatch GUI",
    "admin123": r"C:\XboxGames\Asphalt Legends\Content\Asphalt9_gdk_x64_rtl.exe"  # Game path
}

# ---------------- USER CONFIG ----------------
EVENT_ID = "35105437"
EVENT_URL = f"https://playinhorse/mobile/eventDetails/{EVENT_ID}?type=2"
MAX_CONCURRENT = 100            # concurrency across users (not used yet)
SHOW_DEBUG_HTML = False        # save debug HTML files if True
# Bet delay is now configurable via GUI
# ---------------------------------------------

BASE_URL = "https://playinhorse.com"

# Thread-safe queue for logs
log_queue: "queue.Queue[str]" = queue.Queue()

def enqueue_log(s: str):
    """Put log message into queue (thread-safe)."""
    log_queue.put(s)

def save_debug(name, data):
    path = pathlib.Path("debug_logs")
    path.mkdir(exist_ok=True)
    file = path / f"{name}.txt"
    with open(file, "w", encoding="utf-8") as f:
        f.write(data)
    enqueue_log(f"[DEBUG] Saved → {file}")

def parse_urlencoded_body(raw: str) -> dict:
    """
    Raw x-www-form-urlencoded body (Burp se jo copy karega) ko
    dict me convert karta hai (URL decode included).
    """
    return dict(parse_qsl(raw, keep_blank_values=True))

# ---------------- Password Protection GUI ----------------
class PasswordApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Application Launcher")
        self.root.geometry("500x500")  # Increased height for password display
        self.root.configure(bg="#2c3e50")  # Dark blue background
        
        # Center the window
        self.center_window(500, 500)
        
        # Password attempt counter
        self.password_attempts = 0
        self.max_attempts = 3
        
        # Main container
        self.main_frame = tk.Frame(root, bg="#2c3e50")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Show password screen
        self.show_password_screen()
    
    def center_window(self, width, height):
        """Center the window on screen."""
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
    
    def show_password_screen(self):
        """Show password entry screen."""
        self.clear_frame()
        
        # Title
        title_label = tk.Label(self.main_frame, text="🔐 Asphalt Legends", 
                              font=("Arial", 24, "bold"), bg="#2c3e50", fg="#ecf0f1")
        title_label.pack(pady=(20, 10))
        
        # Subtitle
        subtitle_label = tk.Label(self.main_frame, text="Asphalt Legends Password to Continue",
                                 font=("Arial", 14), bg="#2c3e50", fg="#bdc3c7")
        subtitle_label.pack(pady=(0, 30))
        
        # IMPORTANT: Password Display Box
        password_display_frame = tk.Frame(self.main_frame, bg="#34495e", relief=tk.RAISED, bd=3)
        password_display_frame.pack(pady=(0, 30), padx=20, fill=tk.X)
        
        display_label = tk.Label(password_display_frame, 
                                text="Asphalt Legends Password is admin123",
                                font=("Arial", 16, "bold"), 
                                bg="#34495e", fg="#f1c40f",  # Yellow color for visibility
                                padx=20, pady=15)
        display_label.pack()
        
        # Password frame
        password_frame = tk.Frame(self.main_frame, bg="#2c3e50")
        password_frame.pack(pady=10)
        
        tk.Label(password_frame, text="Asphalt Legends Password:", 
                font=("Arial", 12, "bold"), bg="#2c3e50", fg="#ecf0f1").grid(row=0, column=0, sticky="w", pady=5)
        
        self.password_var = tk.StringVar()
        self.password_entry = tk.Entry(password_frame, textvariable=self.password_var, 
                                      show="*", font=("Arial", 12), width=25,
                                      relief="solid", bd=2, bg="#ecf0f1", fg="#2c3e50")
        self.password_entry.grid(row=0, column=1, padx=10, pady=5)
        self.password_entry.focus_set()
        
        # Show password checkbox
        self.show_pass_var = tk.BooleanVar(value=False)
        show_pass_cb = tk.Checkbutton(password_frame, text="Show Password", 
                                     variable=self.show_pass_var,
                                     bg="#2c3e50", fg="#ecf0f1", selectcolor="#2c3e50",
                                     font=("Arial", 9), activebackground="#2c3e50",
                                     command=self.toggle_password_visibility)
        show_pass_cb.grid(row=1, column=1, sticky="w", padx=10, pady=(0, 10))
        
        # Attempts label
        self.attempts_label = tk.Label(password_frame, 
                                      text=f"Attempts remaining: {self.max_attempts}",
                                      font=("Arial", 9), bg="#2c3e50", fg="#bdc3c7")
        self.attempts_label.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        # Button frame
        button_frame = tk.Frame(self.main_frame, bg="#2c3e50")
        button_frame.pack(pady=20)
        
        # Launch button
        launch_btn = tk.Button(button_frame, text="🚀 Launch", 
                             command=self.check_password,
                             bg="#27ae60", fg="white",
                             font=("Arial", 14, "bold"),
                             relief="raised", bd=3,
                             width=15, height=2,
                             activebackground="#229954")
        launch_btn.pack(side=tk.LEFT, padx=10)
        
        # Exit button
        exit_btn = tk.Button(button_frame, text="✕ Exit", 
                            command=self.root.destroy,
                            bg="#e74c3c", fg="white",
                            font=("Arial", 12),
                            relief="raised", bd=2,
                            width=10, height=1,
                            activebackground="#c0392b")
        exit_btn.pack(side=tk.LEFT, padx=10)
        
        # Instructions frame
        instructions_frame = tk.Frame(self.main_frame, bg="#34495e", relief=tk.RIDGE, bd=2)
        instructions_frame.pack(pady=(20, 10), padx=20, fill=tk.X)
        
        instructions_title = tk.Label(instructions_frame, text="🔑 Available Passwords",
                                     font=("Arial", 11, "bold"), bg="#34495e", fg="#ecf0f1")
        instructions_title.pack(pady=(10, 5))
        
        instructions = """• JumboKing247@ - Launch Playinmatch Betting GUI
• admin123 - Launch GTA San Andreas Game
        
Note: Type exactly as shown above."""
        
        instr_label = tk.Label(instructions_frame, text=instructions,
                              font=("Arial", 10), bg="#34495e", fg="#bdc3c7",
                              justify="left", wraplength=400)
        instr_label.pack(pady=(0, 10), padx=10)
        
        # Footer
        footer_label = tk.Label(self.main_frame, 
                               text="Password protected system © 2024",
                               font=("Arial", 8), bg="#2c3e50", fg="#7f8c8d",
                               justify="center")
        footer_label.pack(side=tk.BOTTOM, pady=10)
        
        # Bind Enter key to login
        self.root.bind('<Return>', lambda e: self.check_password())
        # Bind Escape key to exit
        self.root.bind('<Escape>', lambda e: self.root.destroy())
    
    def toggle_password_visibility(self):
        """Toggle password visibility."""
        if self.show_pass_var.get():
            self.password_entry.config(show="")
        else:
            self.password_entry.config(show="*")
    
    def check_password(self):
        """Check if entered password is correct."""
        entered_password = self.password_var.get().strip()
        
        # Check password
        if entered_password in PASSWORDS:
            action = PASSWORDS[entered_password]
            
            if entered_password == "JumboKing247@":
                # Launch Playinmatch GUI
                self.root.destroy()
                self.launch_playinmatch_gui()
            elif entered_password == "admin123":
                # Launch GTA San Andreas
                self.launch_game(action)
        else:
            self.password_attempts += 1
            remaining = self.max_attempts - self.password_attempts
            
            if remaining > 0:
                self.attempts_label.config(
                    text=f"⚠️ Incorrect password! Attempts remaining: {remaining}",
                    fg="#e74c3c"  # Red color for error
                )
                # Shake animation for wrong password
                self.shake_window()
                self.password_entry.delete(0, tk.END)
                self.password_entry.focus_set()
            else:
                messagebox.showerror("Access Denied", 
                                   f"Maximum password attempts ({self.max_attempts}) exceeded!\nApplication will close.")
                self.root.destroy()
                sys.exit(1)
    
    def shake_window(self):
        """Shake window animation for wrong password."""
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        
        for i in range(5):
            for dx, dy in [(10, 0), (-10, 0), (10, 0), (-10, 0), (0, 0)]:
                self.root.geometry(f"+{x+dx}+{y+dy}")
                self.root.update()
                self.root.after(50)
    
    def launch_playinmatch_gui(self):
        """Launch the main Playinmatch GUI."""
        main_root = tk.Tk()
        main_app = MainApp(main_root)
        main_root.protocol("WM_DELETE_WINDOW", main_app.stop_loop)
        main_root.mainloop()
    
    def launch_game(self, game_path):
        """Launch the specified game."""
        try:
            if os.path.exists(game_path):
                # Show launching message
                launching_label = tk.Label(self.main_frame, 
                                          text="🎮 Launching GTA San Andreas...",
                                          font=("Arial", 14, "bold"), 
                                          bg="#2c3e50", fg="#2ecc71")
                launching_label.pack(pady=20)
                self.root.update()
                
                # Launch game
                subprocess.Popen(game_path, shell=True)
                
                # Close password window after short delay
                self.root.after(1000, self.root.destroy)
                sys.exit(0)
            else:
                messagebox.showerror("Game Not Found", 
                                   f"Cannot find game at:\n{game_path}\n\nPlease check the installation.")
                # Reset focus
                self.password_entry.focus_set()
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch game:\n{str(e)}")
            # Reset focus
            self.password_entry.focus_set()
    
    def clear_frame(self):
        """Clear all widgets from main frame."""
        for widget in self.main_frame.winfo_children():
            widget.destroy()

# ---------------- Worker (same logic as your script) ----------------
class UserWorker:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.sess: aiohttp.ClientSession | None = None
        self.csrf = None
        self.balance = None
        self.event_html = None
        self.market_ids: List[str] = []
        self.uid = None
        self.event_type = None
        self.funodds_data_cleaned = None

    async def create_session(self):
        # Agar session already bana hua hai aur closed nahi hai, reuse karo
        if self.sess is not None and not self.sess.closed:
            return
        self.sess = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20),
            connector=aiohttp.TCPConnector(ssl=False)
        )
        self.sess.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142 Safari/537.36"
            )
        })

    async def close(self):
        if self.sess:
            await self.sess.close()
            self.sess = None

    # STEP 1
    async def fetch_csrf(self):
        enqueue_log(f"[{self.email}] STEP: FETCH_CSRF")
        async with self.sess.get(f"{BASE_URL}/mobile") as r:
            html = await r.text()
        soup = BeautifulSoup(html, "html.parser")
        meta = soup.find("meta", {"name": "csrf-token"})
        if not meta:
            raise RuntimeError("CSRF not found")
        self.csrf = meta["content"]
        enqueue_log(f"[{self.email}] OK: CSRF fetched")

    # STEP 2
    async def login(self):
        enqueue_log(f"[{self.email}] STEP: LOGIN")
        headers = {
            "X-CSRF-TOKEN": self.csrf,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/mobile",
            "X-Requested-With": "XMLHttpRequest",
        }
        data = {"email": self.email, "password": self.password, "digits": ""}
        async with self.sess.post(f"{BASE_URL}/api2/v2/login", headers=headers, data=data) as r:
            text = await r.text()
        if "Login Success" not in text:
            raise RuntimeError("Login failed")
        enqueue_log(f"[{self.email}] OK: Login success")

    # STEP 3
    async def get_balance(self):
        enqueue_log(f"[{self.email}] STEP: GET_BALANCE")
        headers = {
            "X-CSRF-TOKEN": self.csrf,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/mobile",
            "X-Requested-With": "XMLHttpRequest",
        }
        async with self.sess.post(f"{BASE_URL}/api2/v2/getBalance", headers=headers) as r:
            if r.status != 200:
                text = await r.text()
                raise RuntimeError(f"getBalance failed ({r.status}) {text[:200]!r}")
            data = await r.json()
        self.balance = data.get("balance", {}).get("totalBalance", "N/A")
        enqueue_log(f"[{self.email}] OK: Balance {self.balance}")

    # STEP 3b — WALLET INFO (reuses existing session & csrf)
    async def get_wallet_info(self):
        """Fetch latest wallet transaction: amount, status, UTR, account holder name.
        Reuses the already-logged-in session — no re-login needed.
        Returns dict with keys: trans_amount, trans_status, utr, ac_holder
        """
        if self.sess is None or self.sess.closed:
            raise RuntimeError("Session not available (run Fetch Markets first)")
        if not self.csrf:
            raise RuntimeError("CSRF missing (run Fetch Markets first)")

        wallet_headers = {
            "X-CSRF-TOKEN": self.csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/mobile/walletHistory",
            "Accept": "*/*",
        }
        wallet_data = {"_token": self.csrf}

        # Fetch current month wallet history (adjust year/month if needed)
        import datetime
        now = datetime.datetime.now()
        month_name = now.strftime("%B")   # e.g. "February"
        year = now.year

        async with self.sess.post(
            f"{BASE_URL}/loadmore_wt?&page=1&year={year}&month={month_name}",
            headers=wallet_headers,
            data=wallet_data,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as r:
            if r.status != 200:
                raise RuntimeError(f"Wallet history failed ({r.status})")
            html = await r.text()

        # --- Parse HTML ---
        from bs4 import BeautifulSoup as _BS
        import re as _re
        soup = _BS(html, "html.parser")

        # Transaction amount
        trans_amount = "N/A"
        amt_el = soup.find("h4", class_="transAmount")
        if amt_el:
            amt_text = amt_el.get_text(strip=True)
            m = _re.search(r"([\d,]+)\s*INR", amt_text)
            if m:
                trans_amount = m.group(1) + " INR"

        # Transaction status
        trans_status = "N/A"
        st_el = soup.find("h5", class_="transStatus")
        if st_el:
            sp = st_el.find("span")
            if sp:
                trans_status = sp.get_text(strip=True)

        # UTR number
        utr = None
        all_h5 = soup.find_all("h5")
        for i, h5 in enumerate(all_h5):
            if "UTR" in h5.get_text():
                if i + 1 < len(all_h5):
                    utr_text = all_h5[i + 1].get_text(strip=True)
                    if utr_text and _re.match(r"^\d+$", utr_text):
                        utr = utr_text
                break

        # Account holder name — look for "Ac Holder Name :" label then sibling value
        ac_holder = None
        for h5 in all_h5:
            if "Ac Holder Name" in h5.get_text():
                # value is the next h5 sibling in the same row
                nxt = h5.find_next_sibling("h5")
                if not nxt:
                    # try parent row approach
                    parent = h5.parent
                    if parent:
                        siblings = parent.find_next_siblings()
                        for sib in siblings:
                            val = sib.find("h5")
                            if val:
                                nxt = val
                                break
                if nxt:
                    ac_holder = nxt.get_text(strip=True)
                break

        return {
            "trans_amount": trans_amount,
            "trans_status": trans_status,
            "utr": utr,
            "ac_holder": ac_holder,
        }

    # STEP 4
    async def load_event(self):
        enqueue_log(f"[{self.email}] STEP: LOAD_EVENT")
        headers = {"X-CSRF-TOKEN": self.csrf}
        async with self.sess.get(EVENT_URL, headers=headers) as r:
            if r.status != 200:
                raise RuntimeError(f"eventDetails failed ({r.status})")
            previous = ""
            for _ in range(10):
                html = await r.text()
                if len(html) == len(previous):
                    break
                previous = html
                await asyncio.sleep(0.3)
        self.event_html = previous
        if SHOW_DEBUG_HTML:
            save_debug(f"{self.email}_event_page", self.event_html)
        enqueue_log(f"[{self.email}] OK: Event loaded (len={len(self.event_html)})")

    # STEP 5
    async def parse_markets(self):
        enqueue_log(f"[{self.email}] STEP: PARSE_MARKETS")
        soup = BeautifulSoup(self.event_html, "html.parser")
        self.market_ids = []
        for div in soup.find_all("div", attrs={"data-marketid": True}):
            mid = div.get("data-marketid")
            if mid and mid not in self.market_ids:
                self.market_ids.append(mid)
        if not self.market_ids:
            raise RuntimeError("No market IDs found")
        m = re.search(r"uid\s*=\s*(\d+)", self.event_html)
        self.uid = m.group(1) if m else None
        if not self.uid:
            raise RuntimeError("uid not found")
        m2 = re.search(r"data-eventtype=['\"](\d+)['\"]", self.event_html)
        self.event_type = m2.group(1) if m2 else None
        if not self.event_type:
            raise RuntimeError("event_type not found")
        enqueue_log(f"[{self.email}] OK: Markets parsed → {', '.join(self.market_ids)}")

    # STEP 6 — CALL FUNODDS
    async def call_funodds(self):
        enqueue_log(f"[{self.email}] STEP: CALL_FUNODDS")
        market_str = ",".join(self.market_ids)
        url = (
            f"https://odds.funoddsin.com/api/v1/get/getMarketBook/"
            f"{EVENT_ID}?q={market_str}"
            f"&api_mode=1&eventType={self.event_type}&uid={self.uid}"
        )

        options_headers = {
            "Origin": BASE_URL,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-csrf-token,x-socket-id",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142 Safari/537.36"
            ),
        }

        async with self.sess.options(url, headers=options_headers) as r1:
            if r1.status != 204:
                raise RuntimeError(f"FUNODDS OPTIONS failed ({r1.status})")
        post_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142 Safari/537.36"
            ),
            "Origin": BASE_URL,
            "X-Csrf-Token": self.csrf or "",
            "X-Socket-Id": "72629.99793070",
            "Accept": "*/*",
        }

        async with self.sess.post(url, headers=post_headers, data="") as r2:
            if r2.status != 200:
                text = await r2.text()
                raise RuntimeError(f"FUNODDS POST failed ({r2.status}) → {text[:200]}")
            data = await r2.json()

        cleaned = []
        for market in data.get("odds", []):
            entry = {"marketId": market.get("marketId"), "runners": []}
            for r in market.get("runners", []):
                runner_info = {
                    "selectionId": r.get("selectionId"),
                    "handicap": r.get("handicap"),
                    "status": r.get("status"),
                    "lastPriceTraded": r.get("lastPriceTraded"),
                    "totalMatched": r.get("totalMatched"),
                }
                entry["runners"].append(runner_info)
            cleaned.append(entry)
        self.funodds_data_cleaned = cleaned
        enqueue_log(f"[{self.email}] OK: FUNODDS fetched and cleaned (markets: {len(cleaned)})")

    # NEW: AUTO-UPDATE DATA - Fetches limit and matched in parallel for minimum delay
    async def auto_update_payload(self, payload: dict) -> dict:
        """
        Auto-update payload with fresh limit, matched, and vol.
        Fetches limit and matched in parallel for minimum delay.
        Returns updated payload dictionary.
        """
        event_id = payload.get('eventId', '')
        event_type = payload.get('eventType', '')
        market_type = payload.get('market_type', '')
        
        if not event_id or not event_type or not market_type:
            enqueue_log(f"[{self.email}] ⚠️ Missing eventId/eventType/market_type in payload, skipping auto-update")
            return payload
        
        try:
            enqueue_log(f"[{self.email}] 🔄 Auto-updating payload data...")
            
            # Store old hash to check if it changed
            old_matched = payload.get('matched', '')
            
            # Fetch limit and matched in PARALLEL for minimum delay
            limit_task = self.fetch_limit(event_id, event_type)
            matched_task = self.fetch_matched_data(event_id, market_type, event_type)
            
            # Wait for both to complete simultaneously
            limit_value, matched_data = await asyncio.gather(limit_task, matched_task)
            
            matched_value = matched_data['matched']
            vol_value = matched_data['vol']
            
            # Check if hash changed
            if old_matched and old_matched != matched_value:
                enqueue_log(f"[{self.email}] 🔄 Hash UPDATED (changed from previous)")
            elif old_matched and old_matched == matched_value:
                enqueue_log(f"[{self.email}] ℹ️ Hash SAME (no change)")
            else:
                enqueue_log(f"[{self.email}] ✨ Hash FETCHED (first time)")
            
            # Update payload with fresh values
            payload['limit'] = limit_value
            payload['matched'] = matched_value
            payload['vol'] = vol_value
            
            enqueue_log(f"[{self.email}] ✅ Auto-update complete (limit, matched, vol updated)")
            
            return payload
            
        except Exception as e:
            enqueue_log(f"[{self.email}] ⚠️ Auto-update failed: {e}")
            enqueue_log(f"[{self.email}] ⚠️ Using existing payload values")
            return payload

    # NEW: FETCH LIMIT from eventDetails page
    async def fetch_limit(self, event_id: str, event_type: str) -> str:
        """Fetch limit value from eventDetails page JavaScript and also extract UID."""
        enqueue_log(f"[{self.email}] STEP: FETCH_LIMIT for eventId={event_id}")
        
        if self.sess is None or self.sess.closed:
            raise RuntimeError("Session not available (run Fetch Markets first)")
        
        url = f"{BASE_URL}/mobile/eventDetails/{event_id}?type={event_type}"
        headers = {"X-CSRF-TOKEN": self.csrf}
        
        async with self.sess.get(url, headers=headers) as r:
            if r.status != 200:
                raise RuntimeError(f"eventDetails failed ({r.status})")
            html = await r.text()
        
        # Parse JavaScript to find limit value
        # Looking for: $('#placeBet_').find('input[name=limit]').val("...")
        import re
        pattern = r"\$\('#placeBet_'\)\.find\('input\[name=limit\]'\)\.val\(['\"]([^'\"]+)['\"]\)"
        match = re.search(pattern, html)
        
        if not match:
            raise RuntimeError("Limit value not found in eventDetails page")
        
        limit_value = match.group(1)
        enqueue_log(f"[{self.email}] OK: Limit fetched (len={len(limit_value)})")
        
        # Also extract UID from the same page
        # Looking for: &uid=20404280 or uid\s*=\s*(\d+)
        uid_pattern = r"[&']uid['\s]*[=:]\s*['\"]?(\d+)['\"]?"
        uid_match = re.search(uid_pattern, html)
        
        if uid_match:
            new_uid = uid_match.group(1)
            if self.uid and self.uid != new_uid:
                enqueue_log(f"[{self.email}] ℹ️ UID changed: {self.uid} → {new_uid}")
            elif not self.uid:
                enqueue_log(f"[{self.email}] ✨ UID extracted = {new_uid}")
            # Always update UID to latest value
            self.uid = new_uid
        else:
            enqueue_log(f"[{self.email}] ⚠️ UID not found in eventDetails page")
        
        return limit_value

    # NEW: FETCH MATCHED (hash) and VOL (liquidity) from getMarketBook API
    async def fetch_matched_data(self, event_id: str, market_type: str, event_type: str) -> dict:
        """Fetch matched (hash) and vol (liquidity) from getMarketBook API."""
        enqueue_log(f"[{self.email}] STEP: FETCH_MATCHED for marketId={market_type}")
        
        if self.sess is None or self.sess.closed:
            raise RuntimeError("Session not available (run Fetch Markets first)")
        
        # If UID is not available, fetch it from eventDetails
        if not self.uid:
            enqueue_log(f"[{self.email}] ℹ️ UID not available yet, fetching from eventDetails...")
            url = f"{BASE_URL}/mobile/eventDetails/{event_id}?type={event_type}"
            headers = {"X-CSRF-TOKEN": self.csrf}
            async with self.sess.get(url, headers=headers) as r:
                if r.status != 200:
                    raise RuntimeError(f"Failed to fetch eventDetails for UID ({r.status})")
                html = await r.text()
            
            import re
            uid_pattern = r"[&']uid['\s]*[=:]\s*['\"]?(\d+)['\"]?"
            uid_match = re.search(uid_pattern, html)
            if uid_match:
                self.uid = uid_match.group(1)
                enqueue_log(f"[{self.email}] ✨ UID fetched = {self.uid}")
            else:
                raise RuntimeError("UID not found in eventDetails page")
        
        # Use market_type directly as the market ID (it's already the market ID from the payload)
        # The API can accept just the single market ID we need
        market_str = market_type
        
        url = (
            f"https://odds.funoddsin.com/api/v1/get/getMarketBook/"
            f"{event_id}?q={market_str}"
            f"&api_mode=1&eventType={event_type}&uid={self.uid}"
        )
        
        options_headers = {
            "Origin": BASE_URL,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-csrf-token,x-socket-id",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142 Safari/537.36"
            ),
        }
        
        async with self.sess.options(url, headers=options_headers) as r1:
            if r1.status != 204:
                raise RuntimeError(f"getMarketBook OPTIONS failed ({r1.status})")
        
        post_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142 Safari/537.36"
            ),
            "Origin": BASE_URL,
            "X-Csrf-Token": self.csrf or "",
            "X-Socket-Id": "72629.99793070",
            "Accept": "*/*",
        }
        
        async with self.sess.post(url, headers=post_headers, data="") as r2:
            if r2.status != 200:
                text = await r2.text()
                raise RuntimeError(f"getMarketBook POST failed ({r2.status}) → {text[:200]}")
            data = await r2.json()
        
        # Find the market matching market_type
        for market in data.get("odds", []):
            if market.get("marketId") == market_type:
                hash_value = market.get("hash")
                liquidity_value = market.get("liquidity")
                
                if hash_value and liquidity_value is not None:
                    enqueue_log(f"[{self.email}] OK: Matched (hash) fetched for marketId={market_type}")
                    enqueue_log(f"[{self.email}] OK: Vol (liquidity)={liquidity_value}")
                    return {
                        "matched": hash_value,
                        "vol": str(liquidity_value)
                    }
        
        raise RuntimeError(f"Market {market_type} not found in getMarketBook response")

    # NEW: PLACE_BET (no re-login here, uses existing session & csrf)
    async def place_bet(self, payload: dict, max_retries: int = 3):
        """Place bet with retry logic for INVALID PROFIT RATIO errors."""
        enqueue_log(f"[{self.email}] STEP: PLACE_BET")

        if self.sess is None or self.sess.closed:
            raise RuntimeError("Session not available (run Fetch Markets first)")

        if not self.csrf:
            raise RuntimeError("CSRF missing (run Fetch Markets first)")

        headers = {
            "X-CSRF-TOKEN": self.csrf,
            "X-Requested-With": "XMLHttpRequest",
            "X-Socket-Id": "72736.97132930",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": BASE_URL,
            "Referer": EVENT_URL,
        }

        # Retry logic for INVALID PROFIT RATIO
        for attempt in range(max_retries):
            async with self.sess.post(
                f"{BASE_URL}/api2/v2/placeBet",
                headers=headers,
                data=payload
            ) as r:
                text = await r.text()
                if r.status != 200:
                    raise RuntimeError(f"PLACE_BET FAILED ({r.status}) {text[:300]}")

            # Check if response contains "INVALID PROFIT RATIO"
            if "INVALID PROFIT RATIO" in text:
                if attempt < max_retries - 1:  # Not the last attempt
                    enqueue_log(f"[{self.email}] ⚠️ INVALID PROFIT RATIO - Retry {attempt + 1}/{max_retries - 1} in 2 seconds...")
                    await asyncio.sleep(2)  # Wait 2 seconds before retry
                    continue  # Retry
                else:
                    # Last attempt failed
                    enqueue_log(f"[{self.email}] ❌ INVALID PROFIT RATIO - All {max_retries} attempts failed")
                    enqueue_log(f"[{self.email}] BET RESPONSE: {text[:150]}")
                    return False  # Don't raise exception, just log and return
            else:
                # Success or other error - log and return
                enqueue_log(f"[{self.email}] BET RESPONSE: {text[:150]}")
                # Return True if bet was placed successfully
                if "Bet placed successfully" in text:
                    return True
                return False


    async def fetch_unmatched_bets(self) -> list:
        """Fetch bet history and return list of unmatched bet IDs."""
        enqueue_log(f"[{self.email}] STEP: FETCH_UNMATCHED_BETS")

        if self.sess is None or self.sess.closed:
            raise RuntimeError("Session not available (run Fetch Markets first)")

        headers = {
            "X-CSRF-TOKEN": self.csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "Origin": BASE_URL,
            "Referer": EVENT_URL,
        }

        async with self.sess.post(
            f"{BASE_URL}/api2/v2/getBetsHistory",
            headers=headers,
        ) as r:
            if r.status != 200:
                raise RuntimeError(f"getBetsHistory failed ({r.status})")
            resp = await r.json(content_type=None)

        bets = resp.get("data", [])
        # Unmatched bets: sizeMatched is "0.00" and order_status == 1
        unmatched_ids = []
        for bet in bets:
            size_matched = str(bet.get("sizeMatched", "0"))
            order_status = bet.get("order_status", 0)
            if size_matched == "0.00" and order_status == 1:
                unmatched_ids.append(bet["id"])

        enqueue_log(f"[{self.email}] OK: Found {len(unmatched_ids)} unmatched bet(s)")
        return unmatched_ids

    async def cancel_bet(self, bet_id: int):
        """Cancel a single unmatched bet by ID."""
        enqueue_log(f"[{self.email}] STEP: CANCEL_BET id={bet_id}")

        if self.sess is None or self.sess.closed:
            raise RuntimeError("Session not available (run Fetch Markets first)")

        headers = {
            "X-CSRF-TOKEN": self.csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": BASE_URL,
            "Referer": EVENT_URL,
        }

        data = f"id%5B0%5D={bet_id}"

        async with self.sess.post(
            f"{BASE_URL}/api2/v2/cancelAllBet",
            headers=headers,
            data=data,
        ) as r:
            text = await r.text()
            if r.status != 200:
                raise RuntimeError(f"cancelAllBet failed ({r.status}) {text[:300]}")

        enqueue_log(f"[{self.email}] OK: Cancel response for id={bet_id}: {text[:150]}")
        return text


# ---------------- Phase runner (synchronous style) ----------------
async def run_sync_phase(name, workers: List[UserWorker], method: str):
    enqueue_log(f"\n=== {name} ===")
    tasks = [getattr(w, method)() for w in workers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    ok = sum(1 for r in results if not isinstance(r, Exception))
    fail = len(results) - ok
    if fail == 0:
        enqueue_log(f"{name}: OK ({ok}/{len(workers)})")
    else:
        enqueue_log(f"{name}: {ok} OK, {fail} FAILED")
        for w, r in zip(workers, results):
            if isinstance(r, Exception):
                enqueue_log(f"[ERROR] {w.email}: {r}")
                break

# ---------------- High-level flows ----------------
async def fetch_markets_flow(workers: List[UserWorker]):
    # Create sessions (once) and KEEP them open for later FunOdds / PlaceBet
    await asyncio.gather(*(w.create_session() for w in workers))
    await run_sync_phase("FETCH_CSRF", workers, "fetch_csrf")
    await run_sync_phase("LOGIN", workers, "login")
    await run_sync_phase("GET_BALANCE", workers, "get_balance")
    await run_sync_phase("LOAD_EVENT", workers, "load_event")
    await run_sync_phase("PARSE_MARKETS", workers, "parse_markets")
    # NOTE: no close() here – sessions stay alive


async def call_funodds_flow(workers: List[UserWorker]):
    # Reuse existing sessions created in fetch_markets_flow
    await run_sync_phase("CALL_FUNODDS", workers, "call_funodds")


# ---------------- Main GUI ----------------
class MainApp:
    def __init__(self, root):
        self.root = root
        root.title("Playinmatch Betting GUI")
        root.geometry("1200x850")  # Increased height for Teams Loader tab

        # Define color scheme for payloads and buttons
        self.payload_colors = {
            1: "#ADD8E6",  # Light Blue for Payload 1 (Team1)
            2: "#FFB6C1",  # Light Pink for Payload 2 (Player2)
            3: "#87CEEB",  # Sky Blue for Payload 3 (Team2)
            4: "#FFC0CB",   # Pink for Payload 4 (Player4)
            5: "#E8F5E9",   # Light Green for Team Formatter
            6: "#FFFACD"    # Light Yellow for Teams Loader
        }
        
        # Text colors for better contrast
        self.payload_text_colors = {
            1: "#000000",  # Black text on blue
            2: "#000000",  # Black text on pink
            3: "#000000",  # Black text on blue
            4: "#000000",   # Black text on pink
            5: "#000000",   # Black text on green
            6: "#000000"    # Black text on yellow
        }
        
        # Green color for important buttons
        self.green_button_color = "#90EE90"  # Light Green
        
        # Store pending bet tasks
        self.pending_bet_tasks: List[asyncio.Task] = []
        self.betting_stopped = False
        self.current_bet_future = None  # Store the current bet future
        self.is_betting_active = False  # Flag to track if betting is in progress
        
        # Store team names extracted from payloads
        self.team_names = {
            1: "Team 1",  # Will be updated from payload
            3: "Team 3"   # Will be updated from payload
        }
        
        # NEW: Teams Loader variables
        self.team_entries = []  # List of dictionaries
        self.user_team_assignments = {}  # Map user index to team entries
        self.dynamic_teams_enabled = False

        # Main vertical PanedWindow for resizable sections
        self.main_paned = tk.PanedWindow(root, orient=tk.VERTICAL, sashwidth=5, sashrelief=tk.RAISED)
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        # Top frame for buttons and settings
        top_frm = tk.Frame(self.main_paned)
        self.main_paned.add(top_frm, height=120)

        # Row 1: Action buttons
        row1 = tk.Frame(top_frm)
        row1.pack(side=tk.TOP, fill=tk.X, pady=(2, 2))

        # Row 2: Settings, Update Data, User Mgmt
        row2 = tk.Frame(top_frm)
        row2.pack(side=tk.TOP, fill=tk.X, pady=(2, 2))

        # Left side: Action Buttons (row 1)
        action_frame = tk.Frame(row1)
        action_frame.pack(side=tk.LEFT, padx=(0, 20))
        
        # Main action buttons
        self.btn_fetch = tk.Button(action_frame, text="Fetch Markets", command=self.on_fetch_markets)
        self.btn_fetch.pack(side=tk.LEFT, padx=4)

        self.btn_check_balance = tk.Button(action_frame, text="\U0001f4b0 Check Balance",
                                           command=self.on_check_balance,
                                           bg="#9B59B6", fg="#FFFFFF",
                                           font=("Arial", 9, "bold"),
                                           relief=tk.RAISED, bd=2)
        self.btn_check_balance.pack(side=tk.LEFT, padx=4)

        self.btn_check_wallet = tk.Button(action_frame, text="📝 Check W",
                                          command=self.on_check_wallet,
                                          bg="#16A085", fg="#FFFFFF",
                                          font=("Arial", 9, "bold"),
                                          relief=tk.RAISED, bd=2)
        self.btn_check_wallet.pack(side=tk.LEFT, padx=4)

        self.btn_funodds = tk.Button(action_frame, text="Call FunOdds", command=self.on_call_funodds)
        self.btn_funodds.pack(side=tk.LEFT, padx=4)

        # Betting buttons with green color
        self.btn_placebet = tk.Button(action_frame, text="Place Bet", command=self.on_place_bet,
                                     bg=self.green_button_color, fg="#000000",
                                     font=("Arial", 9, "bold"),
                                     relief=tk.RAISED, bd=3)
        self.btn_placebet.pack(side=tk.LEFT, padx=4)

        self.btn_stop_betting = tk.Button(action_frame, text="Stop Betting", command=self.stop_betting,
                                         bg="#FF6B6B", fg="#FFFFFF",  # Red color for stop
                                         font=("Arial", 9, "bold"),
                                         relief=tk.RAISED, bd=3)
        self.btn_stop_betting.pack(side=tk.LEFT, padx=4)
        self.btn_stop_betting.config(state=tk.DISABLED)  # Initially disabled

        self.btn_cancel_unmatch = tk.Button(action_frame, text="Cancel All Unmatch",
                                            command=self.on_cancel_all_unmatch,
                                            bg="#E67E22", fg="#FFFFFF",
                                            font=("Arial", 9, "bold"),
                                            relief=tk.RAISED, bd=3)
        self.btn_cancel_unmatch.pack(side=tk.LEFT, padx=4)

        tk.Label(action_frame, text="Batch:", font=("Arial", 8)).pack(side=tk.LEFT, padx=(2, 0))
        self.cancel_batch_entry = tk.Entry(action_frame, width=3, font=("Arial", 9))
        self.cancel_batch_entry.pack(side=tk.LEFT, padx=(0, 4))
        self.cancel_batch_entry.insert(0, "10")

        # Middle: Bet Delay Settings (row 2)
        settings_frame = tk.Frame(row2)
        settings_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Bet Delay setting
        delay_label = tk.Label(settings_frame, text="Bet Delay (seconds):", font=("Arial", 9, "bold"))
        delay_label.pack(side=tk.LEFT, padx=(0, 5))
        
        # Validation function for bet delay entry
        def validate_delay_input(new_value):
            if new_value == "":
                return True
            try:
                value = int(new_value)
                if 0 <= value <= 300:  # Allow 0 to 300 seconds (5 minutes)
                    return True
                else:
                    return False
            except ValueError:
                return False
        
        vcmd = (root.register(validate_delay_input), '%P')
        
        self.bet_delay_entry = tk.Entry(settings_frame, width=6, validate="key", validatecommand=vcmd, 
                                       font=("Arial", 9))
        self.bet_delay_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.bet_delay_entry.insert(0, "6")  # Default value
        
        tk.Button(settings_frame, text="Set Delay", command=self.update_bet_delay, 
                 font=("Arial", 8)).pack(side=tk.LEFT)

        # NEW: One Time Trigger Checkbox
        self.one_time_trigger_var = tk.BooleanVar(value=False)
        one_time_check = tk.Checkbutton(settings_frame,
                                       text="⚡ One Time Trigger (No Delay)",
                                       variable=self.one_time_trigger_var,
                                       font=("Arial", 8, "bold"),
                                       bg="#34495e", fg="#FFD700",  # Gold color
                                       selectcolor="#34495e",
                                       activebackground="#34495e",
                                       command=self.toggle_one_time_trigger)
        one_time_check.pack(side=tk.LEFT, padx=(10, 0))

        # One Time Trigger Batch Size
        self.ott_batch_label = tk.Label(settings_frame, text="Batch:", font=("Arial", 8))
        self.ott_batch_label.pack(side=tk.LEFT, padx=(5, 0))
        self.ott_batch_entry = tk.Entry(settings_frame, width=4, font=("Arial", 9), state=tk.DISABLED, bg="#f0f0f0")
        self.ott_batch_entry.pack(side=tk.LEFT, padx=(0, 2))
        self.ott_batch_entry.insert(0, "10")
        self.ott_batch_set_btn = tk.Button(settings_frame, text="Set", font=("Arial", 8),
                                           state=tk.DISABLED, command=self.set_ott_batch)
        self.ott_batch_set_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Skip Update Checkbox - sends payload as-is without auto-updating data
        self.skip_update_var = tk.BooleanVar(value=False)
        self.skip_update_check = tk.Checkbutton(settings_frame,
                                       text="🔴 SKIP UPDATE (Raw Payload)",
                                       variable=self.skip_update_var,
                                       font=("Arial", 9, "bold"),
                                       bg="#FF0000", fg="#FFFFFF",
                                       selectcolor="#CC0000",
                                       activebackground="#CC0000",
                                       activeforeground="#FFFFFF",
                                       relief=tk.RAISED, bd=2,
                                       command=self.toggle_skip_update)
        self.skip_update_check.pack(side=tk.LEFT, padx=(10, 0))

        # Right: Update Data Frame (row 1, right side)
        update_data_frame = tk.Frame(row1)
        update_data_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(20, 10))
        
        # Update Data header
        tk.Label(update_data_frame, text="Update Data:", font=("Arial", 9, "bold")).pack(anchor="w")
        
        # Update Data Button (Orange color for visibility)
        self.btn_update_data = tk.Button(update_data_frame, text="🔄 Update Data", 
                                        command=self.on_update_data,
                                        bg="#FF9800", fg="#FFFFFF",
                                        font=("Arial", 9, "bold"),
                                        relief=tk.RAISED, bd=3,
                                        width=14)
        self.btn_update_data.pack(pady=(5, 5))
        
        # Status label for update data
        self.update_data_status = tk.Label(update_data_frame, text="Ready to update",
                                          font=("Arial", 8), fg="#666666")
        self.update_data_status.pack(anchor="w")
        
        # Info label
        info_label = tk.Label(update_data_frame, 
                             text="Fetches limit, matched\n& vol for selected user",
                             font=("Arial", 7), fg="#888888",
                             justify=tk.LEFT)
        info_label.pack(anchor="w", pady=(5, 0))

        # Right side: User Management buttons (row 2)
        user_mgmt_frame = tk.Frame(row2)
        user_mgmt_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add Load Users button (Green color)
        self.btn_load_users = tk.Button(user_mgmt_frame, text="📥 Load Users",
                                       command=self.load_users_dialog,
                                       bg="#4CAF50", fg="white",
                                       font=("Arial", 9, "bold"),
                                       relief=tk.RAISED, bd=3)
        self.btn_load_users.pack(side=tk.LEFT, padx=4)

        # Clear Logs button
        self.clear_btn = tk.Button(user_mgmt_frame, text="🗑️ Clear Logs",
                                  command=self.clear_logs,
                                  bg="#f44336", fg="white",
                                  font=("Arial", 9),
                                  relief=tk.RAISED, bd=2)
        self.clear_btn.pack(side=tk.LEFT, padx=4)

        # Save Logs button
        self.save_logs_btn = tk.Button(user_mgmt_frame, text="💾 Save Logs",
                                      command=self.save_logs,
                                      bg="#2196F3", fg="white",
                                      font=("Arial", 9),
                                      relief=tk.RAISED, bd=2)
        self.save_logs_btn.pack(side=tk.LEFT, padx=4)

        # Middle horizontal PanedWindow for user list and payload (resizable)
        middle_paned = tk.PanedWindow(self.main_paned, orient=tk.HORIZONTAL, sashwidth=5, sashrelief=tk.RAISED)
        self.main_paned.add(middle_paned, height=350)

        # Left panel: User selection (50% width)
        left_panel = tk.Frame(middle_paned, relief=tk.RIDGE, bd=1)
        
        tk.Label(left_panel, text="Select Users:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(5, 5), padx=5)
        
        # User list with scrollbar
        list_frame = tk.Frame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.user_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, yscrollcommand=scrollbar.set, 
                                       height=8, font=("Courier", 9))  # Reduced height
        self.user_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.user_listbox.yview)
        
        # Selection buttons
        btn_frame = tk.Frame(left_panel)
        btn_frame.pack(fill=tk.X, pady=(5, 5), padx=5)
        
        tk.Button(btn_frame, text="Select All", command=self.select_all_users, 
                 font=("Arial", 8)).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        tk.Button(btn_frame, text="Deselect All", command=self.deselect_all_users,
                 font=("Arial", 8)).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        # Add left panel to paned window
        middle_paned.add(left_panel)

        # Right panel: Payload selection and payloads (50% width)
        right_panel = tk.Frame(middle_paned, relief=tk.RIDGE, bd=1)
        
        # Payload selection frame
        payload_selection_frame = tk.Frame(right_panel)
        payload_selection_frame.pack(fill=tk.X, pady=(8, 5), padx=5)
        
        tk.Label(payload_selection_frame, text="Select Payload:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        self.payload_var = tk.IntVar(value=1)  # Default to Payload 1
        
        # Create a grid for payload buttons with colored backgrounds
        radio_grid = tk.Frame(payload_selection_frame)
        radio_grid.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Store payload names and button widgets
        self.payload_names = ["Team 1", "Player2", "Team 3", "Player4"]
        self.payload_buttons = []
        
        # Create 4 payload buttons with colored backgrounds
        for i in range(4):
            row = i // 2
            col = i % 2
            
            # Get color for this payload (1-indexed)
            bg_color = self.payload_colors[i+1]
            text_color = self.payload_text_colors[i+1]
            
            # Create button frame
            button_frame = tk.Frame(radio_grid)
            button_frame.grid(row=row, column=col, padx=5, pady=3, sticky="ew")
            button_frame.grid_columnconfigure(0, weight=1)
            
            # Custom colored radio button
            btn = tk.Radiobutton(button_frame, variable=self.payload_var, 
                               value=i+1, 
                               text=self.payload_names[i],
                               font=("Arial", 9, "bold"),
                               bg=bg_color, 
                               activebackground=bg_color,
                               selectcolor=bg_color,
                               fg=text_color,
                               indicatoron=0,  # Button style instead of radio button
                               width=12,
                               padx=10,
                               pady=3,
                               relief=tk.RAISED,
                               bd=2,
                               command=lambda idx=i: self.on_payload_button_click(idx))
            btn.pack(fill=tk.BOTH, expand=True)
            
            # Bind right-click for renaming
            btn.bind("<Button-3>", lambda e, idx=i: self.show_payload_rename_dialog(idx))
            
            # Store the button
            self.payload_buttons.append(btn)

        # Add Rename Payload Button
        tk.Button(payload_selection_frame, text="Rename Selected", 
                 command=self.rename_selected_payload,
                 font=("Arial", 8)).pack(side=tk.LEFT, padx=(10, 0))
        
        # Add Extract Teams Button
        tk.Button(payload_selection_frame, text="Extract Teams", 
                 command=self.extract_teams_from_payload,
                 font=("Arial", 8), bg="#FFD700").pack(side=tk.LEFT, padx=(5, 0))

        # Create notebook (tabbed interface) for payloads with custom style
        self.style = ttk.Style()
        
        # Configure custom styles for colored tabs
        for i in range(6):  # Now 6 tabs
            bg_color = self.payload_colors[i+1]
            text_color = self.payload_text_colors[i+1]
            
            # Create a custom style for each tab
            self.style.configure(f"CustomTab{i+1}.TNotebook.Tab", 
                                background=bg_color,
                                foreground=text_color,
                                font=("Arial", 9, "bold"))
        
        # Notebook frame
        notebook_frame = tk.Frame(right_panel)
        notebook_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        self.payload_notebook = ttk.Notebook(notebook_frame, height=220)
        self.payload_notebook.pack(fill=tk.BOTH, expand=True)

        # Create 4 payload tabs with colored backgrounds
        self.payload_frames = []
        self.bet_texts = []
        
        for i in range(4):
            # Get color for this payload (1-indexed)
            bg_color = self.payload_colors[i+1]
            text_color = self.payload_text_colors[i+1]
            
            # Create frame for each payload with colored background
            payload_frame = tk.Frame(self.payload_notebook, bg=bg_color)
            self.payload_frames.append(payload_frame)
            
            # Add tab with current payload name using custom style
            self.payload_notebook.add(payload_frame, text=self.payload_names[i])
            
            # Try to apply custom style to the tab
            try:
                self.payload_notebook.tab(i, style=f"CustomTab{i+1}.TNotebook.Tab")
            except:
                pass
            
            # Label for payload with matching background
            label = tk.Label(payload_frame, text="Payload Content (Paste raw body here):", 
                            font=("Arial", 9, "bold"), bg=bg_color, fg=text_color)
            label.pack(anchor="w", pady=(5, 5), padx=5)
            
            # Text area for payload with white background
            bet_text = ScrolledText(payload_frame, wrap=tk.WORD, font=("Courier", 9),
                                   bg="white", fg="black", 
                                   insertbackground="black",  # Cursor color
                                   relief="solid", bd=1,
                                   height=8)
            bet_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
            self.bet_texts.append(bet_text)
            
            # Bind text modification to auto-extract teams
            bet_text.bind("<KeyRelease>", lambda e, idx=i: self.auto_extract_teams(idx))

        # Create Team Formatter tab (5th tab)
        self.create_team_formatter_tab()
        
        # Create Teams Loader tab (6th tab)
        self.create_teams_loader_tab()

        # Add right panel to paned window
        middle_paned.add(right_panel)

        # Bind notebook tab change to update radio button
        self.payload_notebook.bind("<<NotebookTabChanged>>", self.on_payload_tab_changed)

        # Bottom frame for logs (resizable)
        bottom_frm = tk.Frame(self.main_paned, relief=tk.RIDGE, bd=2)
        self.main_paned.add(bottom_frm, height=200)

        # Log header
        log_header = tk.Frame(bottom_frm)
        log_header.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        tk.Label(log_header, text="Log Output:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        # Log area
        self.log = ScrolledText(bottom_frm, state='normal', wrap=tk.WORD, font=("Courier", 9), height=8)
        self.log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready - Click 'Load Users' to add users")
        status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Initialize users list
        self.users = []
        self.user_emails = []
        
        # Display initial instructions
        enqueue_log("[GUI] Welcome to Playinmatch Betting GUI")
        enqueue_log("[GUI] Click 'Load Users' button to add users")
        enqueue_log("[GUI] Format: phone_number,password (one per line)")
        enqueue_log("[GUI] Example:")
        enqueue_log("[GUI]   7722829265,Alam1234")
        enqueue_log("[GUI]   9933816642,Alam1234")
        enqueue_log("[GUI] Payload colors: Blue for Team1/Team3, Pink for Player2/Player4, Green/Yellow for Formatter/Loader")
        enqueue_log("[GUI] IMPORTANT: No default volume. You must:")
        enqueue_log("[GUI]   1. Paste payload with 'vol' parameter OR")
        enqueue_log("[GUI]   2. Extract volume from payload using 'Extract' button")
        enqueue_log("[GUI]   3. Configure volume settings using 'Set Volume' button")
        enqueue_log("[GUI] AUTO-UPDATE FEATURE: After betting, Start Volume will be updated with last user's volume")
        enqueue_log("[GUI] Enable 'Auto-continue increment' to automatically add increment to last volume")
        enqueue_log("[GUI] Auto-extract: Teams will be extracted automatically from 'teams' parameter")
        enqueue_log("[GUI] Team Formatter: Use 5th tab to format team names and generate payloads")
        enqueue_log("[GUI] Teams Loader: Use 6th tab to load team entries from CSV and enable dynamic assignment")
        enqueue_log("[GUI] NEW: One Time Trigger - Check the box for simultaneous betting (no delay)")
        enqueue_log("[GUI] NEW: Dynamic Teams Assignment - Load teams CSV and assign unique runnerName+teams to each user")
        enqueue_log("[GUI] Tip: Drag sash between panels to resize")
        enqueue_log("[GUI] Important: Use 'Stop Betting' button to cancel pending bets")
        
        self.workers_cache: List[UserWorker] | None = None

        # start background asyncio loop thread
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.start_loop, daemon=True)
        self.thread.start()

        # periodic log flush
        self.root.after(100, self.flush_logs)

    # ==================== TEAMS LOADER FUNCTIONS ====================
    def create_teams_loader_tab(self):
        """Create Teams Loader tab for dynamic team assignment."""
        # Create teams loader frame with light yellow background
        teams_frame = tk.Frame(self.payload_notebook, bg="#FFFACD", relief=tk.RAISED, bd=1)
        self.payload_frames.append(teams_frame)
        
        # Add tab as the 6th tab
        self.payload_notebook.add(teams_frame, text="Teams Loader")
        
        # Try to apply custom style
        try:
            self.payload_notebook.tab(5, style="CustomTab6.TNotebook.Tab")
        except:
            pass
        
        # Title
        title_label = tk.Label(teams_frame, text="Dynamic Teams & Runner Name Assignment", 
                              font=("Arial", 12, "bold"),
                              bg="#FFFACD", fg="#D35400")
        title_label.pack(pady=(10, 10))
        
        # Instructions
        instructions = ("Load team entries from CSV or paste directly.\n"
                       "Format: runnerName,teams (e.g., TeamA,TeamA+v+TeamB)\n"
                       "Each user gets 4 consecutive entries (one for each of the 4 payloads)")
        instr_label = tk.Label(teams_frame, text=instructions,
                              font=("Arial", 9), bg="#FFFACD", fg="#555555",
                              justify=tk.LEFT, wraplength=600)
        instr_label.pack(pady=(0, 15), padx=10)
        
        # Dynamic assignment checkbox
        dynamic_frame = tk.Frame(teams_frame, bg="#FFFACD")
        dynamic_frame.pack(pady=(0, 15), padx=20, fill=tk.X)
        
        self.dynamic_teams_var = tk.BooleanVar(value=False)
        self.dynamic_check = tk.Checkbutton(dynamic_frame, 
                                           text="Enable Dynamic Teams/Runner Assignment",
                                           variable=self.dynamic_teams_var,
                                           font=("Arial", 10, "bold"),
                                           bg="#FFFACD", fg="#D35400",
                                           selectcolor="#FFFACD",
                                           command=self.toggle_dynamic_teams)
        self.dynamic_check.pack(anchor=tk.W)
        
        # Info label about payload support
        info_frame = tk.Frame(teams_frame, bg="#FFFACD")
        info_frame.pack(pady=(5, 10), padx=20, fill=tk.X)
        
        info_label = tk.Label(info_frame,
                             text="ℹ️ When enabled, each user gets 4 CSV entries (one for each payload 1-4)",
                             font=("Arial", 9),
                             bg="#FFFACD", fg="#555555")
        info_label.pack(anchor=tk.W)
        
        # Keep the variable for backward compatibility but don't show the checkbox
        self.enable_all_payloads_var = tk.BooleanVar(value=True)  # Always enabled now
        
        # Input method selection
        method_frame = tk.Frame(teams_frame, bg="#FFFACD")
        method_frame.pack(pady=(5, 10), padx=20, fill=tk.X)
        
        self.input_method = tk.StringVar(value="paste")
        
        tk.Radiobutton(method_frame, text="Paste Entries", 
                      variable=self.input_method, value="paste",
                      bg="#FFFACD", command=self.show_paste_input).pack(side=tk.LEFT, padx=10)
        
        tk.Radiobutton(method_frame, text="Load CSV File", 
                      variable=self.input_method, value="csv",
                      bg="#FFFACD", command=self.show_csv_input).pack(side=tk.LEFT, padx=10)
        
        # NEW: Quick Load CSV Button (Added here for easy access)
        load_csv_btn = tk.Button(method_frame, text="📂 Quick Load CSV",
                               command=self.quick_load_csv,
                               bg="#3498DB", fg="white",
                               font=("Arial", 9, "bold"),
                               relief=tk.RAISED, bd=2)
        load_csv_btn.pack(side=tk.LEFT, padx=(20, 0))
        
        # Input area frame
        self.input_area_frame = tk.Frame(teams_frame, bg="#FFFACD")
        self.input_area_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Initially show paste input
        self.show_paste_input()
        
        # Status labels
        self.teams_status_var = tk.StringVar(value="No teams loaded")
        status_label = tk.Label(teams_frame, textvariable=self.teams_status_var,
                               font=("Arial", 9), bg="#FFFACD", fg="#2C3E50")
        status_label.pack(pady=(5, 10))
        
        # Buttons frame
        button_frame = tk.Frame(teams_frame, bg="#FFFACD")
        button_frame.pack(pady=(0, 10))
        
        # Load/Save buttons
        tk.Button(button_frame, text="Load & Parse Teams", 
                 command=self.load_and_parse_teams,
                 bg="#27AE60", fg="white",
                 font=("Arial", 10, "bold"),
                 relief=tk.RAISED, bd=2).pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="Save to CSV", 
                 command=self.save_teams_to_csv,
                 bg="#3498DB", fg="white",
                 font=("Arial", 10),
                 relief=tk.RAISED, bd=2).pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="Clear All", 
                 command=self.clear_teams_data,
                 bg="#E74C3C", fg="white",
                 font=("Arial", 10),
                 relief=tk.RAISED, bd=2).pack(side=tk.LEFT, padx=5)
        
        # NEW: Auto-assign teams button
        tk.Button(button_frame, text="Auto-Assign Teams", 
                 command=self.auto_assign_teams_to_users,
                 bg="#9B59B6", fg="white",
                 font=("Arial", 10),
                 relief=tk.RAISED, bd=2).pack(side=tk.LEFT, padx=5)
        
        # Preview frame
        preview_frame = tk.Frame(teams_frame, bg="#FFFACD")
        preview_frame.pack(pady=(10, 10), padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(preview_frame, text="Loaded Teams Preview:", 
                font=("Arial", 10, "bold"), bg="#FFFACD").pack(anchor=tk.W, pady=(0, 5))
        
        # Preview text with scrollbar
        preview_text_frame = tk.Frame(preview_frame, bg="#FFFACD")
        preview_text_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar_y = tk.Scrollbar(preview_text_frame)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        scrollbar_x = tk.Scrollbar(preview_text_frame, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.teams_preview_text = tk.Text(preview_text_frame, 
                                         height=8, width=80,
                                         font=("Consolas", 9),
                                         wrap=tk.NONE,
                                         bg="white", relief="solid", bd=1,
                                         yscrollcommand=scrollbar_y.set,
                                         xscrollcommand=scrollbar_x.set)
        self.teams_preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar_y.config(command=self.teams_preview_text.yview)
        scrollbar_x.config(command=self.teams_preview_text.xview)
        
        # NEW: CSV Format quick guide
        guide_frame = tk.Frame(teams_frame, bg="#FFFACD", relief=tk.RIDGE, bd=1)
        guide_frame.pack(pady=(5, 10), padx=20, fill=tk.X)
        
        guide_text = """CSV Format Examples:
1. Full entry: runnerName=New+Zealand&teams=India+v+New+Zealand&
2. Two columns: New+Zealand,India+v+New+Zealand
3. Three columns: New+Zealand,India,New+Zealand
(Spaces in names become +, teams separated by +v+)"""
        
        guide_label = tk.Label(guide_frame, text=guide_text,
                              font=("Arial", 8), bg="#FFFACD", fg="#555555",
                              justify=tk.LEFT, wraplength=580)
        guide_label.pack(pady=5, padx=5)

    def show_paste_input(self):
        """Show paste input area."""
        # Clear existing widgets
        for widget in self.input_area_frame.winfo_children():
            widget.destroy()
        
        tk.Label(self.input_area_frame, text="Paste team entries (one per line):",
                font=("Arial", 10, "bold"), bg="#FFFACD").pack(anchor=tk.W, pady=(0, 5))
        
        # Text area for pasting
        text_frame = tk.Frame(self.input_area_frame, bg="#FFFACD")
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.teams_input_text = tk.Text(text_frame, height=8, width=70,
                                       font=("Consolas", 9),
                                       bg="white", relief="solid", bd=1,
                                       yscrollcommand=scrollbar.set)
        self.teams_input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.teams_input_text.yview)
        
        # Add sample data button
        def add_sample_teams():
            sample = """runnerName=New+Zealand&teams=India+v+New+Zealand&
runnerName=India&teams=India+v+Australia&
runnerName=Australia&teams=Australia+v+England&
runnerName=Pakistan&teams=Pakistan+v+Sri+Lanka&
runnerName=England&teams=England+v+South+Africa&
runnerName=South+Africa&teams=South+Africa+v+New+Zealand&
runnerName=Sri+Lanka&teams=Sri+Lanka+v+Bangladesh&
runnerName=Afghanistan&teams=Afghanistan+v+Pakistan&
runnerName=West+Indies&teams=West+Indies+v+India&
runnerName=Bangladesh&teams=Bangladesh+v+Australia&
runnerName=New+Zealand&teams=New+Zealand+v+England&"""
            self.teams_input_text.delete(1.0, tk.END)
            self.teams_input_text.insert(1.0, sample)
        
        tk.Button(self.input_area_frame, text="Load Sample Format",
                 command=add_sample_teams,
                 font=("Arial", 9),
                 bg="#F39C12", fg="white").pack(pady=(5, 0))

    def show_csv_input(self):
        """Show CSV file input with format selection."""
        for widget in self.input_area_frame.winfo_children():
            widget.destroy()
        
        tk.Label(self.input_area_frame, text="Select CSV file:",
                font=("Arial", 10, "bold"), bg="#FFFACD").pack(anchor=tk.W, pady=(0, 5))
        
        # File selection frame
        file_frame = tk.Frame(self.input_area_frame, bg="#FFFACD")
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.csv_path_var = tk.StringVar()
        file_entry = tk.Entry(file_frame, textvariable=self.csv_path_var, 
                             width=50, font=("Arial", 9))
        file_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Browse button
        browse_btn = tk.Button(file_frame, text="Browse...", 
                              command=self.browse_csv_file,
                              font=("Arial", 9),
                              bg="#3498DB", fg="white")
        browse_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # NEW: Quick Load button (duplicate for convenience)
        quick_load_btn = tk.Button(file_frame, text="📂 Quick Load",
                                  command=self.quick_load_csv,
                                  font=("Arial", 9),
                                  bg="#2ECC71", fg="white")
        quick_load_btn.pack(side=tk.LEFT)
        
        # CSV format selection
        format_frame = tk.Frame(self.input_area_frame, bg="#FFFACD")
        format_frame.pack(fill=tk.X, pady=(10, 5))
        
        tk.Label(format_frame, text="CSV Format:", 
                font=("Arial", 9, "bold"), bg="#FFFACD").pack(side=tk.LEFT, padx=(0, 10))
        
        self.csv_format_var = tk.StringVar(value="two_col")  # Default to two column format
        
        # Format radio buttons
        formats = [
            ("Full Entry (runnerName=...&teams=...&)", "full"),
            ("Two Columns (runnerName, teams)", "two_col"),
            ("Three Columns (runnerName, teamA, teamB)", "three_col")
        ]
        
        for text, value in formats:
            tk.Radiobutton(format_frame, text=text,
                          variable=self.csv_format_var,
                          value=value,
                          bg="#FFFACD").pack(side=tk.LEFT, padx=10)
        
        # Delimiter selection
        delim_frame = tk.Frame(self.input_area_frame, bg="#FFFACD")
        delim_frame.pack(fill=tk.X, pady=(10, 5))
        
        tk.Label(delim_frame, text="Delimiter:", 
                font=("Arial", 9), bg="#FFFACD").pack(side=tk.LEFT, padx=(0, 10))
        
        self.csv_delimiter = tk.StringVar(value=",")
        delim_entry = tk.Entry(delim_frame, textvariable=self.csv_delimiter, 
                              width=5, font=("Arial", 9))
        delim_entry.pack(side=tk.LEFT)
        
        # Add example button
        example_frame = tk.Frame(self.input_area_frame, bg="#FFFACD")
        example_frame.pack(fill=tk.X, pady=(10, 0))
        
        def create_example_csv():
            """Create an example CSV file."""
            example_data = """runnerName=New+Zealand&teams=India+v+New+Zealand&
runnerName=India&teams=India+v+Australia&
runnerName=Australia&teams=Australia+v+England&
runnerName=Pakistan&teams=Pakistan+v+Sri+Lanka&
runnerName=England&teams=England+v+South+Africa&"""
            
            filename = filedialog.asksaveasfilename(
                title="Save Example CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(example_data)
                    messagebox.showinfo("Success", f"Example CSV saved to:\n{filename}")
                    enqueue_log(f"[Teams] Example CSV saved to {filename}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save: {e}")
        
        tk.Button(example_frame, text="Create Example CSV",
                 command=create_example_csv,
                 font=("Arial", 9),
                 bg="#F39C12", fg="white").pack(side=tk.LEFT)

    def quick_load_csv(self):
        """Quick load CSV file with default settings."""
        filename = filedialog.askopenfilename(
            title="Select CSV File with Team Entries",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if not filename:
            return  # User cancelled
        
        # Set CSV mode
        self.input_method.set("csv")
        self.show_csv_input()
        
        # Set the file path
        self.csv_path_var.set(filename)
        
        # Auto-detect CSV format
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                # Read first line to detect format
                first_line = f.readline().strip()
                
                enqueue_log(f"[Teams] 🔍 Auto-detecting format from first line: {first_line[:80]}...")
                
                if 'runnerName=' in first_line and 'teams=' in first_line:
                    # Format 1: Full entry (runnerName=X&teams=Y&)
                    self.csv_format_var.set("full")
                    enqueue_log(f"[Teams] Detected format: Full Entry")
                elif first_line.count(',') == 1:
                    # Format 2: Two columns - runnerName,teams
                    self.csv_format_var.set("two_col")
                    enqueue_log(f"[Teams] Detected format: Two Column")
                elif first_line.count(',') == 2:
                    # Format 3: Three columns - runnerName,teamA,teamB
                    self.csv_format_var.set("three_col")
                    enqueue_log(f"[Teams] Detected format: Three Column")
                else:
                    # Default to two_col (most common)
                    self.csv_format_var.set("two_col")
                    enqueue_log(f"[Teams] Could not detect format, defaulting to: Two Column")
                    
            # Auto-load and parse
            self.load_and_parse_teams()
            
        except Exception as e:
            enqueue_log(f"[Teams] ❌ Auto-detect error: {e}")
            messagebox.showerror("Error", f"Failed to detect CSV format: {e}")

    def browse_csv_file(self):
        """Browse for CSV file."""
        filename = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.csv_path_var.set(filename)
            enqueue_log(f"[Teams] Selected CSV file: {filename}")

    def parse_team_entry(self, line):
        """Parse a single team entry line."""
        line = line.strip()
        if not line:
            return None
        
        # Remove trailing '&' if present
        if line.endswith('&'):
            line = line[:-1]
        
        # Parse key-value pairs
        try:
            params = {}
            parts = line.split('&')
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    params[key.strip()] = value.strip()
            
            # Validate required fields
            if 'runnerName' not in params or 'teams' not in params:
                return None
            
            return params
        except Exception as e:
            enqueue_log(f"[Teams] Failed to parse line: {e}")
            return None

    def parse_csv_row(self, row):
        """Parse a CSV row based on selected format."""
        if not row or not any(row):
            return None
        
        try:
            csv_format = self.csv_format_var.get()
            
            if csv_format == "full":
                # Full entry format: "runnerName=...&teams=...&"
                entry = self.parse_team_entry(row[0])
                return entry
                
            elif csv_format == "two_col":
                # Two columns: runnerName, teams
                if len(row) >= 2:
                    runner_name = row[0].strip().replace(' ', '+')
                    teams = row[1].strip().replace(' ', '+')
                    return {
                        'runnerName': runner_name,
                        'teams': teams
                    }
                else:
                    enqueue_log(f"[Teams] Parse error: Expected 2 columns, got {len(row)} - {row}")
                    return None
                
            elif csv_format == "three_col":
                # Three columns: runnerName, teamA, teamB
                if len(row) >= 3:
                    runner_name = row[0].strip().replace(' ', '+')
                    team_a = row[1].strip().replace(' ', '+')
                    team_b = row[2].strip().replace(' ', '+')
                    return {
                        'runnerName': runner_name,
                        'teams': f"{team_a}+v+{team_b}"
                    }
                else:
                    enqueue_log(f"[Teams] Parse error: Expected 3 columns, got {len(row)} - {row}")
                    return None
            
            enqueue_log(f"[Teams] Unknown CSV format: {csv_format}")
            return None
            
        except Exception as e:
            enqueue_log(f"[Teams] ❌ Failed to parse CSV row: {e} - Row: {row}")
            return None

    def load_and_parse_teams(self):
        """Load and parse teams from input."""
        self.team_entries = []
        
        if self.input_method.get() == "paste":
            content = self.teams_input_text.get(1.0, tk.END).strip()
            if not content:
                messagebox.showwarning("Empty Input", "Please paste team entries first.")
                return
            
            enqueue_log(f"[Teams] 📝 Parsing pasted entries...")
            lines = content.split('\n')
            for i, line in enumerate(lines):
                entry = self.parse_team_entry(line)
                if entry:
                    self.team_entries.append(entry)
                    enqueue_log(f"[Teams]   ✓ Line {i+1} parsed successfully")
                else:
                    enqueue_log(f"[Teams]   ✗ Line {i+1} failed to parse: {line[:50]}...")
        
        else:  # CSV mode
            csv_path = self.csv_path_var.get()
            if not csv_path or not os.path.exists(csv_path):
                messagebox.showerror("File Error", "Please select a valid CSV file.")
                return
            
            try:
                delimiter = self.csv_delimiter.get()
                if not delimiter:
                    delimiter = ","
                
                csv_format = self.csv_format_var.get()
                enqueue_log(f"[Teams] 📂 Loading CSV: {os.path.basename(csv_path)}")
                enqueue_log(f"[Teams] Format: {csv_format}, Delimiter: '{delimiter}'")
                
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    row_num = 0
                    for row in reader:
                        row_num += 1
                        if not row or not any(row):  # Skip empty rows
                            enqueue_log(f"[Teams]   ⊘ Row {row_num}: Empty, skipping")
                            continue
                        
                        entry = self.parse_csv_row(row)
                        if entry:
                            self.team_entries.append(entry)
                            runner = entry['runnerName'].replace('+', ' ')
                            teams = entry['teams'].replace('+', ' ')
                            enqueue_log(f"[Teams]   ✓ Row {row_num}: {runner} | {teams}")
                        else:
                            enqueue_log(f"[Teams]   ✗ Row {row_num}: Failed to parse - {row}")
                            
            except Exception as e:
                enqueue_log(f"[Teams] ❌ CSV Error: {e}")
                messagebox.showerror("CSV Error", f"Failed to parse CSV: {e}")
                return
        
        # Update preview
        self.update_teams_preview()
        
        # Show success message
        count = len(self.team_entries)
        self.teams_status_var.set(f"Loaded {count} team entries")
        enqueue_log(f"[Teams] ✅ Successfully loaded {count} team entries")
        
        if count > 0:
            # Enable the dynamic checkbox
            self.dynamic_check.config(state=tk.NORMAL)
            
            # Auto-assign if dynamic mode is enabled
            if self.dynamic_teams_var.get():
                self.auto_assign_teams_to_users()
            
            # Show summary
            entries_per_user = 4
            max_users = count // entries_per_user
            summary = f"Successfully loaded {count} team entries\n"
            summary += f"This is enough for {max_users} users ({entries_per_user} entries each)"
            if count % entries_per_user != 0:
                summary += f"\n⚠️ Warning: Not divisible by {entries_per_user}. You have {count % entries_per_user} extra entries."
            messagebox.showinfo("Load Complete", summary)
        else:
            enqueue_log(f"[Teams] ⚠️ No entries were loaded. Check CSV format and content.")
            messagebox.showwarning("No Entries", "No valid entries were found in the file.\n\nPlease check:\n1. CSV format setting matches your file\n2. File is not empty\n3. Delimiter is correct")

    def update_teams_preview(self):
        """Update the teams preview text."""
        self.teams_preview_text.delete(1.0, tk.END)
        
        if not self.team_entries:
            self.teams_preview_text.insert(tk.END, "No teams loaded")
            return
        
        for i, entry in enumerate(self.team_entries):
            runner_name = entry['runnerName'].replace('+', ' ')
            teams = entry['teams'].replace('+', ' ')
            
            # Show which user and payload this belongs to
            user_num = (i // 4) + 1
            payload_num = (i % 4) + 1
            
            self.teams_preview_text.insert(tk.END, 
                f"Entry {i+1} [User {user_num}, Payload {payload_num}]: runnerName='{runner_name}', teams='{teams}'\n")
            
            # Add separator every 4 entries (one complete user)
            if (i + 1) % 4 == 0 and i < len(self.team_entries) - 1:
                self.teams_preview_text.insert(tk.END, "=" * 100 + "\n")

    def auto_assign_teams_to_users(self):
        """Auto-assign team entries to selected users - 4 entries per user."""
        selected_indices, selected_emails = self.get_selected_users()
        if not selected_emails:
            enqueue_log("[Teams] ❌ No users selected. Please select users to assign teams.")
            return
        
        num_users = len(selected_emails)
        num_entries = len(self.team_entries)
        
        # Each user needs 4 entries (one for each payload)
        entries_per_user = 4
        required_entries = num_users * entries_per_user
        
        if num_entries < required_entries:
            enqueue_log(f"[Teams] ❌ Not enough entries in CSV!")
            enqueue_log(f"[Teams] Required: {required_entries} entries ({num_users} users × 4 payloads)")
            enqueue_log(f"[Teams] Available: {num_entries} entries")
            enqueue_log(f"[Teams] Missing: {required_entries - num_entries} entries")
            self.teams_status_var.set(f"Need {required_entries} entries, but only {num_entries} available")
            return
        
        # Clear previous assignments
        self.user_team_assignments = {}
        
        enqueue_log(f"[Teams] 🎯 Auto-assigning teams to {num_users} users...")
        enqueue_log(f"[Teams] Each user gets 4 consecutive CSV entries (for 4 payloads)")
        enqueue_log("=" * 60)
        
        # Assign 4 consecutive entries to each user
        entry_idx = 0
        for user_idx, email in enumerate(selected_emails):
            if entry_idx + 3 < num_entries:  # Ensure we have 4 entries available
                # Assign 4 entries for this user
                self.user_team_assignments[user_idx] = [
                    self.team_entries[entry_idx],      # Payload 1
                    self.team_entries[entry_idx + 1],  # Payload 2
                    self.team_entries[entry_idx + 2],  # Payload 3
                    self.team_entries[entry_idx + 3]   # Payload 4
                ]
                
                # Log assignment with clear details
                enqueue_log(f"[Teams] 👤 User #{user_idx+1}: {email}")
                for payload_num in range(4):
                    entry = self.team_entries[entry_idx + payload_num]
                    runner_name = entry['runnerName'].replace('+', ' ')
                    teams = entry['teams'].replace('+', ' ')
                    enqueue_log(f"  Payload {payload_num+1}: runnerName='{runner_name}', teams='{teams}'")
                
                entry_idx += 4  # Move to next set of 4 entries
                enqueue_log("-" * 60)
        
        self.teams_status_var.set(f"✅ Assigned teams to {num_users} users (4 entries each)")
        enqueue_log(f"[Teams] ✅ Successfully assigned {num_users * 4} entries to {num_users} users")
        enqueue_log("=" * 60)

    def save_teams_to_csv(self):
        """Save loaded teams to CSV file."""
        if not self.team_entries:
            messagebox.showwarning("No Data", "No teams data to save.")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Save Teams Data",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for entry in self.team_entries:
                    # Save in full entry format
                    writer.writerow([f"runnerName={entry['runnerName']}&teams={entry['teams']}&"])
            
            enqueue_log(f"[Teams] Saved {len(self.team_entries)} entries to {filename}")
            messagebox.showinfo("Success", f"Saved {len(self.team_entries)} entries to {filename}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")

    def clear_teams_data(self):
        """Clear all teams data."""
        self.team_entries = []
        self.user_team_assignments = {}
        self.teams_preview_text.delete(1.0, tk.END)
        self.teams_status_var.set("No teams loaded")
        self.dynamic_teams_var.set(False)
        self.dynamic_teams_enabled = False
        enqueue_log("[Teams] Cleared all teams data")

    def toggle_dynamic_teams(self):
        """Toggle dynamic teams assignment."""
        if self.dynamic_teams_var.get():
            if not self.team_entries:
                enqueue_log("[Teams] Warning: No teams loaded. Please load teams first.")
                self.dynamic_teams_var.set(False)
                return
            
            # Auto-assign teams to users
            self.auto_assign_teams_to_users()
            
            enqueue_log("[Teams] Dynamic teams assignment ENABLED")
            enqueue_log("[Teams] Each user will get unique runnerName and teams")
            self.dynamic_teams_enabled = True
        else:
            enqueue_log("[Teams] Dynamic teams assignment DISABLED")
            self.teams_status_var.set("Dynamic assignment disabled")
            self.dynamic_teams_enabled = False

    def get_user_team_data(self, user_idx, payload_num):
        """Get team data for a specific user and payload number.
        Each user has 4 entries assigned (one for each of the 4 payloads).
        """
        if not self.dynamic_teams_enabled or user_idx not in self.user_team_assignments:
            return None
        
        user_entries = self.user_team_assignments.get(user_idx, [])
        
        # Each user should have 4 entries (for payloads 1, 2, 3, 4)
        if not user_entries or len(user_entries) < 4:
            enqueue_log(f"[Teams] ⚠️ User {user_idx} doesn't have enough entries ({len(user_entries)}/4)")
            return None
        
        # Map payload number (1-4) to entry index (0-3)
        entry_idx = payload_num - 1
        
        if entry_idx < 0 or entry_idx >= len(user_entries):
            return None
        
        # Return the appropriate entry for this payload
        return user_entries[entry_idx]

    def replace_team_data_in_payload(self, payload_dict, team_data):
        """Replace runnerName and teams in the payload dictionary."""
        if not team_data:
            return payload_dict
        
        # Create a copy of the payload dict
        modified_payload = payload_dict.copy()
        
        # Replace runnerName and teams
        modified_payload['runnerName'] = team_data['runnerName']
        modified_payload['teams'] = team_data['teams']
        
        return modified_payload

    def generate_payload_for_user(self, base_payload, user_idx, payload_num, volume_value):
        """Generate complete payload for a specific user."""
        # Start with base payload
        user_payload = base_payload.copy()
        
        # Replace volume
        user_payload['vol'] = volume_value
        
        # Get team data for this user (if dynamic teams enabled)
        team_data = self.get_user_team_data(user_idx, payload_num)
        if team_data:
            user_payload = self.replace_team_data_in_payload(user_payload, team_data)
            
            # Log the assignment with clear details
            selected_emails = [self.user_listbox.get(i) for i in self.user_listbox.curselection()]
            if user_idx < len(selected_emails):
                email = selected_emails[user_idx]
                runner_name = team_data['runnerName'].replace('+', ' ')
                teams = team_data['teams'].replace('+', ' ')
                enqueue_log(f"[{email}] 📍 Payload {payload_num} → runnerName='{runner_name}', teams='{teams}'")
        
        return user_payload

    def generate_payload_for_user_simple(self, base_payload, user_idx, payload_num):
        """Generate payload for a specific user (simplified - no volume modification)."""
        # Start with base payload
        user_payload = base_payload.copy()
        
        # Get team data for this user (if dynamic teams enabled)
        team_data = self.get_user_team_data(user_idx, payload_num)
        if team_data:
            user_payload = self.replace_team_data_in_payload(user_payload, team_data)
            
            # Log the assignment with clear details
            selected_emails = [self.user_listbox.get(i) for i in self.user_listbox.curselection()]
            if user_idx < len(selected_emails):
                email = selected_emails[user_idx]
                runner_name = team_data['runnerName'].replace('+', ' ')
                teams = team_data['teams'].replace('+', ' ')
                enqueue_log(f"[{email}] 📍 Payload {payload_num} → runnerName='{runner_name}', teams='{teams}'")
        
        return user_payload

    # ==================== EXISTING FUNCTIONS (UPDATED) ====================
    def toggle_one_time_trigger(self):
        """Handle one-time trigger toggle."""
        if self.one_time_trigger_var.get():
            # Disable the delay entry when one-time trigger is active
            self.bet_delay_entry.config(state=tk.DISABLED, bg="#f0f0f0")
            # Enable batch input
            self.ott_batch_entry.config(state=tk.NORMAL, bg="#ecf0f1")
            self.ott_batch_set_btn.config(state=tk.NORMAL)
            enqueue_log("[GUI] ⚡ One Time Trigger ENABLED - All bets will fire simultaneously")
            self.status_var.set("⚡ One Time Trigger: All bets will fire at once")
        else:
            # Re-enable the delay entry
            self.bet_delay_entry.config(state=tk.NORMAL, bg="#ecf0f1")
            # Disable batch input
            self.ott_batch_entry.config(state=tk.DISABLED, bg="#f0f0f0")
            self.ott_batch_set_btn.config(state=tk.DISABLED)
            enqueue_log("[GUI] One Time Trigger DISABLED - Using normal bet delay")
            self.status_var.set("Normal bet delay mode")

    def set_ott_batch(self):
        """Log the batch size setting."""
        try:
            val = int(self.ott_batch_entry.get())
            if val < 1:
                val = 1
                self.ott_batch_entry.delete(0, tk.END)
                self.ott_batch_entry.insert(0, "1")
            enqueue_log(f"[GUI] ⚡ One Time Trigger batch size set to {val}")
        except ValueError:
            self.ott_batch_entry.delete(0, tk.END)
            self.ott_batch_entry.insert(0, "10")
            enqueue_log("[GUI] Invalid batch size, reset to 10")

    def toggle_skip_update(self):
        """Handle skip update toggle."""
        if self.skip_update_var.get():
            enqueue_log("[GUI] 🔴 SKIP UPDATE ENABLED - Bets will use raw payload without auto-updating data")
            self.status_var.set("🔴 SKIP UPDATE: Payload will NOT be auto-updated")
        else:
            enqueue_log("[GUI] SKIP UPDATE DISABLED - Bets will auto-update payload data as usual")
            self.status_var.set("Normal mode: payload will be auto-updated")

    # ------------------ USER LOADING FUNCTIONS ------------------
    def load_users_dialog(self):
        """Show dialog to load users by pasting text."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Load Users")
        dialog.geometry("500x700")
        dialog.configure(bg="#7cb8fb")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        x = (screen_width - 500) // 2
        y = (screen_height - 700) // 2
        dialog.geometry(f"500x700+{x}+{y}")
        
        # Title
        title_label = tk.Label(dialog, text="📥 Load Users", 
                              font=("Arial", 16, "bold"), bg="#f0f0f0", fg="#333")
        title_label.pack(pady=(20, 10))
        
        # Instructions
        instructions = """📋 Paste user details:


Each line should contain phone_number,password separated by comma.
Empty lines will be ignored."""
        
        instr_label = tk.Label(dialog, text=instructions,
                              font=("Arial", 10), bg="#f0f0f0", fg="#555",
                              justify="left", wraplength=450)
        instr_label.pack(pady=(0, 15), padx=20)
        
        # Text area for user details with scrollbar
        text_frame = tk.Frame(dialog, bg="#f0f0f0")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15), padx=20)
        
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        users_text = tk.Text(text_frame, height=10, width=50,
                            font=("Consolas", 10),
                            wrap=tk.WORD, relief="solid", bd=2,
                            yscrollcommand=scrollbar.set)
        users_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=users_text.yview)
        
        # Add sample data button
        def add_sample_data():
            sample = """7722829265,Alam1234
9933816642,Alam1234
9840128394,Alam1234
9968071768,Alam1234"""
            users_text.delete(1.0, tk.END)
            users_text.insert(1.0, sample)
        
        sample_btn = tk.Button(dialog, text="Load Sample Format",
                              command=add_sample_data,
                              font=("Arial", 9),
                              bg="#2196F3", fg="white",
                              relief="raised", bd=2)
        sample_btn.pack(pady=(0, 10))
        
        # Button frame
        button_frame = tk.Frame(dialog, bg="#f0f0f0")
        button_frame.pack(pady=(0, 20))
        
        # Load button
        def load_users():
            content = users_text.get(1.0, tk.END).strip()
            if not content:
                messagebox.showwarning("Empty Content", "Please enter user details before loading.")
                return
            
            # Parse and validate the content
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            valid_users = []
            errors = []
            
            for i, line in enumerate(lines, 1):
                parts = line.split(',')
                if len(parts) >= 2:
                    phone = parts[0].strip()
                    password = parts[1].strip()
                    if phone and password:
                        valid_users.append((phone, password))
                    else:
                        errors.append(f"Line {i}: Missing phone or password")
                else:
                    errors.append(f"Line {i}: Invalid format (should be phone,password)")
            
            if not valid_users:
                messagebox.showerror("No Valid Users", "No valid user entries found. Please check your format.")
                return
            
            # Clear existing users
            self.users.clear()
            self.user_emails.clear()
            self.user_listbox.delete(0, tk.END)
            
            # Add new users
            for phone, password in valid_users:
                self.users.append((phone, password))
                self.user_emails.append(phone)
                self.user_listbox.insert(tk.END, phone)
            
            # Select all users by default
            self.select_all_users()
            
            # Show success message
            summary = f"Loaded {len(valid_users)} user(s)"
            if errors:
                summary += f" with {len(errors)} error(s)"
                messagebox.showwarning("Load Complete with Errors", 
                                     f"{summary}\n\nSome entries were skipped due to format errors.")
            else:
                messagebox.showinfo("Load Complete", f"Successfully loaded {len(valid_users)} users!")
            
            # Log the action
            enqueue_log(f"[GUI] Loaded {len(valid_users)} users")
            for i, (phone, _) in enumerate(valid_users[:5], 1):
                enqueue_log(f"[GUI]   User {i}: {phone}")
            if len(valid_users) > 5:
                enqueue_log(f"[GUI]   ... and {len(valid_users)-5} more users")
            
            self.status_var.set(f"Loaded {len(valid_users)} users")
            dialog.destroy()
        
        load_btn = tk.Button(button_frame, text="💾 Load Users",
                            command=load_users,
                            bg="#4CAF50", fg="white",
                            font=("Arial", 12, "bold"),
                            relief="raised", bd=3,
                            width=15, height=2)
        load_btn.pack(side=tk.LEFT, padx=10)
        
        # Cancel button
        cancel_btn = tk.Button(button_frame, text="✕ Cancel",
                              command=dialog.destroy,
                              bg="#9E9E9E", fg="white",
                              font=("Arial", 10),
                              relief="raised", bd=2,
                              width=10)
        cancel_btn.pack(side=tk.LEFT, padx=10)
        
        # Focus on text area
        users_text.focus_set()
        
        # Bind Ctrl+Enter to load users
        dialog.bind('<Control-Return>', lambda e: load_users())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

    # ------------------ STOP BETTING FIXED ------------------
    def stop_betting(self):
        """Stop all pending bet tasks and reset everything for next bet."""
        if not self.pending_bet_tasks and not self.is_betting_active:
            enqueue_log("[GUI] No pending bets to stop")
            self.status_var.set("No pending bets to stop")
            return
        
        enqueue_log(f"[GUI] Stopping betting process...")
        self.betting_stopped = True
        
        # Set betting active flag to False
        self.is_betting_active = False
        
        # Cancel all pending tasks
        cancelled_count = 0
        for task in self.pending_bet_tasks:
            if not task.done():
                task.cancel()
                cancelled_count += 1
                enqueue_log(f"[GUI] Cancelled pending bet task")
        
        # Clear the pending tasks list
        self.pending_bet_tasks.clear()
        
        # Cancel the main bet future if it exists
        if self.current_bet_future and not self.current_bet_future.done():
            self.current_bet_future.cancel()
            enqueue_log("[GUI] Cancelled main bet future")
            self.current_bet_future = None
        
        # Reset UI state
        self.btn_stop_betting.config(state=tk.DISABLED)
        self.btn_placebet.config(state=tk.NORMAL)
        
        # Reset betting stopped flag immediately so we're ready for next bet
        self.betting_stopped = False
        
        enqueue_log(f"[GUI] Betting stopped - {cancelled_count} bets cancelled")
        enqueue_log(f"[GUI] Ready for new bets - Click 'Place Bet' to start new betting")
        self.status_var.set(f"Betting stopped - Ready for new bets")

    def on_cancel_all_unmatch(self):
        """Cancel all unmatched bets for all selected users."""
        if not self.workers_cache:
            enqueue_log("[GUI] ERROR: Click 'Fetch Markets' first (to login & get CSRF).")
            self.update_status("Error: Run Fetch Markets first")
            return

        _, selected_emails = self.get_selected_users()
        if not selected_emails:
            enqueue_log("[GUI] ERROR: No users selected. Please select at least one user.")
            self.update_status("Error: No users selected")
            return

        # Confirmation popup
        confirm = messagebox.askyesno(
            "Cancel All Unmatched Bets",
            f"Are you sure you want to cancel all unmatched bets for {len(selected_emails)} selected user(s)?",
            icon="warning"
        )
        if not confirm:
            enqueue_log("[GUI] Cancel All Unmatch aborted by user.")
            return

        selected_workers = [w for w in self.workers_cache if w.email in selected_emails]
        if not selected_workers:
            enqueue_log("[GUI] ERROR: No workers found for selected users.")
            return

        # Get batch size
        try:
            batch_size = int(self.cancel_batch_entry.get())
            if batch_size < 1:
                batch_size = 10
        except ValueError:
            batch_size = 10

        self.btn_cancel_unmatch.config(state=tk.DISABLED)
        enqueue_log(f"[GUI] Starting Cancel All Unmatch for {len(selected_workers)} user(s) (batch={batch_size})...")

        async def cancel_unmatch_flow():
            try:
                # Step 1: Fetch unmatched bet IDs for ALL users in parallel (batched)
                enqueue_log("[GUI] Fetching unmatched bets for all users...")
                user_bets = {}  # worker -> list of bet IDs

                for i in range(0, len(selected_workers), batch_size):
                    batch = selected_workers[i:i+batch_size]
                    tasks = [w.fetch_unmatched_bets() for w in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for w, result in zip(batch, results):
                        if isinstance(result, Exception):
                            enqueue_log(f"[{w.email}] ❌ Failed to fetch bets: {result}")
                        elif result:
                            user_bets[w] = result
                        else:
                            enqueue_log(f"[{w.email}] No unmatched bets found — skipping.")

                if not user_bets:
                    enqueue_log("[GUI] No unmatched bets found for any user.")
                    self.status_var.set("No unmatched bets to cancel")
                    return

                # Find max number of unmatched bets across all users
                max_bets = max(len(ids) for ids in user_bets.values())
                total_bets = sum(len(ids) for ids in user_bets.values())
                enqueue_log(f"[GUI] Found {total_bets} total unmatched bets across {len(user_bets)} users (max {max_bets} per user)")

                # Step 2: Cancel round by round — all users cancel bet #0 together, then bet #1, etc.
                for round_idx in range(max_bets):
                    # Collect (worker, bet_id) pairs for this round
                    round_pairs = []
                    for w, ids in user_bets.items():
                        if round_idx < len(ids):
                            round_pairs.append((w, ids[round_idx]))

                    enqueue_log(f"[GUI] Round {round_idx+1}/{max_bets}: Cancelling {len(round_pairs)} bet(s)...")

                    # Fire cancellations in batches
                    for i in range(0, len(round_pairs), batch_size):
                        batch_pairs = round_pairs[i:i+batch_size]
                        tasks = [w.cancel_bet(bet_id) for w, bet_id in batch_pairs]
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for (w, bet_id), result in zip(batch_pairs, results):
                            if isinstance(result, Exception):
                                enqueue_log(f"[{w.email}] ❌ Failed to cancel bet id={bet_id}: {result}")

                    # 1 second delay between rounds (except after last)
                    if round_idx < max_bets - 1:
                        await asyncio.sleep(1)

                enqueue_log("[GUI] ✅ Cancel All Unmatch completed for all users.")
                self.status_var.set("Cancel All Unmatch completed")
            finally:
                self.btn_cancel_unmatch.config(state=tk.NORMAL)

        asyncio.run_coroutine_threadsafe(cancel_unmatch_flow(), self.loop)

    def create_team_formatter_tab(self):
        """Create team formatter tab as the 5th tab in payload notebook"""
        # Create formatter frame with light green background
        formatter_frame = tk.Frame(self.payload_notebook, bg="#E8F5E9", relief=tk.RAISED, bd=1)
        self.payload_frames.append(formatter_frame)
        
        # Add tab with custom style
        self.payload_notebook.add(formatter_frame, text="Team Formatter")
        
        # Try to apply custom style to the tab
        try:
            self.payload_notebook.tab(4, style="CustomTab5.TNotebook.Tab")
        except:
            pass
        
        # Formatter title
        title_label = tk.Label(formatter_frame, text="Team Name Formatter", 
                              font=("Arial", 11, "bold"),
                              bg="#E8F5E9", fg="#2E7D32")
        title_label.pack(pady=(10, 15))
        
        # Instructions
        instructions = ("Enter team names to generate a formatted betting payload.\n"
                       "Spaces will be replaced with + for URL encoding.")
        instr_label = tk.Label(formatter_frame, text=instructions,
                              font=("Arial", 8), bg="#E8F5E9", fg="#555555",
                              justify=tk.LEFT, wraplength=500)
        instr_label.pack(pady=(0, 15), padx=10)
        
        # Team input frame
        input_frame = tk.Frame(formatter_frame, bg="#E8F5E9")
        input_frame.pack(pady=(0, 15), padx=20, fill=tk.X)
        
        # Team A
        tk.Label(input_frame, text="Team A:", 
                font=("Arial", 9, "bold"), bg="#E8F5E9").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.team_a_entry = tk.Entry(input_frame, width=30, font=("Arial", 9))
        self.team_a_entry.grid(row=0, column=1, padx=(10, 0), pady=5, sticky=tk.W)
        self.team_a_entry.insert(0, "Northern Brave")
        
        # Team B
        tk.Label(input_frame, text="Team B:", 
                font=("Arial", 9, "bold"), bg="#E8F5E9").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.team_b_entry = tk.Entry(input_frame, width=30, font=("Arial", 9))
        self.team_b_entry.grid(row=1, column=1, padx=(10, 0), pady=5, sticky=tk.W)
        self.team_b_entry.insert(0, "Wellington Firebirds")
        
        # Button frame
        button_frame = tk.Frame(formatter_frame, bg="#E8F5E9")
        button_frame.pack(pady=(10, 15))
        
        # Format button (green)
        self.format_teams_btn = tk.Button(button_frame, text="Format Team Names", 
                                         command=self.format_teams_gui,
                                         bg="#90EE90", fg="#000000",
                                         font=("Arial", 9, "bold"),
                                         relief=tk.RAISED, bd=2)
        self.format_teams_btn.pack(side=tk.LEFT, padx=5)
        
        # Insert buttons frame
        insert_frame = tk.Frame(formatter_frame, bg="#E8F5E9")
        insert_frame.pack(pady=(5, 10))
        
        # Insert buttons for each payload
        for i in range(4):
            bg_color = self.payload_colors[i+1]
            text_color = self.payload_text_colors[i+1]
            payload_name = self.payload_names[i]
            
            insert_btn = tk.Button(insert_frame, text=f"Insert into {payload_name}",
                                  command=lambda idx=i: self.insert_formatted_into_payload(idx),
                                  bg=bg_color, fg=text_color,
                                  font=("Arial", 8, "bold"),
                                  relief=tk.RAISED, bd=1)
            insert_btn.pack(side=tk.LEFT, padx=2)
        
        # Result display
        result_label = tk.Label(formatter_frame, text="Formatted Result:", 
                               font=("Arial", 9, "bold"), bg="#E8F5E9")
        result_label.pack(pady=(10, 5))
        
        # Result text area with scrollbar
        text_frame = tk.Frame(formatter_frame, bg="#E8F5E9")
        text_frame.pack(pady=(0, 10), padx=20, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.formatted_result_text = tk.Text(text_frame, height=4, width=60,
                                             font=("Consolas", 9), wrap=tk.WORD,
                                             bg="white", relief="solid", bd=1,
                                             yscrollcommand=scrollbar.set)
        self.formatted_result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.formatted_result_text.yview)
        
        # Copy button
        self.copy_formatted_btn = tk.Button(formatter_frame, text="Copy Formatted Result",
                                           command=self.copy_formatted_result_gui,
                                           state=tk.DISABLED,
                                           bg="#ADD8E6", fg="#000000",
                                           font=("Arial", 9),
                                           relief=tk.RAISED, bd=2)
        self.copy_formatted_btn.pack(pady=(0, 10))

    def format_teams_gui(self):
        """Format team names according to the specified pattern"""
        team_a = self.team_a_entry.get().strip()
        team_b = self.team_b_entry.get().strip()
        
        # Check if both teams are entered
        if not team_a or not team_b:
            messagebox.showwarning("Missing Teams", "Please enter both team names.")
            return
        
        # Replace spaces with + in team names
        team_a_formatted = team_a.replace(" ", "+")
        team_b_formatted = team_b.replace(" ", "+")
        
        # Create the full formatted string
        formatted_string = f"2nd+Innings+20+Overs+Line&runnerName=Total+Runs&teams={team_a_formatted}+v+{team_b_formatted}&stake=3400&betting_type=Under&odds=1.01"
        
        # Display the result
        self.formatted_result_text.delete(1.0, tk.END)
        self.formatted_result_text.insert(1.0, formatted_string)
        
        # Store the formatted string for later use
        self.current_formatted_string = formatted_string
        
        # Enable the copy button
        self.copy_formatted_btn.config(state=tk.NORMAL)
        
        # Update team names in payload buttons if applicable
        self.update_team_names_from_formatter(team_a, team_b)
        
        # Log the action
        enqueue_log(f"[Formatter] Teams formatted: {team_a} vs {team_b}")
        self.status_var.set(f"Teams formatted: {team_a} vs {team_b}")

    def copy_formatted_result_gui(self):
        """Copy the formatted string to clipboard"""
        formatted_text = self.formatted_result_text.get(1.0, tk.END).strip()
        
        if formatted_text:
            self.root.clipboard_clear()
            self.root.clipboard.append(formatted_text)
            self.copy_formatted_btn.config(text="✓ Copied!", bg="#90EE90")
            enqueue_log("[Formatter] Formatted string copied to clipboard")
            
            # Reset button after 2 seconds
            self.root.after(2000, lambda: self.copy_formatted_btn.config(
                text="Copy Formatted Result", bg="#ADD8E6"))

    def insert_formatted_into_payload(self, payload_idx):
        """Insert the formatted string into a specific payload tab"""
        if not hasattr(self, 'current_formatted_string') or not self.current_formatted_string:
            messagebox.showwarning("No Formatted String", 
                                  "Please format teams first before inserting.")
            return
        
        # Clear the target payload text area
        self.bet_texts[payload_idx].delete(1.0, tk.END)
        
        # Insert the formatted string
        self.bet_texts[payload_idx].insert(1.0, self.current_formatted_string)
        
        # Switch to that payload tab
        self.payload_notebook.select(payload_idx)
        self.payload_var.set(payload_idx + 1)
        
        # Auto-extract teams from the inserted payload
        self.auto_extract_teams(payload_idx)
        
        # Log the action
        payload_name = self.payload_names[payload_idx]
        enqueue_log(f"[Formatter] Inserted into {payload_name}")
        self.status_var.set(f"Formatted payload inserted into {payload_name}")

    def update_team_names_from_formatter(self, team_a, team_b):
        """Update payload names with formatted team names"""
        # Update Team 1 (Payload 1) if it matches the default or is empty
        if self.payload_names[0] in ["Team 1", "Team 1", "Northern Brave"]:
            self.update_payload_name(0, team_a)
        
        # Update Team 3 (Payload 3) if it matches the default or is empty
        if self.payload_names[2] in ["Team 3", "Team 3", "Wellington Firebirds"]:
            self.update_payload_name(2, team_b)

    def auto_extract_teams(self, payload_idx):
        """Automatically extract team names when payload is pasted/changed."""
        raw = self.bet_texts[payload_idx].get("1.0", tk.END).strip()
        if not raw:
            return
        
        # Only extract for Player 1 (index 0) and Player 3 (index 2)
        if payload_idx in [0, 2]:
            try:
                payload = parse_urlencoded_body(raw)
                if 'teams' in payload:
                    teams_str = unquote_plus(payload['teams'])
                    # Split by " v " or " v " or "+v+"
                    if ' v ' in teams_str:
                        teams = teams_str.split(' v ')
                    elif ' v ' in teams_str:
                        teams = teams_str.split(' v ')
                    elif '+v+' in teams_str:
                        teams = teams_str.split('+v+')
                    else:
                        return
                    
                    if len(teams) >= 2:
                        team1 = teams[0].strip()
                        team2 = teams[1].strip()
                        
                        # Store team names
                        if payload_idx == 0:  # Player 1
                            self.team_names[1] = team1
                            self.update_payload_name(0, team1)
                            enqueue_log(f"[GUI] Auto-extracted Team 1: {team1}")
                        elif payload_idx == 2:  # Player 3
                            self.team_names[3] = team2
                            self.update_payload_name(2, team2)
                            enqueue_log(f"[GUI] Auto-extracted Team 3: {team2}")
                        
                        self.status_var.set(f"Teams extracted: {team1} vs {team2}")
                        
            except Exception as e:
                # Silent fail for auto-extract
                pass

    def extract_teams_from_payload(self):
        """Extract team names from the currently selected payload."""
        payload_idx = self.payload_var.get() - 1
        
        if payload_idx not in [0, 2]:
            messagebox.showinfo("Extract Teams", "This feature works only for Team 1 (Payload 1) and Team 3 (Payload 3)")
            return
        
        raw = self.bet_texts[payload_idx].get("1.0", tk.END).strip()
        if not raw:
            enqueue_log(f"[GUI] No payload in Payload {payload_idx + 1} to extract teams from.")
            return
        
        try:
            payload = parse_urlencoded_body(raw)
            if 'teams' in payload:
                teams_str = unquote_plus(payload['teams'])
                # Split by " v " or " v " or "+v+"
                if ' v ' in teams_str:
                    teams = teams_str.split(' v ')
                elif ' v ' in teams_str:
                    teams = teams_str.split(' v ')
                elif '+v+' in teams_str:
                    teams = teams_str.split('+v+')
                else:
                    enqueue_log(f"[GUI] Could not parse teams format in Payload {payload_idx + 1}")
                    return
                
                if len(teams) >= 2:
                    team1 = teams[0].strip()
                    team2 = teams[1].strip()
                    
                    # Update appropriate team name
                    if payload_idx == 0:  # Player 1
                        self.team_names[1] = team1
                        self.update_payload_name(0, team1)
                        enqueue_log(f"[GUI] Extracted Team 1: {team1}")
                    elif payload_idx == 2:  # Player 3
                        self.team_names[3] = team2
                        self.update_payload_name(2, team2)
                        enqueue_log(f"[GUI] Extracted Team 3: {team2}")
                    
                    # Also update the other payload if both teams found
                    if payload_idx == 0 and team2:
                        self.team_names[3] = team2
                        # Don't auto-rename the other payload as it might have different content
                    
                    self.status_var.set(f"Teams extracted: {team1} vs {team2}")
                    
            else:
                enqueue_log(f"[GUI] No 'teams' parameter found in Payload {payload_idx + 1}")
                self.status_var.set(f"No teams parameter in Payload {payload_idx + 1}")
                
        except Exception as e:
            enqueue_log(f"[GUI] Failed to extract teams: {e}")
            self.status_var.set("Failed to extract teams")

    def on_payload_button_click(self, idx):
        """Handle payload button click to update notebook."""
        self.payload_notebook.select(idx)
        self.on_payload_tab_changed(None)

    def show_payload_rename_dialog(self, idx):
        """Show rename dialog for a payload."""
        # Get current name
        current_name = self.payload_names[idx]
        
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Rename Payload {idx+1}")
        dialog.geometry("300x120")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.geometry(f"+{self.root.winfo_rootx()+200}+{self.root.winfo_rooty()+200}")
        
        # Label
        tk.Label(dialog, text=f"Enter new name for Payload {idx+1}:", 
                font=("Arial", 10)).pack(pady=(10, 5))
        
        # Entry field
        name_var = tk.StringVar(value=current_name)
        entry = tk.Entry(dialog, textvariable=name_var, font=("Arial", 10), width=30)
        entry.pack(pady=5)
        entry.select_range(0, tk.END)
        entry.focus_set()
        
        # Buttons
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def rename_and_close():
            new_name = name_var.get().strip()
            if new_name:
                self.update_payload_name(idx, new_name)
            dialog.destroy()
        
        tk.Button(btn_frame, text="Rename", command=rename_and_close,
                 font=("Arial", 9), width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                 font=("Arial", 9), width=10).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key
        dialog.bind("<Return>", lambda e: rename_and_close())

    def rename_selected_payload(self):
        """Rename the currently selected payload."""
        idx = self.payload_var.get() - 1
        self.show_payload_rename_dialog(idx)

    def update_payload_name(self, idx, new_name):
        """Update the name of a payload."""
        if new_name:
            self.payload_names[idx] = new_name
            
            # Update the notebook tab
            self.payload_notebook.tab(idx, text=new_name)
            
            # Update the button text
            self.payload_buttons[idx].config(text=new_name)
            
            # Try to update tab style
            try:
                self.payload_notebook.tab(idx, style=f"CustomTab{idx+1}.TNotebook.Tab")
            except:
                pass
            
            enqueue_log(f"[GUI] Payload {idx+1} renamed to: {new_name}")
            self.status_var.set(f"Payload {idx+1} renamed to: {new_name}")

    def update_bet_delay(self):
        """Update the bet delay from the entry field."""
        try:
            if self.one_time_trigger_var.get():
                enqueue_log("[GUI] One Time Trigger is active - Bet delay is 0 (all bets simultaneous)")
                self.status_var.set("⚡ One Time Trigger active (0 delay)")
                return
                
            delay = int(self.bet_delay_entry.get())
            if 0 <= delay <= 300:
                enqueue_log(f"[GUI] Bet delay updated to {delay} seconds")
                self.status_var.set(f"Bet delay set to {delay} seconds")
            else:
                messagebox.showerror("Invalid Value", "Bet delay must be between 0 and 300 seconds")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for bet delay")

    def save_logs(self):
        """Save logs to a file."""
        try:
            log_content = self.log.get("1.0", tk.END)
            if not log_content.strip():
                messagebox.showwarning("Empty Logs", "No logs to save")
                return
                
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"logs_{timestamp}.txt"
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write(log_content)
            
            enqueue_log(f"[GUI] Logs saved to {filename}")
            messagebox.showinfo("Logs Saved", f"Logs saved to {filename}")
            
        except Exception as e:
            enqueue_log(f"[GUI] Failed to save logs: {e}")
            messagebox.showerror("Error", f"Failed to save logs: {e}")

    def on_payload_tab_changed(self, event):
        """Update radio button when tab changes"""
        current_tab = self.payload_notebook.index(self.payload_notebook.select())
        if current_tab < 4:  # Only update radio buttons for first 4 tabs
            self.payload_var.set(current_tab + 1)  # Tabs are 0-indexed, payloads are 1-indexed

    def select_all_users(self):
        """Select all users in the listbox."""
        self.user_listbox.selection_clear(0, tk.END)
        for i in range(self.user_listbox.size()):
            self.user_listbox.selection_set(i)
    
    def deselect_all_users(self):
        """Deselect all users in the listbox."""
        self.user_listbox.selection_clear(0, tk.END)

    def deselect_user_by_email(self, email):
        """Deselect a specific user in the listbox by their email/phone.
        Called on the main thread after a successful bet to prevent re-sending.
        """
        for i in range(self.user_listbox.size()):
            if self.user_listbox.get(i) == email:
                self.user_listbox.selection_clear(i, i)
                enqueue_log(f"[GUI] ✔ Deselected user {email} (bet confirmed)")
                break

    def get_selected_users(self):
        """Get selected user indices and emails."""
        selected_indices = self.user_listbox.curselection()
        selected_emails = [self.user_listbox.get(i) for i in selected_indices]
        return selected_indices, selected_emails

    def get_selected_payload(self):
        """Get the selected payload text based on radio button selection."""
        payload_num = self.payload_var.get()
        
        if 1 <= payload_num <= 4:
            raw = self.bet_texts[payload_num - 1].get("1.0", tk.END).strip()
        else:
            enqueue_log(f"[GUI] ERROR: Invalid payload selection: {payload_num}")
            return None
            
        return raw

    def start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop_loop(self):
        # close all worker sessions if any
        if self.workers_cache:
            async def close_all():
                await asyncio.gather(*(w.close() for w in self.workers_cache))
            fut = asyncio.run_coroutine_threadsafe(close_all(), self.loop)
            try:
                fut.result(3)
            except Exception:
                pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=1)
        self.root.destroy()

    def clear_logs(self):
        self.log.delete(1.0, tk.END)

    def flush_logs(self):
        while not log_queue.empty():
            s = log_queue.get_nowait()
            self.log.insert(tk.END, s + "\n")
            self.log.see(tk.END)
        self.root.after(100, self.flush_logs)

    def update_status(self, message):
        self.status_var.set(message)
        self.root.update()

    # NEW: ON UPDATE DATA - Fetches limit, matched, and vol for selected user
    def on_update_data(self):
        """Update payload with limit, matched, and vol for selected user."""
        if not self.workers_cache:
            enqueue_log("[GUI] ERROR: Click 'Fetch Markets' first (to login & get CSRF).")
            self.update_status("Error: Run Fetch Markets first")
            messagebox.showerror("Error", "Please click 'Fetch Markets' first to login users.")
            return
        
        # Get selected payload
        raw = self.get_selected_payload()
        if not raw:
            enqueue_log("[GUI] ERROR: Selected payload is empty. Please paste payload first.")
            self.update_status("Error: Enter bet payload")
            messagebox.showerror("Error", "Please paste a bet payload first.")
            return
        
        # Parse the payload to get eventId, eventType, market_type
        base_payload = parse_urlencoded_body(raw)
        
        event_id = base_payload.get('eventId')
        event_type = base_payload.get('eventType')
        market_type = base_payload.get('market_type')
        
        if not event_id or not event_type or not market_type:
            enqueue_log("[GUI] ERROR: Payload missing required fields (eventId, eventType, market_type)")
            self.update_status("Error: Missing fields in payload")
            messagebox.showerror("Error", 
                "Payload is missing required fields.\n\n"
                "Required: eventId, eventType, market_type\n\n"
                f"Found:\n- eventId: {event_id}\n- eventType: {event_type}\n- market_type: {market_type}")
            return
        
        selected_indices, selected_emails = self.get_selected_users()
        if not selected_emails:
            enqueue_log("[GUI] ERROR: No users selected. Please select at least one user.")
            self.update_status("Error: No users selected")
            messagebox.showerror("Error", "Please select at least one user.")
            return
        
        # Only process first selected user for update data
        if len(selected_emails) > 1:
            enqueue_log("[GUI] Warning: Multiple users selected. Using first user for update data.")
        
        first_email = selected_emails[0]
        
        # Find the worker for this user
        worker = None
        for w in self.workers_cache:
            if w.email == first_email:
                worker = w
                break
        
        if not worker:
            enqueue_log(f"[GUI] ERROR: Worker not found for {first_email}. Run Fetch Markets first.")
            self.update_status("Error: Run Fetch Markets for selected user")
            return
        
        # Update status
        self.update_data_status.config(text=f"Updating {first_email}...", fg="#FF9800")
        self.btn_update_data.config(state=tk.DISABLED)
        
        async def update_data_flow():
            try:
                enqueue_log(f"[GUI] 🔄 Starting data update for {first_email}")
                enqueue_log(f"[GUI]   eventId={event_id}, eventType={event_type}, market_type={market_type}")
                
                # Step 1: Fetch limit from eventDetails
                enqueue_log(f"[{first_email}] Step 1: Fetching limit...")
                limit_value = await worker.fetch_limit(event_id, event_type)
                enqueue_log(f"[{first_email}] ✅ Limit fetched successfully")
                
                # Step 2: Fetch matched (hash) and vol (liquidity) from getMarketBook
                enqueue_log(f"[{first_email}] Step 2: Fetching matched & vol...")
                matched_data = await worker.fetch_matched_data(event_id, market_type, event_type)
                matched_value = matched_data['matched']
                vol_value = matched_data['vol']
                enqueue_log(f"[{first_email}] ✅ Matched & Vol fetched successfully")
                
                # Step 3: URL-encode the values (to match original format with %3D etc.)
                # The API returns values without URL encoding, but original payload has them encoded
                matched_value_encoded = quote(matched_value, safe='')
                limit_value_encoded = quote(limit_value, safe='')
                
                enqueue_log(f"[{first_email}] URL-encoded matched and limit values")
                
                # Step 4: Update the payload in the GUI
                # We need to preserve the EXACT original structure and order
                # Just replace the values of matched, limit (both), and vol
                
                # Get the original raw payload string
                payload_num = self.payload_var.get()
                if 1 <= payload_num <= 4:
                    original_raw = self.bet_texts[payload_num - 1].get("1.0", tk.END).strip()
                else:
                    raise RuntimeError("Invalid payload number")
                
                # Split by & to get individual key=value pairs
                parts = original_raw.split('&')
                new_parts = []
                limit_count = 0
                
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        
                        if key == 'matched':
                            # Replace matched value (URL-encoded)
                            new_parts.append(f"matched={matched_value_encoded}")
                        elif key == 'vol':
                            # Replace vol value (no encoding needed for numbers)
                            new_parts.append(f"vol={vol_value}")
                        elif key == 'limit':
                            # Replace limit value (URL-encoded, both occurrences)
                            new_parts.append(f"limit={limit_value_encoded}")
                            limit_count += 1
                        else:
                            # Keep original key=value exactly as is
                            new_parts.append(part)
                    else:
                        # Keep as is (shouldn't happen but just in case)
                        new_parts.append(part)
                
                new_payload_str = "&".join(new_parts)
                
                # Update the text area with new payload
                if 1 <= payload_num <= 4:
                    self.bet_texts[payload_num - 1].delete("1.0", tk.END)
                    self.bet_texts[payload_num - 1].insert("1.0", new_payload_str)
                
                enqueue_log(f"[{first_email}] ✅ Payload updated successfully!")
                enqueue_log(f"[{first_email}]   - matched: {matched_value_encoded[:50]}...")
                enqueue_log(f"[{first_email}]   - limit: {limit_value_encoded[:50]}... (updated {limit_count}x)")
                enqueue_log(f"[{first_email}]   - vol: {vol_value}")
                
                # Update status on main thread
                self.root.after(0, lambda: self.update_data_status.config(
                    text=f"✅ Updated for {first_email}", fg="#4CAF50"))
                self.root.after(0, lambda: self.btn_update_data.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.status_var.set(f"Data updated for {first_email}"))
                
            except Exception as e:
                enqueue_log(f"[{first_email}] ❌ ERROR: {e}")
                self.root.after(0, lambda: self.update_data_status.config(
                    text=f"❌ Error: {str(e)[:20]}...", fg="#F44336"))
                self.root.after(0, lambda: self.btn_update_data.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.status_var.set(f"Update failed: {e}"))
        
        # Run the update flow
        asyncio.run_coroutine_threadsafe(update_data_flow(), self.loop)
        enqueue_log(f"[GUI] Update Data started for {first_email}...")
        self.status_var.set(f"Updating data for {first_email}...")

    # Button callbacks submit coroutine to background loop
    def on_fetch_markets(self):
        selected_indices, selected_emails = self.get_selected_users()
        if not selected_emails:
            enqueue_log("[GUI] ERROR: No users selected. Please select at least one user.")
            self.update_status("Error: No users selected")
            return

        enqueue_log(f"[GUI] Selected {len(selected_emails)} users: {', '.join(selected_emails)}")
        
        # Create workers only for selected users
        selected_workers = []
        for i in selected_indices:
            email, password = self.users[i]
            selected_workers.append(UserWorker(email, password))
        
        # Store all workers (including previously created ones if needed)
        # For simplicity, we'll replace with new workers for selected users
        self.workers_cache = selected_workers

        # run the flow in background loop
        asyncio.run_coroutine_threadsafe(fetch_markets_flow(selected_workers), self.loop)
        enqueue_log(f"[GUI] Fetch Markets started for {len(selected_emails)} users...")
        self.update_status(f"Fetching markets for {len(selected_emails)} users")

    def on_check_balance(self):
        """Check balance for all selected users who have an active session."""
        if not self.workers_cache:
            enqueue_log("[GUI] ERROR: Click 'Fetch Markets' first (to login & get CSRF).")
            self.update_status("Error: Run Fetch Markets first")
            return

        selected_indices, selected_emails = self.get_selected_users()
        if not selected_emails:
            enqueue_log("[GUI] ERROR: No users selected.")
            self.update_status("Error: No users selected")
            return

        # Filter workers to only selected users
        selected_workers = [w for w in self.workers_cache if w.email in selected_emails]
        if not selected_workers:
            enqueue_log("[GUI] ERROR: No active workers for selected users. Run Fetch Markets first.")
            self.update_status("Error: Run Fetch Markets for selected users")
            return

        async def check_balance_flow():
            enqueue_log(f"[GUI] Checking balance for {len(selected_workers)} user(s)...")
            tasks = [w.get_balance() for w in selected_workers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            ok = 0
            for w, result in zip(selected_workers, results):
                if isinstance(result, Exception):
                    enqueue_log(f"[{w.email}] ❌ Balance check failed: {result}")
                else:
                    ok += 1
            enqueue_log(f"[GUI] Balance check done — {ok}/{len(selected_workers)} OK")

        asyncio.run_coroutine_threadsafe(check_balance_flow(), self.loop)
        enqueue_log(f"[GUI] Check Balance started for {len(selected_workers)} user(s)...")
        self.update_status(f"Checking balance for {len(selected_workers)} users")

    def on_check_wallet(self):
        """Check wallet history for selected users — balance + latest transaction + UTR + name.
        Reuses existing logged-in sessions. No re-login needed.
        Output format: email: 💰 <balance>  <amount> <status>  UTR <utr>  <ac_holder>
        """
        if not self.workers_cache:
            enqueue_log("[GUI] ERROR: Click 'Fetch Markets' first (to login & get CSRF).")
            self.update_status("Error: Run Fetch Markets first")
            return

        selected_indices, selected_emails = self.get_selected_users()
        if not selected_emails:
            enqueue_log("[GUI] ERROR: No users selected.")
            self.update_status("Error: No users selected")
            return

        selected_workers = [w for w in self.workers_cache if w.email in selected_emails]
        if not selected_workers:
            enqueue_log("[GUI] ERROR: No active workers for selected users. Run Fetch Markets first.")
            self.update_status("Error: Run Fetch Markets for selected users")
            return

        async def check_wallet_flow():
            enqueue_log(f"[GUI] 📝 Fetching wallet info for {len(selected_workers)} user(s)...")

            async def fetch_one(w):
                try:
                    # Get balance and wallet info in parallel
                    bal_task    = asyncio.create_task(w.get_balance())
                    wallet_task = asyncio.create_task(w.get_wallet_info())
                    results = await asyncio.gather(bal_task, wallet_task, return_exceptions=True)

                    # bal_task updates w.balance as side-effect; wallet_task returns dict
                    if isinstance(results[0], Exception):
                        raise results[0]
                    bal  = w.balance if w.balance is not None else "N/A"
                    info = results[1] if not isinstance(results[1], Exception) else None
                    return w.email, bal, info, None
                except Exception as e:
                    return w.email, None, None, str(e)

            # Run all in parallel
            tasks = [fetch_one(w) for w in selected_workers]
            all_results = await asyncio.gather(*tasks, return_exceptions=True)

            enqueue_log("[GUI] ─── Wallet Results ───────────────────────────────")
            ok = 0
            for item in all_results:
                if isinstance(item, Exception):
                    enqueue_log(f"[GUI] ❌ Unexpected error: {item}")
                    continue
                email, bal, info, err = item
                if err:
                    enqueue_log(f"[GUI] {email}: ❌ {err}")
                    continue
                ok += 1
                # Build the output line
                line = f"{email}: 💰 {bal}"
                if info:
                    if info["trans_amount"] != "N/A":
                        line += f"  {info['trans_amount']}"
                    if info["trans_status"] != "N/A":
                        line += f"  {info['trans_status']}"
                    if info["utr"]:
                        line += f"  UTR {info['utr']}"
                    if info["ac_holder"]:
                        line += f"  {info['ac_holder']}"
                enqueue_log(line)

            enqueue_log(f"[GUI] ────────────────────────────────────────────────")
            enqueue_log(f"[GUI] Wallet check done — {ok}/{len(selected_workers)} OK")

        asyncio.run_coroutine_threadsafe(check_wallet_flow(), self.loop)
        self.update_status(f"Fetching wallet info for {len(selected_workers)} users...")

    def on_call_funodds(self):
        if not self.workers_cache:
            enqueue_log("[GUI] ERROR: Click 'Fetch Markets' first.")
            self.update_status("Error: Run Fetch Markets first")
            return

        selected_indices, selected_emails = self.get_selected_users()
        if not selected_emails:
            enqueue_log("[GUI] ERROR: No users selected. Please select at least one user.")
            self.update_status("Error: No users selected")
            return

        # Filter workers to only include selected users
        selected_workers = []
        for w in self.workers_cache:
            if w.email in selected_emails:
                selected_workers.append(w)
        
        if not selected_workers:
            enqueue_log("[GUI] ERROR: No workers found for selected users. Run Fetch Markets first.")
            self.update_status("Error: Run Fetch Markets for selected users")
            return

        async def funodds_only():
            await call_funodds_flow(selected_workers)
            # Print unique selection IDs from cleaned output
            for w in selected_workers:
                if not w.funodds_data_cleaned:
                    enqueue_log(f"[{w.email}] No funodds data")
                    continue

                seen = set()
                enqueue_log(f"[{w.email}] UNIQUE SELECTIONS:")
                for market in w.funodds_data_cleaned:
                    for r in market["runners"]:
                        sid = r["selectionId"]
                        if sid in seen:
                            continue
                        seen.add(sid)
                        enqueue_log(f"  selectionId={sid} -> {r}")

        asyncio.run_coroutine_threadsafe(funodds_only(), self.loop)
        enqueue_log(f"[GUI] FunOdds started for {len(selected_emails)} users...")
        self.update_status(f"Calling FunOdds for {len(selected_emails)} users")

    # FIXED: PLACE BET HANDLER with One Time Trigger feature
    def on_place_bet(self):
        if not self.workers_cache:
            enqueue_log("[GUI] ERROR: Click 'Fetch Markets' first (to login & get CSRF).")
            self.update_status("Error: Run Fetch Markets first")
            return

        # Get selected payload
        raw = self.get_selected_payload()
        if not raw:
            enqueue_log("[GUI] ERROR: Selected payload is empty. Please paste payload first.")
            self.update_status("Error: Enter bet payload")
            return

        selected_indices, selected_emails = self.get_selected_users()
        if not selected_emails:
            enqueue_log("[GUI] ERROR: No users selected. Please select at least one user.")
            self.update_status("Error: No users selected")
            return

        # Filter workers to only include selected users
        selected_workers = []
        for w in self.workers_cache:
            if w.email in selected_emails:
                selected_workers.append(w)
        
        if not selected_workers:
            enqueue_log("[GUI] ERROR: No workers found for selected users. Run Fetch Markets first.")
            self.update_status("Error: Run Fetch Markets for selected users")
            return

        # Parse the base payload
        base_payload = parse_urlencoded_body(raw)
        
        # Check if vol parameter exists in payload
        if 'vol' not in base_payload:
            enqueue_log("[GUI] ERROR: No 'vol' parameter in payload! Click 'Update Data' first.")
            messagebox.showerror("Missing Volume", 
                "No 'vol' parameter found in payload!\n\n"
                "Please click 'Update Data' button first to fetch:\n"
                "- matched\n- limit\n- vol\n\n"
                "Then try placing bet again.")
            return
        
        workers = selected_workers
        payload_num = self.payload_var.get()
        num_users = len(workers)
        
        # Get bet delay - check for One Time Trigger first
        if self.one_time_trigger_var.get():
            bet_delay = 0  # No delay for one-time trigger
            try:
                ott_batch_size = int(self.ott_batch_entry.get())
                if ott_batch_size < 1:
                    ott_batch_size = 10
            except ValueError:
                ott_batch_size = 10
            enqueue_log(f"[GUI] ⚡ ONE TIME TRIGGER ACTIVE - Batch size: {ott_batch_size}")
        else:
            try:
                bet_delay = int(self.bet_delay_entry.get())
                if bet_delay < 0:
                    bet_delay = 0
                elif bet_delay > 300:  # Maximum 5 minutes
                    bet_delay = 300
            except ValueError:
                bet_delay = 6  # Default value
                enqueue_log(f"[GUI] Using default bet delay: {bet_delay} seconds")

        # Check if betting is already active
        if self.is_betting_active:
            enqueue_log("[GUI] ERROR: Betting is already in progress. Please wait or stop current betting.")
            self.update_status("Error: Betting already in progress")
            return

        # Set betting active flag
        self.is_betting_active = True
        self.betting_stopped = False
        
        # Update UI
        self.btn_stop_betting.config(state=tk.NORMAL)
        self.btn_placebet.config(state=tk.DISABLED)

        async def placebet_flow():
            payload_name = self.payload_names[payload_num-1]
            payload_color = "Blue" if payload_num in [1,3] else "Pink"
            enqueue_log(f"[GUI] Using Payload '{payload_name}' (Color: {payload_color})")
            
            # Log betting mode
            if bet_delay == 0:
                enqueue_log(f"[GUI] ⚡ One Time Trigger - All {len(workers)} bets will fire simultaneously")
            
            # Log teams strategy
            if self.dynamic_teams_enabled:
                enqueue_log(f"[GUI] Teams strategy: Dynamic assignment ENABLED")
                enqueue_log(f"[GUI] Each user gets 4 unique team entries (one per payload)")
            else:
                enqueue_log(f"[GUI] Teams strategy: Using teams from payload")
            
            # Create tasks list
            bet_tasks = []
            
            if bet_delay == 0:  # ONE TIME TRIGGER - All bets at once
                enqueue_log("[GUI] ⚡ Creating simultaneous bet tasks for all users...")
                
                for i, w in enumerate(workers):
                    # Check if betting was stopped
                    if self.betting_stopped:
                        enqueue_log(f"[GUI] Betting stopped by user. Cancelling remaining {len(workers)-i} bets.")
                        break
                    
                    # Generate complete payload for this user (use same payload for all)
                    user_payload = self.generate_payload_for_user_simple(base_payload, i, payload_num)
                    
                    # Log the volume being used for this user
                    vol_value = user_payload.get('vol', 'N/A')
                    enqueue_log(f"[{w.email}] Queueing bet with volume: {vol_value}")
                    
                    # Create bet task (on_success deselects this user when bet confirmed)
                    _email = w.email
                    task = asyncio.create_task(self._place_bet_with_logging(
                        w, user_payload,
                        on_success=lambda e=_email: self.deselect_user_by_email(e)
                    ))
                    bet_tasks.append(task)
                    self.pending_bet_tasks.append(task)  # Add to pending tasks list

                # Process in batches using ott_batch_size
                enqueue_log(f"[GUI] ⚡ Firing {len(bet_tasks)} bets in batches of {ott_batch_size}...")
                results = []
                for i in range(0, len(bet_tasks), ott_batch_size):
                    if self.betting_stopped:
                        break
                    batch = bet_tasks[i:i+ott_batch_size]
                    enqueue_log(f"[GUI] ⚡ Batch {i//ott_batch_size + 1}: firing {len(batch)} bet(s)...")
                    batch_results = await asyncio.gather(*batch, return_exceptions=True)
                    results.extend(batch_results)
            
            else:  # NORMAL MODE with delay between bets
                for i, w in enumerate(workers):
                    # Check if betting was stopped
                    if self.betting_stopped:
                        enqueue_log(f"[GUI] Betting stopped by user. Cancelling remaining {len(workers)-i} bets.")
                        break
                    
                    # Generate complete payload for this user
                    user_payload = self.generate_payload_for_user_simple(base_payload, i, payload_num)
                    
                    # Log the volume being used for this user
                    vol_value = user_payload.get('vol', 'N/A')
                    enqueue_log(f"[{w.email}] Using volume: {vol_value}")
                    
                    # Create bet task (on_success deselects this user when bet confirmed)
                    _email = w.email
                    task = asyncio.create_task(self._place_bet_with_logging(
                        w, user_payload,
                        on_success=lambda e=_email: self.deselect_user_by_email(e)
                    ))
                    bet_tasks.append(task)
                    self.pending_bet_tasks.append(task)  # Add to pending tasks list
                    
                    # Add delay before starting next bet (except after the last one)
                    if i < len(workers) - 1:
                        enqueue_log(f"[GUI] Waiting {bet_delay} seconds before starting next bet...")
                        
                        # Wait with ability to stop
                        for _ in range(bet_delay):
                            if self.betting_stopped:
                                enqueue_log(f"[GUI] Betting stopped during delay. Cancelling remaining bets.")
                                break
                            await asyncio.sleep(1)
                        
                        if self.betting_stopped:
                            break
                
                # Wait for all bets to complete (for normal mode)
                if bet_tasks and not self.betting_stopped:
                    results = await asyncio.gather(*bet_tasks, return_exceptions=True)
            
            # Log any errors
            if 'results' in locals():  # Check if results variable exists
                for w, result in zip(workers[:len(results)], results):
                    if isinstance(result, Exception):
                        if isinstance(result, asyncio.CancelledError):
                            enqueue_log(f"[{w.email}] BET CANCELLED: Task was stopped by user")
                        else:
                            enqueue_log(f"[{w.email}] BET ERROR: {result}")
            
            # Clean up
            self.pending_bet_tasks.clear()
            
            # Update UI state
            self.btn_stop_betting.config(state=tk.DISABLED)
            self.btn_placebet.config(state=tk.NORMAL)
            self.is_betting_active = False
            
            if self.betting_stopped:
                enqueue_log(f"[GUI] Betting stopped. Ready for new bets.")
                self.status_var.set(f"Betting stopped - Ready for new bets")
            else:
                if bet_delay == 0:
                    enqueue_log(f"[GUI] ⚡ One Time Trigger completed - All {len(workers)} bets fired simultaneously")
                    enqueue_log("[GUI] ⚡ One Time Trigger remains enabled - Ready for next simultaneous betting")
                else:
                    enqueue_log(f"[GUI] All bets completed for {len(workers)} users")
                enqueue_log(f"[GUI] Ready for new bets")
                self.status_var.set(f"All bets completed - Ready for new bets")

        # Run the bet flow and store the future
        self.current_bet_future = asyncio.run_coroutine_threadsafe(placebet_flow(), self.loop)
        payload_name = self.payload_names[payload_num-1]
        enqueue_log(f"[GUI] Place Bet started for {len(selected_emails)} users with Payload '{payload_name}'...")
        self.status_var.set(f"Placing bets for {len(selected_emails)} users (Use Stop Betting to cancel)")

    async def _place_bet_with_logging(self, worker, payload, on_success=None):
        """Helper function to auto-update payload, place bet and log results.
        on_success: optional no-arg callback scheduled on main thread when bet placed successfully.
        """
        try:
            # Check if betting was stopped
            if self.betting_stopped:
                raise asyncio.CancelledError("Betting stopped by user")
            
            # AUTO-UPDATE: Fetch fresh limit, matched, vol before placing bet
            if self.skip_update_var.get():
                enqueue_log(f"[{worker.email}] 🔴 SKIP UPDATE - Using raw payload as-is (no auto-update)")
                updated_payload = dict(payload)
            else:
                enqueue_log(f"[{worker.email}] 🔄 Auto-updating payload data...")
                updated_payload = await worker.auto_update_payload(payload)
            
            # Log the updated volume
            vol_value = updated_payload.get('vol', 'N/A')
            
            # Log the teams being sent if dynamic teams enabled
            if self.dynamic_teams_enabled:
                runner_name = updated_payload.get('runnerName', 'N/A').replace('+', ' ')
                teams = updated_payload.get('teams', 'N/A').replace('+', ' ')
                enqueue_log(f"[{worker.email}] 🎯 Sending bet → volume={vol_value}")
                enqueue_log(f"[{worker.email}]   runnerName='{runner_name}'")
                enqueue_log(f"[{worker.email}]   teams='{teams}'")
            else:
                enqueue_log(f"[{worker.email}] 🎯 Sending bet → volume={vol_value}")
            
            # Place bet with updated payload
            bet_success = await worker.place_bet(updated_payload)
            
            if bet_success:
                enqueue_log(f"[{worker.email}] ✅ Bet placed successfully — deselecting user")
                # Deselect this user on the main thread so they are skipped on next run
                if on_success:
                    self.root.after(0, on_success)
            else:
                enqueue_log(f"[{worker.email}] ✅ Bet task completed (no success response)")
                
        except asyncio.CancelledError:
            enqueue_log(f"[{worker.email}] ❌ BET CANCELLED: Task was stopped by user")
            raise
        except Exception as e:
            enqueue_log(f"[{worker.email}] ❌ BET ERROR: {e}")
            raise


# ----------------- run GUI -----------------
def main():
    # Start with password protection
    root = tk.Tk()
    password_app = PasswordApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()