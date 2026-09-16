#!/usr/bin/env python3
"""Claude Code Buddy - Desktop Pet (Claw'd-style mascot).

Always-on-top, borderless, transparent-background pixel mascot: flat
single-color body, two side arm nubs, four legs with a wide center notch,
and blocky eyes. Everything is drawn as flat grid rectangles - no
outlines, gradients, or curves.

Grid proportions were measured from a reference image of the mascot and
expressed in units of 1/72nd of the body width.

The mascot randomly switches between a set of expressions/actions
(normal, happy, sleepy, surprised, wink, working, nap, look_around, jump)
every 5-8 seconds, each with its own pose/eye shape and optional
decoration. A single click (press + release without dragging) also
immediately cycles to a new one; double-click still makes it talk, and
dragging still moves it.
"""
import json
import random
import threading
import tkinter as tk
import urllib.request
from datetime import datetime

BG = "magenta"  # transparent color key
BODY = "#D97757"
EYE = "#1A1310"
TOOL = "#8A8A8A"
ACCENT = "#FFD166"

CELL = 0.75  # screen pixels per art pixel
GW_BODY = 88
EXTRA_RIGHT = 24  # side margin reserved for the "working" hammer/button prop
GW = GW_BODY + EXTRA_RIGHT
TOP_MARGIN = 44  # headroom above the body: decorations + full jump clearance
BODY_H0 = 70  # original body+legs height (without headroom)
GH = BODY_H0 + TOP_MARGIN
W, H = int(GW * CELL), int(GH * CELL)

BODY_COL, BODY_W, BODY_H = 8, 72, 52
BODY_ROW = TOP_MARGIN
ARM_ROW, ARM_W, ARM_H = TOP_MARGIN + 17, 8, 18
LEG_ROW, LEG_W, LEG_H = TOP_MARGIN + 52, 8, 17
LEG_COLS = (8, 24, 56, 72)
EYE_ROW = TOP_MARGIN + 15
EYE_COLS = (15, 62)

GROUND_ROW = LEG_ROW + LEG_H  # = GH, the bottom of the sprite
PROP_COL = GW_BODY + 4  # left edge of the hammer/button prop area

CLICK_DRAG_THRESHOLD = 4  # pixels of movement before a press counts as a drag


def pattern_to_cells(rows):
    return [(c, r) for r, line in enumerate(rows) for c, ch in enumerate(line) if ch == "X"]


# --- eye glyphs (each occupies an 11-wide x 13-tall box) ---------------

_CHEVRON_TOP = [
    "X..........",
    "XXX........",
    "XXXXXX.....",
    "XXXXXXXX...",
    ".XXXXXXXXX.",
    "....XXXXXXX",
    "......XXXXX",
]
CHEVRON_RIGHT = pattern_to_cells(_CHEVRON_TOP + _CHEVRON_TOP[-2::-1])  # ">"
CHEVRON_LEFT = [(10 - c, r) for c, r in CHEVRON_RIGHT]  # "<"

FLAT_BAR = pattern_to_cells(
    ["." * 11] * 5 + ["X" * 11] * 3 + ["." * 11] * 5
)  # closed / sleeping / effortful eye

SQUARE_EYE = pattern_to_cells(
    ["." * 11] * 2 + [".." + "X" * 7 + ".."] * 7 + ["." * 11] * 4
)  # wide-open surprised eye

HAPPY_ARC = pattern_to_cells(
    [
        "....XXX....",
        "...XXXXX...",
        "..XX...XX..",
        ".XX.....XX.",
        "XX.......XX",
    ] + ["." * 11] * 8
)  # upward happy squint

LOOK_LEFT = pattern_to_cells(
    ["." * 11] * 4 + ["XXXX......."] * 4 + ["." * 11] * 5
)  # pupil shifted to the left side of the socket
LOOK_RIGHT = pattern_to_cells(
    ["." * 11] * 4 + [".......XXXX"] * 4 + ["." * 11] * 5
)  # pupil shifted to the right side of the socket

# --- head decoration glyphs --------------------------------------------

