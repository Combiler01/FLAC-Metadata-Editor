import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, font as tkfont
import os
import io
import sys
from mutagen.flac import FLAC, Picture
from PIL import Image

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

APPLE_RED = "#fa243c"
APPLE_RED_HOVER = "#d91e32"
BG_MAIN = "#1c1c1e"
BG_SIDEBAR = "#242426"
BG_TOPBAR = "#2a2a2d"
TEXT_MUTED = "#a1a1a6"

class FLAC_Editor(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Native OS Title Bar Restored
        self.title("FLAC Editor")
        self.geometry("1400x900")
        self.configure(fg_color=BG_MAIN)
        
        self.all_music_files = []
        self.sidebar_widgets = []
        self.selected_files = []
        
        self.cover_art_path = None
        self.entries = {}
        self.initial_values = {}  
        self.current_file_index = None
        self.track_rows = [] 
        self.toast_frame = None
        self._anim_id = None 

        self.setup_fonts()
        self.setup_layout()
        
        self.create_sidebar()
        self.create_topbar()
        self.create_main_content()

        self.bind("<Return>", self.save_current_file_on_enter)

    def setup_fonts(self):
        available_fonts = tkfont.families()
        preferred_fonts = [
            "SF Pro Display", "SF Pro Text", "SF Pro", 
            ".AppleSystemUIFont", "-apple-system", 
            "Helvetica Neue", "Segoe UI", "Arial"
        ]
        
        self.apple_font = "Arial"
        for font in preferred_fonts:
            if font in available_fonts:
                self.apple_font = font
                break

    def get_font(self, size, weight="normal"):
        return ctk.CTkFont(family=self.apple_font, size=size, weight=weight)

    def setup_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1) 

    # --- Smooth Scrolling Engine ---
    def apply_smooth_scrolling(self, scrollable_frame):
        """Overrides chunky default scrolling with fluid kinematic easing."""
        canvas = scrollable_frame._parent_canvas
        scroll_state = {'target': 0.0, 'animating': False}
        
        def smooth_on_mousewheel(event):
        
            if canvas.yview() == (0.0, 1.0):
                return

            if not scroll_state['animating']:
                scroll_state['target'] = canvas.yview()[0]
            
            # Normalize scroll delta between Windows (120) and Mac (1)
            if sys.platform == "darwin":
                delta = -event.delta * 0.02
            else:
                delta = -(event.delta / 120) * 0.05
                
            scroll_state['target'] = max(0.0, min(1.0, scroll_state['target'] + delta))
            
            if not scroll_state['animating']:
                scroll_state['animating'] = True
                animate_scroll()

        def animate_scroll():
            current = canvas.yview()[0]
            diff = scroll_state['target'] - current
            
            # Easing loop
            if abs(diff) > 0.001:
                canvas.yview_moveto(current + (diff * 0.2))
                self.after(16, animate_scroll)
            else:
                canvas.yview_moveto(scroll_state['target'])
                scroll_state['animating'] = False
                
        # Bind the smooth scroll to the canvas
        canvas.bind("<MouseWheel>", smooth_on_mousewheel)

    # --- Sidebar & Content ---

    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, corner_radius=0, width=350)
        # Shifted back up to Row 0 since the custom title bar is gone
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew") 
        self.sidebar.grid_propagate(False)

        brand_label = ctk.CTkLabel(self.sidebar, text="Library", font=self.get_font(size=24, weight="bold"), anchor="w")
        brand_label.pack(fill="x", padx=20, pady=(30, 10))

        self.search_entry = ctk.CTkEntry(
            self.sidebar, placeholder_text="Search music...", 
            font=self.get_font(size=16), height=40, fg_color="#1c1c1e", border_width=0
        )
        self.search_entry.pack(fill="x", padx=20, pady=(0, 15))
        self.search_entry.bind("<KeyRelease>", self.filter_sidebar_list)

        self.btn_select_folder = ctk.CTkButton(
            self.sidebar, text="Choose Music Folder", anchor="center", 
            fg_color="#333336", text_color="white", hover_color="#444447",
            font=self.get_font(size=16, weight="bold"), height=40, command=self.select_music_folder
        )
        self.btn_select_folder.pack(fill="x", padx=20, pady=(0, 15))

        self.sidebar_list_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.sidebar_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.apply_smooth_scrolling(self.sidebar_list_frame) # Apply Smooth Scroll

        ctk.CTkFrame(self.sidebar, height=1, fg_color="#333").pack(fill="x", padx=20, pady=5)

        self.btn_save = ctk.CTkButton(
            self.sidebar, text="Batch Save All", height=45,
            fg_color=APPLE_RED, hover_color=APPLE_RED_HOVER,
            font=self.get_font(size=18, weight="bold"), command=self.batch_save_metadata
        )
        self.btn_save.pack(fill="x", padx=20, pady=15)

    def create_topbar(self):
        self.topbar = ctk.CTkFrame(self, height=70, fg_color=BG_TOPBAR, corner_radius=0)
        self.topbar.grid(row=0, column=1, sticky="ew")
        self.topbar.pack_propagate(False)

        self.now_playing_frame = ctk.CTkFrame(self.topbar, fg_color="#1e1e1e", corner_radius=6, width=500, height=48)
        self.now_playing_frame.pack(expand=True, pady=11)
        self.now_playing_frame.pack_propagate(False)
        
        self.lbl_now_playing = ctk.CTkLabel(self.now_playing_frame, text="No File Selected", font=self.get_font(size=16), text_color=TEXT_MUTED)
        self.lbl_now_playing.pack(expand=True)

    def create_main_content(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=1, column=1, sticky="nsew", padx=30, pady=30)
        self.main_container.grid_columnconfigure(1, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        self.album_header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.album_header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        self.album_header_frame.grid_columnconfigure(1, weight=1)

        self.art_container = ctk.CTkFrame(self.album_header_frame, fg_color="transparent")
        self.art_container.grid(row=0, column=0, sticky="n", padx=(0, 30))
        
        self.preview_frame = ctk.CTkFrame(self.art_container, width=280, height=280, corner_radius=8, fg_color="#2a2a2d")
        self.preview_frame.pack()
        self.preview_frame.pack_propagate(False)
        
        self.lbl_art_preview = ctk.CTkLabel(self.preview_frame, text="[No Art]", font=self.get_font(size=18), text_color=TEXT_MUTED)
        self.lbl_art_preview.pack(expand=True, fill="both")

        btn_frame = ctk.CTkFrame(self.art_container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=15)
        
        self.btn_select_art = ctk.CTkButton(btn_frame, text="Add Art", font=self.get_font(size=16, weight="bold"), fg_color=APPLE_RED, hover_color=APPLE_RED_HOVER, width=130, height=35, command=self.select_art)
        self.btn_select_art.pack(side="left")
        
        self.btn_clear_art = ctk.CTkButton(btn_frame, text="Clear Art", font=self.get_font(size=16, weight="bold"), fg_color="#333336", hover_color="#444447", width=130, height=35, command=self.clear_art)
        self.btn_clear_art.pack(side="right")

        self.tag_editor_frame = ctk.CTkScrollableFrame(self.album_header_frame, fg_color="transparent", height=320)
        self.tag_editor_frame.grid(row=0, column=1, sticky="nsew")
        self.apply_smooth_scrolling(self.tag_editor_frame) # Apply Smooth Scroll
        
        lbl_editor_title = ctk.CTkLabel(self.tag_editor_frame, text="Metadata Editor", font=self.get_font(size=32, weight="bold"))
        lbl_editor_title.pack(anchor="w", pady=(0, 10))
        
        self.lbl_editor_hint = ctk.CTkLabel(
            self.tag_editor_frame, 
            text="Press Enter to save current file. Changes auto-save when you click another file.", 
            font=self.get_font(size=15), text_color=TEXT_MUTED, justify="left"
        )
        self.lbl_editor_hint.pack(anchor="w", pady=(0, 15))

        self.tracklist_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.tracklist_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.apply_smooth_scrolling(self.tracklist_frame) # Apply Smooth Scroll
        
        header_frame = ctk.CTkFrame(self.tracklist_frame, fg_color="transparent", height=40)
        header_frame.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(header_frame, text="#", font=self.get_font(size=16), text_color=TEXT_MUTED, width=40, anchor="w").pack(side="left", padx=(10, 0))
        ctk.CTkLabel(header_frame, text="File Name", font=self.get_font(size=16), text_color=TEXT_MUTED, anchor="w").pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkLabel(header_frame, text="Type", font=self.get_font(size=16), text_color=TEXT_MUTED, width=60, anchor="e").pack(side="right", padx=(0, 20))
        
        ctk.CTkFrame(self.tracklist_frame, height=1, fg_color="#333").pack(fill="x", pady=(0, 5))

        self.build_metadata_fields([])

    # --- Folder & Sidebar Logic ---

    def select_music_folder(self):
        folder = filedialog.askdirectory(title="Select Music Folder")
        if folder:
            self.all_music_files.clear()
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith('.flac'):
                        self.all_music_files.append(os.path.join(root, file))
            
            self.all_music_files.sort()
            self.search_entry.delete(0, tk.END)
            self.build_sidebar_list()

    def build_sidebar_list(self):
        for widget in self.sidebar_list_frame.winfo_children():
            widget.destroy()
        self.sidebar_widgets.clear()

        for file_path in self.all_music_files:
            filename = os.path.basename(file_path)
            
            var = tk.BooleanVar(value=(file_path in self.selected_files))
            cb = ctk.CTkCheckBox(
                self.sidebar_list_frame, text=filename, variable=var, 
                font=self.get_font(size=14), fg_color=APPLE_RED, hover_color=APPLE_RED_HOVER,
                command=lambda f=file_path, v=var: self.toggle_sidebar_selection(f, v)
            )
            cb.pack(pady=4, padx=5, anchor="w", fill="x")
            
            self.sidebar_widgets.append((filename, cb))

    def filter_sidebar_list(self, event=None):
        query = self.search_entry.get().lower()
        for filename, cb in self.sidebar_widgets:
            if query in filename.lower():
                cb.pack(pady=4, padx=5, anchor="w", fill="x")
            else:
                cb.pack_forget()

    def toggle_sidebar_selection(self, file_path, var):
        if var.get():
            if file_path not in self.selected_files:
                self.selected_files.append(file_path)
        else:
            if file_path in self.selected_files:
                if self.current_file_index is not None and self.current_file_index < len(self.selected_files):
                    if self.selected_files[self.current_file_index] == file_path:
                        self.process_save(is_auto_save=True)
                        self.current_file_index = None
                        self.clear_art()
                        self.build_metadata_fields([])
                        self.lbl_now_playing.configure(text="No File Selected")
                
                self.selected_files.remove(file_path)
                self.current_file_index = None 

        self.refresh_tracklist()

    # --- Main Content Logic ---

    def build_metadata_fields(self, detected_keys, audio_obj=None):
        for widget in self.tag_editor_frame.winfo_children():
            if isinstance(widget, ctk.CTkFrame): 
                widget.destroy()
                
        self.entries.clear()
        self.initial_values.clear()

        standard_fields = ["title", "artist", "album", "albumartist", "composer", "date", "genre", "tracknumber", "discnumber"]
        all_fields = standard_fields.copy()
        
        for key in detected_keys:
            if key not in all_fields:
                all_fields.append(key)

        for field in all_fields:
            frame = ctk.CTkFrame(self.tag_editor_frame, fg_color="transparent")
            frame.pack(fill="x", pady=6)
            
            is_primary = field in ["title", "artist", "album"]
            text_col = "white" if field == "artist" else "white"
            font_wt = "bold" if is_primary else "normal"
            
            lbl = ctk.CTkLabel(frame, text=field.capitalize(), width=130, anchor="w", text_color=text_col, font=self.get_font(size=18, weight=font_wt))
            lbl.pack(side="left", padx=5)
            
            entry = ctk.CTkEntry(
                frame, font=self.get_font(size=18), 
                fg_color="#2a2a2d", text_color="white", border_width=0, 
                height=35, width=450, placeholder_text=f"Enter {field}..."
            )
            entry.pack(side="left", padx=(5, 20))
            
            if audio_obj and field in audio_obj:
                val = str(audio_obj[field][0])
                entry.insert(0, val)
                self.initial_values[field] = val
            else:
                self.initial_values[field] = ""
                
            self.entries[field] = entry

    # --- Smooth Cascading Render Engine ---

    def refresh_tracklist(self):
        if self._anim_id is not None:
            self.after_cancel(self._anim_id)
            self._anim_id = None

        for row in self.track_rows:
            row.destroy()
        self.track_rows.clear()

        self._render_index = 0
        self._render_next_row()

    def _render_next_row(self):
        if self._render_index < len(self.selected_files):
            i = self._render_index
            file_path = self.selected_files[i]
            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            ext_text = ext.replace('.', '').upper()
            
            row_frame = ctk.CTkFrame(self.tracklist_frame, fg_color="transparent", corner_radius=6, height=45)
            row_frame.pack(fill="x", pady=2)
            row_frame.pack_propagate(False)
            
            lbl_idx = ctk.CTkLabel(row_frame, text=str(i+1), font=self.get_font(size=16), text_color=TEXT_MUTED, width=40, anchor="w")
            lbl_idx.pack(side="left", padx=(10, 0))
            
            lbl_name = ctk.CTkLabel(row_frame, text=name, font=self.get_font(size=18), text_color="white", anchor="w")
            lbl_name.pack(side="left", padx=10, fill="x", expand=True)
            
            lbl_type = ctk.CTkLabel(row_frame, text=ext_text, font=self.get_font(size=14), text_color=TEXT_MUTED, width=60, anchor="e")
            lbl_type.pack(side="right", padx=(0, 20))
            
            for widget in (row_frame, lbl_idx, lbl_name, lbl_type):
                widget.bind("<Enter>", lambda e, r=row_frame, idx=i: self.on_hover_enter(r, idx))
                widget.bind("<Leave>", lambda e, r=row_frame, idx=i: self.on_hover_leave(r, idx))
                widget.bind("<Button-1>", lambda e, idx=i: self.on_file_select(idx))
                
            self.track_rows.append(row_frame)
            
            if self.current_file_index == i:
                self.highlight_row(i)

            self._render_index += 1
            self._anim_id = self.after(15, self._render_next_row)

    def on_hover_enter(self, row_frame, idx):
        if self.current_file_index != idx:
            row_frame.configure(fg_color="#2a2a2d")

    def on_hover_leave(self, row_frame, idx):
        if self.current_file_index != idx:
            row_frame.configure(fg_color="transparent")

    def highlight_row(self, index):
        for i, row in enumerate(self.track_rows):
            if i == index:
                row.configure(fg_color="#3a3a3d") 
            else:
                row.configure(fg_color="transparent")

    def on_file_select(self, index):
        if self.current_file_index is not None and self.current_file_index != index:
            self.process_save(is_auto_save=True)

        self.current_file_index = index
        
        if index < len(self.track_rows):
            self.highlight_row(index)
        
        file_path = self.selected_files[index]
        filename = os.path.basename(file_path)
        name, _ = os.path.splitext(filename)
        
        self.lbl_now_playing.configure(text=name, text_color="white")
        
        try:
            audio = FLAC(file_path)
            file_keys = [k.lower() for k in audio.keys()]
            self.build_metadata_fields(file_keys, audio)
            
            if not self.cover_art_path:
                if audio.pictures:
                    self.update_preview(audio.pictures[0].data)
                else:
                    self.update_preview(None)
                    
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    # --- Automated Saving & Notification ---

    def show_toast(self, message):
        if self.toast_frame:
            try:
                self.toast_frame.destroy()
            except: pass

        self.toast_frame = ctk.CTkFrame(self, fg_color="#333333", corner_radius=20, border_color="#555555", border_width=1)
        self.toast_frame.place(relx=0.5, rely=0.95, anchor="s")
        
        lbl = ctk.CTkLabel(self.toast_frame, text=message, font=self.get_font(size=15, weight="bold"), text_color="white")
        lbl.pack(padx=30, pady=12)
        
        self.after(2500, self.toast_frame.destroy)

    def save_current_file_on_enter(self, event=None):
        self.focus() 
        self.process_save(is_auto_save=False)

    def process_save(self, is_auto_save=False):
        if self.current_file_index is None or self.current_file_index >= len(self.selected_files):
            return

        changed_fields = {}
        for field, entry in self.entries.items():
            current_val = entry.get().strip()
            if current_val != self.initial_values.get(field, ""):
                changed_fields[field] = current_val

        if not changed_fields:
            if not is_auto_save:
                self.show_toast("No changes to save.")
            return

        file_path = self.selected_files[self.current_file_index]
        try:
            audio = FLAC(file_path)
            for field, new_val in changed_fields.items():
                if new_val:
                    audio[field] = new_val
                elif field in audio:
                    del audio[field]
                self.initial_values[field] = new_val

            audio.save()
            filename, _ = os.path.splitext(os.path.basename(file_path))
            
            if is_auto_save:
                self.show_toast(f"✓ Auto-saved text edits: {filename}")
            else:
                self.show_toast(f"✓ Saved: {filename}")
                
        except Exception as e:
            print(f"Failed to save {file_path}: {e}")

    # --- Album Art Logic ---

    def select_art(self):
        path = filedialog.askopenfilename(title="Select Album Art", filetypes=[("Image Files", "*.jpg *.jpeg *.png")])
        if path:
            self.cover_art_path = path
            self.update_preview(path)
            if self.selected_files:
                self.apply_art_to_all_selected()

    def apply_art_to_all_selected(self):
        try:
            image_data = open(self.cover_art_path, "rb").read()
            pic = Picture()
            pic.data = image_data
            pic.type = 3
            pic.mime = "image/png" if self.cover_art_path.lower().endswith(".png") else "image/jpeg"
            pic.desc = "Front Cover"

            success_count = 0
            for file_path in self.selected_files:
                try:
                    audio = FLAC(file_path)
                    audio.clear_pictures()
                    audio.add_picture(pic)
                    audio.save()
                    success_count += 1
                except Exception as e:
                    print(f"Failed to apply art to {file_path}: {e}")
                    
            self.show_toast(f"✓ Album Art embedded into {success_count} files!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image:\n{e}")

    def clear_art(self):
        self.cover_art_path = None
        if self.current_file_index is not None and self.current_file_index < len(self.selected_files):
            self.on_file_select(self.current_file_index)
        else:
            self.update_preview(None)

    def update_preview(self, image_source):
        try:
            if image_source is None:
                self.lbl_art_preview.configure(image='', text="[No Art]")
                return

            if isinstance(image_source, str):
                img = Image.open(image_source)
            else:
                img = Image.open(io.BytesIO(image_source))

            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(280, 280))
            self.lbl_art_preview.configure(image=ctk_img, text="")
            
        except Exception:
            self.lbl_art_preview.configure(image='', text="[Preview Error]")

    def batch_save_metadata(self):
        if not self.selected_files:
            messagebox.showwarning("Warning", "No files selected in the Library.")
            return

        changed_fields = {}
        for field, entry in self.entries.items():
            current_val = entry.get().strip()
            if current_val != self.initial_values.get(field, ""):
                changed_fields[field] = current_val

        if not changed_fields:
            self.show_toast("No text edits to batch save.")
            return

        success_count = 0
        current_file_path = self.selected_files[self.current_file_index] if self.current_file_index is not None else None

        for file_path in self.selected_files:
            try:
                audio = FLAC(file_path)
                file_modified = False
                is_current_file = (file_path == current_file_path)

                for field, new_val in changed_fields.items():
                    if field in ["title", "tracknumber"] and not is_current_file:
                        continue
                    
                    if new_val:
                        audio[field] = new_val
                    elif field in audio:
                        del audio[field]
                    file_modified = True

                if file_modified:
                    audio.save()
                    success_count += 1

            except Exception as e:
                print(f"Batch fail on {file_path}: {e}")

        self.show_toast(f"✓ Batch saved text edits to {success_count} file(s)!")
        
        if self.current_file_index is not None:
            self.on_file_select(self.current_file_index) 

if __name__ == "__main__":
    app = FLAC_Editor()
    app.mainloop()