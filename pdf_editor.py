import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk,ImageDraw
import tkinter as tk
import fitz
import os
import win32clipboard
import win32con
import struct
import time
class PDFRedactorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF editor")

        self.scale = 1.0
        self.min_scale = 0.5
        self.max_scale = 3.0

        self.center_window(650, 800)

        self.toolbar = tk.Frame(root)
        self.toolbar.pack(fill="x")

        tk.Button(self.toolbar, text="Open File", command=self.open_file_dialog).pack(side="left")
        tk.Button(self.toolbar, text="Save File", command=self.save_pdf).pack(side="left")
        tk.Button(self.toolbar, text="Copy File", command=self.copy_pdf_file_to_clipboard).pack(side="left")

        self.canvas = tk.Canvas(root, bg="gray", cursor="cross")

        self.v_scrollbar = tk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.h_scrollbar = tk.Scrollbar(root, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)

        self.current_fill_color = "white"
        self.pipette_mode = False

        tk.Button(self.toolbar, text="Pipette", command=self.activate_pipette).pack(side="left")
        tk.Button(self.toolbar, text="Reset color", command=self.reset_fill_color).pack(side="left")

        self.v_scrollbar.pack(side="right", fill="y")
        self.h_scrollbar.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True)

        # self.canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind_all("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind_all("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind_all("<ButtonRelease-1>", self.on_mouse_up)

        self.root.bind_all("<Control-v>", self.paste_from_clipboard)
        self.root.bind_all("<Command-v>", self.paste_from_clipboard)

        self.root.bind_all("<Key>", self.on_key_press)
        self.root.bind_all("<MouseWheel>", self.on_mouse_wheel_global)
        self.canvas.bind_all("<ButtonPress-3>", self.on_right_mouse_down)
        self.canvas.bind_all("<B3-Motion>", self.on_right_mouse_drag)

        self.canvas_images = []
        self.image_tks = []
        self.page_images = []
        self.page_rects = {}
        self.current_rect = None
        self.rect_start = None
        self.current_page = None
        self.doc = None
        self.image_mode = False
        

    def activate_pipette(self):
        self.pipette_mode = True
        self.canvas.config(cursor="dot")  

    def reset_fill_color(self):
        self.current_fill_color = "white"
        self.pipette_mode = False
        self.canvas.config(cursor="cross")

    def center_window(self, width, height):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def on_key_press(self, event):
        is_ctrl = event.state & 0x4       
        is_cmd = event.state & 0x10      
        
        keycode = event.keycode
        key = event.keysym.lower()

        if (is_ctrl or is_cmd) and (keycode == 90 or key in ['z', 'я']):
            self.undo_last_rect()
        elif (is_ctrl or is_cmd) and (keycode == 86 or key in ['v', 'м']):
            self.paste_from_clipboard()
        elif (is_ctrl or is_cmd) and (keycode == 67 or key in ['c', 'с']):
            self.copy_pdf_file_to_clipboard()

    def on_right_mouse_down(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def on_right_mouse_drag(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def open_file_dialog(self):
        self.canvas.delete("all")
        self.canvas_images.clear()
        self.image_tks.clear()
        self.page_images.clear()
        self.page_rects.clear()
        self.current_rect = None
        self.rect_start = None
        self.current_page = None
        self.doc = None
        self.image_mode = False

        filepath = filedialog.askopenfilename(filetypes=[
            ("Supported files", "*.pdf;*.png;*.jpg;*.jpeg;*.jfif"),
            ("PDF files", "*.pdf"),
            ("Image files", "*.png;*.jpg;*.jpeg;*.jfif")
        ])
        if not filepath:
            return

        ext = filepath.lower().split('.')[-1]
        if ext == 'pdf':
            self.filepath = filepath
            self.render_pdf()
        elif ext in ('png', 'jpg', 'jpeg', 'jfif'):
            self.open_image_dialog(filepath)
        else:
            tk.messagebox.showerror("Unsupported file", "Only PDF and image files are supported.")


    def render_pdf(self):
        if not hasattr(self, "filepath"):
            return

        self.doc = fitz.open(self.filepath)
        self.canvas.delete("all")
        self.canvas_images.clear()
        self.image_tks.clear()
        self.page_images.clear()
        self.current_rect = None
        self.rect_start = None
        self.current_page = None

        y_offset = 10
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.page_images.append(pix)
            img_tk = ImageTk.PhotoImage(img)
            self.image_tks.append(img_tk)
            image_id = self.canvas.create_image(10, y_offset, anchor="nw", image=img_tk, tags=f"page_{page_num}")
            self.canvas_images.append((page_num, image_id))
            self.draw_rects_for_page(page_num)

            y_offset += pix.height + 20

        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def get_page_from_y(self, y):
        for page_num, image_id in self.canvas_images:
            bbox = self.canvas.bbox(image_id)
            if bbox and bbox[1] <= y <= bbox[3]:
                return page_num, bbox
        return None, None

    def on_mouse_wheel_global(self, event):
        if event.state & 0x0004:  
            direction = 1 if event.delta > 0 else -1
            new_scale = self.scale + direction * 0.1
            new_scale = max(self.min_scale, min(self.max_scale, new_scale))
            if new_scale != self.scale:
                self.scale = new_scale
                if self.image_mode:
                    self.open_image_dialog(self.filepath)
                else:
                    self.render_pdf()
        else:
            self.on_mouse_wheel(event)

    def open_image_dialog(self, filepath):
        if not filepath:
            return

        self.doc = None  
        self.image_mode = True
        self.canvas.delete("all")
        self.canvas_images.clear()
        self.image_tks.clear()
        if 0 not in self.page_rects:
            self.page_rects[0] = []
        self.current_rect = None
        self.rect_start = None
        self.current_page = 0  
        self.filepath = filepath

        img = Image.open(filepath).convert("RGB")
        width, height = img.size
        scaled_size = (int(width * self.scale), int(height * self.scale))
        img_resized = img.resize(scaled_size, Image.Resampling.LANCZOS)

        self.loaded_image = img  
        img_tk = ImageTk.PhotoImage(img_resized)
        self.image_tks.append(img_tk)
        image_id = self.canvas.create_image(10, 10, anchor="nw", image=img_tk, tags="image")
        self.canvas_images.append((0, image_id))
        existing_rects = self.page_rects.get(0, [])
        self.page_rects[0] = existing_rects

        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self.draw_rects_for_page(0)


    def on_mouse_down(self, event):
        y = self.canvas.canvasy(event.y)
        x = self.canvas.canvasx(event.x)

        if self.pipette_mode and self.image_mode:
            image = self.loaded_image
            bbox = self.canvas.bbox("image")
            if not bbox:
                return
            img_x = int((x - bbox[0]) / self.scale)
            img_y = int((y - bbox[1]) / self.scale)
            if 0 <= img_x < image.width and 0 <= img_y < image.height:
                pixel = image.getpixel((img_x, img_y))
                self.current_fill_color = '#%02x%02x%02x' % pixel
                print("Цвет выбран:", self.current_fill_color)
            self.pipette_mode = False
            self.canvas.config(cursor="cross")
            return

        page_num, bbox = self.get_page_from_y(y)
        if page_num is None:
            return
        self.current_page = page_num
        self.rect_start = (x, y)
        self.current_rect = self.canvas.create_rectangle(x, y, x, y, outline="red", width=2)

    def on_mouse_drag(self, event):
        if self.rect_start:
            x0, y0 = self.rect_start
            x1 = self.canvas.canvasx(event.x)
            y1 = self.canvas.canvasy(event.y)
            self.canvas.coords(self.current_rect, x0, y0, x1, y1)

    def on_mouse_up(self, event):
        if not self.current_rect or self.current_page is None:
            return
        coords = self.canvas.coords(self.current_rect)
        if abs(coords[2] - coords[0]) < 5 or abs(coords[3] - coords[1]) < 5:
            self.canvas.delete(self.current_rect)
        else:
            page_num = self.current_page
            x0, y0, x1, y1 = coords
            x0, x1 = sorted([x0, x1])
            y0, y1 = sorted([y0, y1])
            if self.image_mode:
                bbox = self.canvas.bbox("image")
            else:
                bbox = self.canvas.bbox(f"page_{page_num}")

            if not bbox:
                print("WARNING: bbox not found.")
                return

            logical_coords = (
                (x0 - bbox[0]) / self.scale,
                (y0 - bbox[1]) / self.scale,
                (x1 - bbox[0]) / self.scale,
                (y1 - bbox[1]) / self.scale
            )
            print(f"Saved rect (logical coords): x0={logical_coords[0]}, y0={logical_coords[1]}, x1={logical_coords[2]}, y1={logical_coords[3]}")
            self.page_rects.setdefault(page_num, []).append(logical_coords)
            self.canvas.delete(self.current_rect) 
            self.draw_rects_for_page(page_num) 
        self.current_rect = None
        self.rect_start = None

    def undo_last_rect(self, event=None):
        if self.image_mode:
            if self.page_rects.get(0):
                self.page_rects[0].pop()
                self.draw_rects_for_page(0)
        elif self.doc:
            for page_num in reversed(range(len(self.doc))):
                rects = self.page_rects.get(page_num, [])
                if rects:
                    rects.pop()
                    self.draw_rects_for_page(page_num)
                    break

    def draw_rects_for_page(self, page_num):
        self.canvas.delete(f"rect_page_{page_num}")
        
        if self.image_mode:
            bbox = self.canvas.bbox("image")
        else:
            bbox = self.canvas.bbox(f"page_{page_num}")
        if not bbox:
            return
        offset_x, offset_y = bbox[0], bbox[1]

        for rect in self.page_rects.get(page_num, []):
            x0, y0, x1, y1 = rect
            
            x0 = x0 * self.scale + offset_x
            y0 = y0 * self.scale + offset_y
            x1 = x1 * self.scale + offset_x
            y1 = y1 * self.scale + offset_y
            print(f"Drawn rect: x0={x0}, y0={y0}, x1={x1}, y1={y1}")
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=self.current_fill_color, outline="", tags=f"rect_page_{page_num}")


    def on_mouse_wheel(self, event):
        if event.state & 0x0001:  
            self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def save_pdf(self):
        save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not save_path:
            return

        if self.image_mode:
            img = self.loaded_image.copy()
            draw = Image.new("RGB", img.size, self.current_fill_color)
            draw.paste(img)

            for coords in self.page_rects.get(0, []):
                x0, y0, x1, y1 = coords
                x0, x1 = sorted([x0, x1])
                y0, y1 = sorted([y0, y1])
                ImageDraw.Draw(draw).rectangle([x0, y0, x1, y1], fill=self.current_fill_color)

            draw.save(save_path, "PDF")
            return

        if not self.doc:
            return

        for page_num in self.page_rects:
            page = self.doc[page_num]
            for coords in self.page_rects.get(page_num, []): 
                x0, y0, x1, y1 = coords
                rect = fitz.Rect(x0, y0, x1, y1)
                page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()
        self.doc.save(save_path)

    def copy_pdf_file_to_clipboard(self):
        base, ext = os.path.splitext(self.filepath)
        temp_path = base + "_updated.pdf"

        if self.image_mode:
            img = self.loaded_image.copy()
            draw = Image.new("RGB", img.size, self.current_fill_color)
            draw.paste(img)

            for coords in self.page_rects.get(0, []):
                x0, y0, x1, y1 = coords
                x0, x1 = sorted([x0, x1])
                y0, y1 = sorted([y0, y1])
                ImageDraw.Draw(draw).rectangle([x0, y0, x1, y1], fill=self.current_fill_color)

            draw.save(temp_path, "PDF")
        else:
            if not self.doc:
                return
            temp_doc = fitz.open(self.filepath)  
            for page_num in self.page_rects:
                page = temp_doc[page_num]
                for coords in self.page_rects.get(page_num, []): 
                    x0, y0, x1, y1 = coords
                    rect = fitz.Rect(x0, y0, x1, y1)
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                page.apply_redactions()
            temp_doc.save(temp_path)

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        dropfiles = struct.pack('IHHHHI', 20, 0, 0, 0, 0, 0)
        filepath_bytes = (temp_path + '\0\0').encode('utf-16le')
        data = dropfiles + filepath_bytes
        win32clipboard.SetClipboardData(win32con.CF_HDROP, data)
        win32clipboard.CloseClipboard()
    
    def paste_from_clipboard(self, event=None):
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                files = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                if files:
                    filepath = files[0]
                    ext = filepath.lower().split('.')[-1]
                    if ext == 'pdf':
                        self.open_file_from_path(filepath)
                    elif ext in ('png', 'jpg', 'jpeg', 'jfif'):
                        self.open_image_dialog(filepath)
                    else:
                        tk.messagebox.showerror("Unsupported file", "Only PDF and image files are supported.")
            win32clipboard.CloseClipboard()
        except Exception as e:
            win32clipboard.CloseClipboard()
            tk.messagebox.showerror("Clipboard Error", f"Could not read clipboard content.\n{str(e)}")
   
    def open_file_from_path(self, filepath):
        self.canvas.delete("all")
        self.canvas_images.clear()
        self.image_tks.clear()
        self.page_images.clear()
        self.page_rects.clear()
        self.current_rect = None
        self.rect_start = None
        self.current_page = None
        self.doc = None
        self.image_mode = False

        self.filepath = filepath

        ext = filepath.lower().split('.')[-1]
        if ext == 'pdf':
            self.render_pdf()
        elif ext in ('png', 'jpg', 'jpeg', 'jfif'):
            self.open_image_dialog(filepath)

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFRedactorApp(root)
    root.mainloop()