Z_GLYPH = pattern_to_cells(["XXXXX", "...X.", "..X..", ".X...", "XXXXX"])
EXCLAIM_GLYPH = pattern_to_cells(["XX", "XX", "XX", "XX", "..", "XX"])
QUESTION_GLYPH = pattern_to_cells([".XX..", "X..X.", "...X.", "..X..", ".....", "..X.."])
SPARKLE_GLYPH = pattern_to_cells([".X.", "XXX", ".X."])
PLUS_GLYPH = pattern_to_cells(["..X..", "..X..", "XXXXX", "..X..", "..X.."])  # jump sparkle

# --- lying-down "nap" pose geometry -------------------------------------
# Measured from a reference clip: it's the standing silhouette flipped -
# the 4 legs become small spikes poking up out of the top of a squat
# body, and the arms droop down to a lower, ground-level position.
NAP_ARM_H = 12
NAP_BODY_H = 26
NAP_SPIKE_W, NAP_SPIKE_H = 4, 6
NAP_SPIKE_COLS = (10, 26, 58, 74)
NAP_BODY_BOTTOM = GROUND_ROW
NAP_BODY_TOP = NAP_BODY_BOTTOM - NAP_BODY_H
NAP_SPIKE_TOP = NAP_BODY_TOP - NAP_SPIKE_H
NAP_ARM_TOP = NAP_BODY_BOTTOM - NAP_ARM_H

# name -> (left eye glyph, right eye glyph, decoration key or None)
# "nap" and "look_around" are handled as special cases in draw(); their
# glyph slots below are unused placeholders so they still take part in
# the random rotation.
EXPRESSIONS = {
    "normal": (CHEVRON_RIGHT, CHEVRON_LEFT, None),
    "happy": (HAPPY_ARC, HAPPY_ARC, "happy"),
    "sleepy": (FLAT_BAR, FLAT_BAR, "sleepy"),
    "surprised": (SQUARE_EYE, SQUARE_EYE, "surprised"),
    "wink": (CHEVRON_RIGHT, FLAT_BAR, None),
    "working": (FLAT_BAR, FLAT_BAR, "working"),
    "nap": (None, None, None),
    "look_around": (None, None, None),
    "jump": (HAPPY_ARC, HAPPY_ARC, "jump"),
}

TALK_LINES = [
    "嗨！我在陪你寫 code 喔～",
    "記得存檔啦！",
    "休息一下吧？",
    "這個 bug 有點意思。",
    "你今天很棒！",
    "喝口水吧。",
]

# random pool for the every-5-to-10-minute reminder timer: health nudges +
# a few playful lines, plus (when data is available) a weather report.
REMINDER_LINES = [
    "該起來走一走囉！",
    "記得多喝水喔！",
    "眨眨眼，讓眼睛休息一下～",
    "肩膀酸了嗎？轉一轉脖子吧！",
    "深呼吸一口氣，放鬆一下！",
    "偷偷說，多存幾次檔比較安心喔。",
    "你已經很努力了，真棒！",
    "今天的水/咖啡喝了嗎？",
    "站起來伸個懶腰吧～",
]

# fixed daily greetings, keyed by "HH:MM"
GREETINGS = {
    "08:30": "早安！新的一天開始囉～",
    "13:30": "午安！別忘了休息一下眼睛。",
    "17:00": "下班時間快到囉，準備收工吧！",
}

WEATHER_REFRESH_MS = 15 * 60 * 1000  # refresh weather data every 15 minutes
CLOCK_CHECK_MS = 30 * 1000  # check hourly-chime / daily-greeting every 30s


