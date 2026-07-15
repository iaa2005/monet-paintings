#!/usr/bin/env python3
"""GUI-редактор для ручного выделения аватарок на картинах Моне."""

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import cv2

DIR = os.path.expanduser("~/Desktop/paintings")
ARTWORKS_DIR = os.path.join(DIR, "artworks")
AVATARS_DIR = os.path.join(DIR, "avatars")
JSON_PATH = os.path.join(AVATARS_DIR, "avatars.json")
PAINTINGS_JSON = os.path.join(DIR, "monet_paintings.json")
IMG_MAX = 900
HANDLE_SIZE = 6
MIN_BBOX = 10


def load_avatars():
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_avatars(data):
    os.makedirs(AVATARS_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_paintings():
    with open(PAINTINGS_JSON, encoding="utf-8") as f:
        return json.load(f)


class BBox:
    def __init__(self, x, y, w, h, avatar_data=None):
        self.x, self.y = x, y
        self.w, self.h = w, h
        self.data = avatar_data or {}
        self.selected = False

    @property
    def handles(self):
        return {
            "tl": (self.x, self.y),
            "tr": (self.x + self.w, self.y),
            "bl": (self.x, self.y + self.h),
            "br": (self.x + self.w, self.y + self.h),
        }

    def move(self, dx, dy, img_w, img_h):
        self.x += dx
        self.y += dy

    def resize_corner(self, corner, new_x, new_y, img_w, img_h):
        old_cx, old_cy = self.x + self.w / 2, self.y + self.h / 2
        if "l" in corner:
            self.w = max(MIN_BBOX, self.x + self.w - new_x)
            self.x = new_x
        if "r" in corner:
            self.w = max(MIN_BBOX, new_x - self.x)
        if "t" in corner:
            self.h = max(MIN_BBOX, self.y + self.h - new_y)
            self.y = new_y
        if "b" in corner:
            self.h = max(MIN_BBOX, new_y - self.y)
        # Keep square
        side = max(self.w, self.h)
        self.w = self.h = side
        new_cx, new_cy = self.x + side / 2, self.y + side / 2
        self.x += old_cx - new_cx
        self.y += old_cy - new_cy

    def contains(self, px, py, margin=0):
        return self.x - margin <= px <= self.x + self.w + margin and self.y - margin <= py <= self.y + self.h + margin

    def handle_at(self, px, py):
        for name, (hx, hy) in self.handles.items():
            if abs(px - hx) <= HANDLE_SIZE + 4 and abs(py - hy) <= HANDLE_SIZE + 4:
                return name
        return None


class EditorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Monet Avatar Editor")
        self.root.geometry("1400x900")

        self.paintings = load_paintings()
        self.idx = 0
        self.bboxes = []
        self.all_avatars = load_avatars()
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drag_mode = None
        self.drag_handle = None
        self.drag_start = None
        self.cv_img = None

        self._build_ui()
        self._load_painting()

    def _build_ui(self):
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text="\u25c0 Prev", command=self._prev).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Next \u25b6", command=self._next).pack(side=tk.LEFT, padx=2)

        ttk.Label(toolbar, text=" Go:").pack(side=tk.LEFT, padx=(10, 2))
        self.jump_var = tk.StringVar()
        self.jump_entry = ttk.Entry(toolbar, textvariable=self.jump_var, width=6)
        self.jump_entry.pack(side=tk.LEFT)
        self.jump_entry.bind("<Return>", lambda e: self._jump())
        ttk.Button(toolbar, text="Go", command=self._jump, width=3).pack(side=tk.LEFT)

        self.info_label = ttk.Label(toolbar, text="", width=50)
        self.info_label.pack(side=tk.LEFT, padx=10)

        self.gender_var = tk.StringVar(value="unknown")
        ttk.Label(toolbar, text="Gender:").pack(side=tk.LEFT, padx=(20, 2))
        ttk.Radiobutton(toolbar, text="Male", variable=self.gender_var, value="male", command=self._on_gender_change).pack(side=tk.LEFT)
        ttk.Radiobutton(toolbar, text="Female", variable=self.gender_var, value="female", command=self._on_gender_change).pack(side=tk.LEFT)
        ttk.Radiobutton(toolbar, text="Unknown", variable=self.gender_var, value="unknown", command=self._on_gender_change).pack(side=tk.LEFT)

        ttk.Button(toolbar, text="\u2715 Delete", command=self._delete_selected).pack(side=tk.LEFT, padx=(20, 2))
        ttk.Label(toolbar, text=" | ").pack(side=tk.LEFT)
        ttk.Button(toolbar, text="\u25b2", width=2, command=lambda: self._nudge(0, -1)).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="\u25bc", width=2, command=lambda: self._nudge(0, 1)).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="\u25c0", width=2, command=lambda: self._nudge(-1, 0)).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="\u25b6", width=2, command=lambda: self._nudge(1, 0)).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="\U0001f4be Save All", command=self._save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="Gallery", command=self._gallery).pack(side=tk.RIGHT, padx=5)
        self.status = ttk.Label(toolbar, text="", foreground="gray")
        self.status.pack(side=tk.RIGHT, padx=10)

        self.canvas_frame = ttk.Frame(self.root)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.canvas_frame, bg="#222", cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_down)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_up)
        self.root.bind("<Left>", lambda e: self._prev())
        self.root.bind("<Right>", lambda e: self._next())
        self.root.bind("<Delete>", lambda e: self._delete_selected())
        self.root.bind("<Control-s>", lambda e: self._save())

    def _current_painting(self):
        return self.paintings[self.idx]

    def _load_painting(self):
        p = self._current_painting()
        fpath = os.path.join(ARTWORKS_DIR, os.path.basename(p["filename"]))
        if not os.path.exists(fpath):
            fpath = os.path.join(DIR, p["filename"])

        self.cv_img = cv2.imread(fpath)
        if self.cv_img is None:
            return
        self.cv_img = cv2.cvtColor(self.cv_img, cv2.COLOR_BGR2RGB)

        h, w = self.cv_img.shape[:2]
        self.scale = IMG_MAX / max(w, h)
        self.offset_x = max(0, (self.canvas.winfo_width() - w * self.scale) / 2) if self.canvas.winfo_width() > 1 else 0
        self.offset_y = 0

        self._load_bboxes_for_current()
        self._update_info()
        self._redraw()

    def _load_bboxes_for_current(self):
        p = self._current_painting()
        src = p["filename"]
        self.bboxes = []
        for a in self.all_avatars:
            if a.get("source", "") == src or a.get("source", "").endswith(os.path.basename(src)):
                bb = a.get("bbox", {})
                self.bboxes.append(BBox(bb.get("x", 0), bb.get("y", 0),
                                        bb.get("w", 0), bb.get("h", 0), a))

    def _redraw(self):
        if self.cv_img is None:
            return
        h, w = self.cv_img.shape[:2]
        nw, nh = int(w * self.scale), int(h * self.scale)
        pil_img = Image.fromarray(self.cv_img).resize((nw, nh), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(pil_img)
        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self._tk_img)
        self._draw_bboxes()

    def _draw_bboxes(self):
        h, w = self.cv_img.shape[:2]
        cw = w * self.scale
        ch = h * self.scale
        for b in self.bboxes:
            # Visual coords clamped to canvas
            vsx = self.offset_x + max(-10, b.x) * self.scale
            vsy = self.offset_y + max(-10, b.y) * self.scale
            vex = self.offset_x + min(w + 10, b.x + b.w) * self.scale
            vey = self.offset_y + min(h + 10, b.y + b.h) * self.scale
            sx = self.offset_x + b.x * self.scale
            sy = self.offset_y + b.y * self.scale
            ex = sx + b.w * self.scale
            ey = sy + b.h * self.scale
            g = b.data.get("gender", "unknown")
            if b.selected:
                color, width = "#00ff00", 3
            elif g == "male":
                color, width = "#4488ff", 2
            elif g == "female":
                color, width = "#ff88aa", 2
            else:
                color, width = "#ff4444", 2
            self.canvas.create_rectangle(vsx, vsy, vex, vey, outline=color, width=width, tags="bbox")
            # Draw dashed line to show actual position if outside
            if b.x < 0 or b.y < 0 or b.x + b.w > w or b.y + b.h > h:
                self.canvas.create_rectangle(vsx, vsy, vex, vey, outline=color, width=1, dash=(2, 4), tags="bbox")
            g = b.data.get("gender", "unknown")
            label = {"male": "M", "female": "F"}.get(g, "?")
            self.canvas.create_text(vsx + 2, vsy + 2, text=label, anchor=tk.NW,
                                    fill=color, font=("Arial", 9, "bold"), tags="bbox")
            if b.selected:
                for h_name, (hx, hy) in b.handles.items():
                    vhx = max(0, min(cw, self.offset_x + hx * self.scale))
                    vhy = max(0, min(ch, self.offset_y + hy * self.scale))
                    cx = self.offset_x + hx * self.scale
                    cy = self.offset_y + hy * self.scale
                    self.canvas.create_rectangle(vhx - HANDLE_SIZE, vhy - HANDLE_SIZE,
                                                 vhx + HANDLE_SIZE, vhy + HANDLE_SIZE,
                                                 fill=color, outline="white", tags="bbox")

    def _update_info(self):
        p = self._current_painting()
        self.info_label.config(
            text=f"{self.idx+1}/{len(self.paintings)}  {p['title']} ({p.get('year','')})  |  BBoxes: {len(self.bboxes)}")
        self.root.title(f"Monet Avatar Editor — {p['title']}")

    def _next(self):
        if self.idx < len(self.paintings) - 1:
            self._auto_save()
            self.idx += 1
            self._load_painting()

    def _prev(self):
        if self.idx > 0:
            self._auto_save()
            self.idx -= 1
            self._load_painting()

    def _jump(self):
        try:
            n = int(self.jump_var.get()) - 1
            if 0 <= n < len(self.paintings):
                self._auto_save()
                self.idx = n
                self._load_painting()
        except ValueError:
            pass

    def _auto_save(self):
        """Save avatars and JSON for current painting."""
        if not self.bboxes:
            return
        self._do_save()
        self.status.config(text="Auto-saved")

    def _to_img(self, cx, cy):
        x = (cx - self.offset_x) / self.scale
        y = (cy - self.offset_y) / self.scale
        h, w = self.cv_img.shape[:2]
        return max(0, min(w, x)), max(0, min(h, y))

    def _on_down(self, event):
        cx, cy = event.x, event.y
        # Check handles on selected bbox (use raw coords for out-of-bounds)
        for b in self.bboxes:
            if b.selected:
                # Use unclamped image coords for handle detection
                rx = (cx - self.offset_x) / self.scale
                ry = (cy - self.offset_y) / self.scale
                hname = b.handle_at(rx, ry)
                if hname:
                    self.drag_mode = "resize"
                    self.drag_handle = (b, hname)
                    return

        # Check bbox hit (use unclamped coords so out-of-bounds bboxes are hittable)
        for b in reversed(self.bboxes):
            rx = (cx - self.offset_x) / self.scale
            ry = (cy - self.offset_y) / self.scale
            ix, iy = self._to_img(cx, cy)
            if b.contains(rx, ry, margin=6) or b.contains(ix, iy, margin=6):
                for bb in self.bboxes:
                    bb.selected = False
                b.selected = True
                self.drag_mode = "move"
                self.drag_handle = b
                self.drag_start = (ix - b.x, iy - b.y)
                self.gender_var.set(b.data.get("gender", "unknown"))
                self._redraw()
                return

        for b in self.bboxes:
            b.selected = False
        self.drag_mode = "draw"
        self.drag_start = self._to_img(cx, cy)
        self._redraw()

    def _on_drag(self, event):
        ix, iy = self._to_img(event.x, event.y)
        h, w = self.cv_img.shape[:2]

        if self.drag_mode == "move":
            b = self.drag_handle
            dx = ix - b.x - self.drag_start[0]
            dy = iy - b.y - self.drag_start[1]
            b.move(dx, dy, w, h)
            self._redraw()
        elif self.drag_mode == "resize":
            b, hname = self.drag_handle
            b.resize_corner(hname, ix, iy, w, h)
            self._redraw()
        elif self.drag_mode == "draw":
            sx, sy = self.drag_start
            side = max(abs(ix - sx), abs(iy - sy))
            x1 = sx if ix >= sx else sx - side
            y1 = sy if iy >= sy else sy - side
            x2, y2 = x1 + side, y1 + side
            self._redraw()
            csx = self.offset_x + x1 * self.scale
            csy = self.offset_y + y1 * self.scale
            cex = self.offset_x + x2 * self.scale
            cey = self.offset_y + y2 * self.scale
            self.canvas.create_rectangle(csx, csy, cex, cey, outline="#ffff00",
                                         width=2, dash=(4, 2), tags="draw")
            self.status.config(text=f"Drawing: {x2-x1}x{y2-y1}px")

    def _on_up(self, event):
        if self.drag_mode == "draw" and self.drag_start:
            ix, iy = self._to_img(event.x, event.y)
            sx, sy = self.drag_start
            side = max(abs(ix - sx), abs(iy - sy))
            x1 = sx if ix >= sx else sx - side
            y1 = sy if iy >= sy else sy - side
            x2, y2 = x1 + side, y1 + side
            rw, rh = x2 - x1, y2 - y1
            if rw >= MIN_BBOX and rh >= MIN_BBOX:
                b = BBox(x1, y1, rw, rh, {
                    "gender": self.gender_var.get(),
                    "title": self._current_painting()["title"],
                    "year": self._current_painting().get("year", ""),
                    "source": self._current_painting()["filename"],
                })
                b.selected = True
                for bb in self.bboxes:
                    bb.selected = False
                self.bboxes.append(b)
                self.gender_var.set(b.data.get("gender", "unknown"))
                self.status.config(text=f"BBox added: {rw}x{rh}px")
        self.drag_mode = None
        self.drag_handle = None
        self.drag_start = None
        self._redraw()

    def _on_gender_change(self):
        for b in self.bboxes:
            if b.selected:
                b.data['gender'] = self.gender_var.get()

    def _nudge(self, dx, dy):
        selected = [b for b in self.bboxes if b.selected]
        if not selected:
            self.status.config(text='Select a bbox first')
            return
        h, w = self.cv_img.shape[:2]
        for b in selected:
            b.move(dx, dy, w, h)
        self._redraw()

    def _delete_selected(self):
        self.bboxes = [b for b in self.bboxes if not b.selected]
        self._do_save()
        self._redraw()
        self.status.config(text="Deleted")

    def _do_save(self):
        p = self._current_painting()
        basename = os.path.basename(p["filename"])
        # Remove old
        self.all_avatars = [a for a in self.all_avatars
                            if not (a.get("source","") == p["filename"] or a.get("source","").endswith(basename))]
        # Remove old avatar files
        base = os.path.splitext(basename)[0]
        for f in os.listdir(AVATARS_DIR):
            if f.startswith(base + "_face") and f.endswith(".jpg"):
                os.remove(os.path.join(AVATARS_DIR, f))

        h, w = self.cv_img.shape[:2]
        for i, b in enumerate(self.bboxes):
            aname = f"{base}_face{i+1}.jpg"
            side = b.w  # bbox is already square, no padding
            half = side // 2
            cx, cy = b.x + b.w // 2, b.y + b.h // 2
            x1 = max(0, cx - half)
            y1 = max(0, cy - half)
            x2 = min(w, x1 + side)
            y2 = min(h, y1 + side)
            x1 = max(0, x2 - side)
            y1 = max(0, y2 - side)
            crop = cv2.cvtColor(self.cv_img[int(y1):int(y2), int(x1):int(x2)], cv2.COLOR_RGB2BGR)
            crop = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_LANCZOS4)
            cv2.imwrite(os.path.join(AVATARS_DIR, aname), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])

            self.all_avatars.append({
                "filename": aname,
                "source": p["filename"],
                "gender": b.data.get("gender", "unknown"),
                "title": p.get("title", ""),
                "year": p.get("year", ""),
                "confidence": 1.0,
                "bbox": {"x": int(b.x), "y": int(b.y), "w": int(b.w), "h": int(b.h)}
            })

        save_avatars(self.all_avatars)

    def _save(self):
        self._do_save()
        self.status.config(text=f"Saved {len(self.bboxes)} avatars")


    def _gallery(self):
        self._auto_save()
        gallery = tk.Toplevel(self.root)
        gallery.title("All Avatars")
        gallery.geometry("1000x700")

        colors = {"male": "#4488ff", "female": "#ff88aa", "unknown": "#ff4444"}

        canvas = tk.Canvas(gallery, bg="#f0f0f0")
        scrollbar = ttk.Scrollbar(gallery, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        gallery.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        groups = {}
        for a in self.all_avatars:
            src = a.get("source", "")
            groups.setdefault(src, []).append(a)

        for src, avatars in groups.items():
            pidx = None
            for i, p in enumerate(self.paintings):
                if p["filename"] == src:
                    pidx = i
                    break
            title = next((p["title"] for p in self.paintings if p["filename"] == src), src)

            header = ttk.Frame(scroll_frame)
            header.pack(fill=tk.X, padx=10, pady=(15, 5))
            tk.Label(header, text=title, font=("Arial", 11, "bold"), fg="#000000").pack(side=tk.LEFT)
            if pidx is not None:
                btn = ttk.Button(header, text=f"Edit (#{pidx+1})",
                                 command=lambda n=pidx: self._jump_to(n, gallery))
                btn.pack(side=tk.LEFT, padx=10)

            gallery.update_idletasks()
            gw = gallery.winfo_width()
            imgs_per_row = max(1, (gw - 40) // 114) if gw > 100 else 8
            row = tk.Frame(scroll_frame, bg="#f0f0f0")
            row.pack(fill=tk.X, padx=10)
            col = 0

            for a in avatars:
                if col >= imgs_per_row:
                    row = tk.Frame(scroll_frame, bg="#f0f0f0")
                    row.pack(fill=tk.X, padx=10)
                    col = 0
                fname = a.get("filename", "")
                fpath = os.path.join(AVATARS_DIR, fname)
                if os.path.exists(fpath):
                    img = Image.open(fpath)
                    img = img.resize((100, 100), Image.LANCZOS)
                    g = a.get("gender", "unknown")
                    border_color = colors.get(g, "#ff4444")
                    bordered = Image.new("RGB", (108, 108), border_color)
                    bordered.paste(img, (4, 4))
                    photo = ImageTk.PhotoImage(bordered)
                    lbl = tk.Label(row, image=photo, bg="#f0f0f0")
                    lbl.image = photo
                    lbl.pack(side=tk.LEFT, padx=3, pady=3)
                    col += 1

    def _jump_to(self, n, gallery=None):
        if gallery:
            gallery.destroy()
        self._auto_save()
        self.idx = n
        self._load_painting()

if __name__ == "__main__":
    app = EditorApp()
    app.root.mainloop()