class DesktopBuddy:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.config(bg=BG)
        self.root.wm_attributes("-transparentcolor", BG)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{sw - W - 60}+{sh - H - 100}")

        self.canvas = tk.Canvas(self.root, width=W, height=H, bg=BG, highlightthickness=0)
        self.canvas.pack()

        self.tick = 0
        self.state = "normal"
        self.bubble = None
        self._dx = self._dy = 0
        self._press_x = self._press_y = 0
        self._dragged = False
        self._state_job = None

        self.weather = None
        self._greeted = {}
        self._last_hour_chime = None

        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.do_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.talk)
        self.canvas.bind("<ButtonPress-3>", self.show_menu)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="說話", command=self.talk)
        self.menu.add_command(label="換表情", command=self.change_state)
        self.menu.add_command(label="查天氣", command=self.show_weather_now)
        self.menu.add_command(label="結束", command=self.root.destroy)

        self.schedule_state_change()
        self.schedule_reminder()
        self.schedule_weather_fetch()
        self.check_clock()
        self.animate()

    def start_drag(self, event):
        self._dx, self._dy = event.x, event.y
        self._press_x, self._press_y = event.x_root, event.y_root
        self._dragged = False

    def do_drag(self, event):
        if abs(event.x_root - self._press_x) > CLICK_DRAG_THRESHOLD or \
                abs(event.y_root - self._press_y) > CLICK_DRAG_THRESHOLD:
            self._dragged = True
        x = self.root.winfo_pointerx() - self._dx
        y = self.root.winfo_pointery() - self._dy
        self.root.geometry(f"+{x}+{y}")
        self.remove_bubble()

    def on_release(self, event):
        if not self._dragged:
            self.change_state()

    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def talk(self, event=None):
        self.show_message(random.choice(TALK_LINES), duration=2500)

    def show_message(self, text, duration=4500):
        self.remove_bubble()
        self.bubble = tk.Toplevel(self.root)
        self.bubble.overrideredirect(True)
        self.bubble.wm_attributes("-topmost", True)
        tk.Label(
            self.bubble, text=text, bg="#FFF8E7", fg="#333333",
            font=("Microsoft JhengHei", 10), padx=8, pady=4,
            relief="solid", bd=1, wraplength=220, justify="left",
        ).pack()
        self.bubble.update_idletasks()
        bw = self.bubble.winfo_width()
        x = self.root.winfo_x() + W // 2 - bw // 2
        y = self.root.winfo_y() - self.bubble.winfo_height() - 10
        self.bubble.geometry(f"+{x}+{y}")
        self.root.after(duration, self.remove_bubble)

    def remove_bubble(self):
        if self.bubble is not None:
            try:
                self.bubble.destroy()
            except tk.TclError:
                pass
            self.bubble = None

    def schedule_state_change(self):
        if self._state_job is not None:
            self.root.after_cancel(self._state_job)
        self._state_job = self.root.after(random.randint(5000, 8000), self.change_state)

    def change_state(self):
        choices = [s for s in EXPRESSIONS if s != self.state]
        self.state = random.choice(choices)
        self.schedule_state_change()

    # --- reminders: random health/fun nudges + weather, every 5-10 min ---

    def schedule_reminder(self):
        self.root.after(random.randint(300_000, 600_000), self.fire_reminder)

    def fire_reminder(self):
        candidates = list(REMINDER_LINES)
        if self.weather is not None:
            candidates.append("__weather__")
        choice = random.choice(candidates)
        if choice == "__weather__":
            self.show_message(self.weather_message())
        else:
            self.show_message(choice)
        self.schedule_reminder()

    # --- weather: fetched in a background thread, no API key needed ------

    def schedule_weather_fetch(self):
        threading.Thread(target=self._fetch_weather_worker, daemon=True).start()
        self.root.after(WEATHER_REFRESH_MS, self.schedule_weather_fetch)

    def _fetch_weather_worker(self):
        try:
            loc_req = urllib.request.Request(
                "https://ipinfo.io/json", headers={"User-Agent": "Mozilla/5.0"}
            )
            loc = json.loads(urllib.request.urlopen(loc_req, timeout=8).read())
            lat, lon = loc["loc"].split(",")
            city = loc.get("city", "")

            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&current=temperature_2m,relative_humidity_2m,precipitation"
                "&hourly=precipitation_probability&timezone=auto&forecast_days=1"
            )
            data = json.loads(urllib.request.urlopen(url, timeout=8).read())
            cur = data["current"]
            hourly_times = data["hourly"]["time"]
            hourly_prob = data["hourly"]["precipitation_probability"]
            idx = hourly_times.index(cur["time"]) if cur["time"] in hourly_times else 0
            self.weather = {
                "city": city,
                "temp": cur["temperature_2m"],
                "humidity": cur["relative_humidity_2m"],
                "precip": cur["precipitation"],
                "precip_prob": hourly_prob[idx] if hourly_prob else 0,
            }
        except Exception:
            pass  # keep whatever (possibly None) weather data we already had

    def weather_message(self):
        w = self.weather
        if w["precip_prob"] >= 50:
            return f"目前降雨機率 {w['precip_prob']:.0f}%，記得帶把傘！"
        if w["temp"] <= 10:
            return f"目前氣溫探到 {w['temp']:.0f}°C，天氣濕冷，多穿件外套！"
        if w["precip"] >= 15:
            return "目前雨勢較大，外出請小心！"
        return f"目前氣溫 {w['temp']:.0f}°C，濕度 {w['humidity']:.0f}%"

    def show_weather_now(self):
        if self.weather is None:
            self.show_message("天氣資料查詢中，稍後再試一次～")
        else:
            self.show_message(self.weather_message())

    # --- clock: hourly chime + 3 fixed daily greetings --------------------

    def check_clock(self):
        now = datetime.now()
        today = now.date()
        hm = now.strftime("%H:%M")

        if hm in GREETINGS and self._greeted.get(hm) != today:
            self._greeted[hm] = today
            self.show_message(GREETINGS[hm], duration=5000)

        if now.minute == 0:
            marker = (today, now.hour)
            if self._last_hour_chime != marker:
                self._last_hour_chime = marker
                self.show_message(self.hour_message(now.hour), duration=4000)

        self.root.after(CLOCK_CHECK_MS, self.check_clock)

    @staticmethod
    def hour_message(hour):
        if hour < 6:
            period = "凌晨"
        elif hour < 12:
            period = "上午"
        elif hour == 12:
            period = "中午"
        elif hour < 18:
            period = "下午"
        else:
            period = "晚上"
        h12 = hour % 12 or 12
        return f"現在是{period} {h12} 點囉！"

    def px(self, gx, gy, color, gw=1, gh=1):
        self.canvas.create_rectangle(
            gx * CELL, gy * CELL, (gx + gw) * CELL, (gy + gh) * CELL,
            fill=color, outline=color,
        )

    def draw_glyph(self, col, row, glyph, color):
        for dc, dr in glyph:
            self.px(col + dc, row + dr, color)

    def draw_glyph_scaled(self, col, row, glyph, color, scale):
        for dc, dr in glyph:
            self.px(col + dc * scale, row + dr * scale, color, gw=scale, gh=scale)

    def draw_working(self):
        struck = (self.tick // 10) % 2 == 1

        base_h = 4
        base_row = GROUND_ROW - base_h
        self.px(PROP_COL, base_row, TOOL, gw=8, gh=base_h)

        cap_row = base_row - (1 if struck else 3)
        cap_h = 1 if struck else 3
        self.px(PROP_COL + 1, cap_row, ACCENT if struck else EYE, gw=6, gh=cap_h)

        head_row = (base_row - 6) if struck else (ARM_ROW - 20)
        self.px(PROP_COL - 2, head_row, TOOL, gw=12, gh=4)
        handle_top = head_row + 4
        handle_bottom = cap_row
        if handle_bottom > handle_top:
            self.px(PROP_COL + 3, handle_top, TOOL, gw=2, gh=handle_bottom - handle_top)

        if struck:
            self.px(PROP_COL - 4, cap_row - 1, ACCENT, gw=2, gh=2)
            self.px(PROP_COL + 10, cap_row - 1, ACCENT, gw=2, gh=2)

    def draw_nap(self):
        self.px(BODY_COL, NAP_BODY_TOP, BODY, gw=BODY_W, gh=NAP_BODY_H)
        self.px(0, NAP_ARM_TOP, BODY, gw=ARM_W, gh=NAP_ARM_H)
        self.px(GW_BODY - ARM_W, NAP_ARM_TOP, BODY, gw=ARM_W, gh=NAP_ARM_H)
        for col in NAP_SPIKE_COLS:
            self.px(col, NAP_SPIKE_TOP, BODY, gw=NAP_SPIKE_W, gh=NAP_SPIKE_H)
        for col in EYE_COLS:
            self.draw_glyph(col, NAP_BODY_TOP + 10, FLAT_BAR, EYE)

        # a couple of Z's cascade upward, growing larger as they rise, then loop
        cycle = 40
        for phase in (0, 20):
            p = (self.tick + phase) % cycle
            scale = 1 + p // 10
            row = NAP_SPIKE_TOP - 4 - p
            self.draw_glyph_scaled(64, row, Z_GLYPH, EYE, scale)

    def draw_decoration(self, decor, bob):
        if decor == "sleepy":
            float_off = (self.tick // 3) % 10
            self.draw_glyph(60, TOP_MARGIN - 4 - float_off // 2, Z_GLYPH, EYE)
        elif decor == "surprised":
            self.draw_glyph(43, TOP_MARGIN - 8, EXCLAIM_GLYPH, EYE)
        elif decor == "happy":
            if (self.tick // 8) % 2 == 0:
                self.draw_glyph(4, TOP_MARGIN - 11, SPARKLE_GLYPH, EYE)
                self.draw_glyph(80, TOP_MARGIN - 8, SPARKLE_GLYPH, EYE)
            else:
                self.draw_glyph(6, TOP_MARGIN - 8, SPARKLE_GLYPH, EYE)
                self.draw_glyph(78, TOP_MARGIN - 12, SPARKLE_GLYPH, EYE)
        elif decor == "working":
            self.draw_working()
        elif decor == "jump":
            # bright sparkles ride along with the hop, twinkling on and off
            for col, row_off, twinkle_ph in ((-8, -4, 0), (92, 2, 5), (40, -18, 10)):
                if (self.tick + twinkle_ph) % 12 < 8:
                    self.draw_glyph(col, TOP_MARGIN + row_off + bob, PLUS_GLYPH, ACCENT)

    def compute_bob(self):
        if self.state == "jump":
            cycle = self.tick % 26
            half = 13
            phase = cycle if cycle < half else 26 - cycle
            return -int(phase / half * 28)
        return 1 if (self.tick // 8) % 2 == 0 else 0

    def draw(self):
        self.canvas.delete("all")

        if self.state == "nap":
            self.draw_nap()
            return

        bob = self.compute_bob()

        self.px(BODY_COL, BODY_ROW + bob, BODY, gw=BODY_W, gh=BODY_H)
        self.px(0, ARM_ROW + bob, BODY, gw=ARM_W, gh=ARM_H)
        self.px(GW_BODY - ARM_W, ARM_ROW + bob, BODY, gw=ARM_W, gh=ARM_H)
        for col in LEG_COLS:
            self.px(col, LEG_ROW + bob, BODY, gw=LEG_W, gh=LEG_H)

        if self.state == "look_around":
            phase = (self.tick // 15) % 2
            glyph = LOOK_LEFT if phase == 0 else LOOK_RIGHT
            for col in EYE_COLS:
                self.draw_glyph(col, EYE_ROW + bob, glyph, EYE)
            mark = QUESTION_GLYPH if phase == 0 else EXCLAIM_GLYPH
            self.draw_glyph(43, TOP_MARGIN - 8, mark, EYE)
        else:
            left_glyph, right_glyph, decor = EXPRESSIONS[self.state]
            for col, glyph in zip(EYE_COLS, (left_glyph, right_glyph)):
                self.draw_glyph(col, EYE_ROW + bob, glyph, EYE)
            self.draw_decoration(decor, bob)

    def animate(self):
        self.tick += 1
        self.draw()
        self.root.after(120, self.animate)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    DesktopBuddy().run()
