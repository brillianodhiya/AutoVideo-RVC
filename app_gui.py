import os
import sys
import json
import glob
import asyncio
import requests
import proglog
# pyrefly: ignore [missing-import]
from PySide6.QtCore import Qt, QThread, Signal, QObject, QSize
# pyrefly: ignore [missing-import]
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QSpinBox, QDoubleSpinBox, 
    QSlider, QComboBox, QFileDialog, QMessageBox, QProgressBar, 
    QHeaderView, QFrame, QSplitter, QGroupBox, QStackedWidget,
    QDialog, QDialogButtonBox, QCheckBox
)
# pyrefly: ignore [missing-import]
from PySide6.QtGui import QIcon, QFont, QColor

import app_style
import ai_generator

# ==========================================
# 0. PREMIUM SCRIPT TEXT EDITOR DIALOG (MODAL)
# ==========================================
class ScriptEditDialog(QDialog):
    def __init__(self, parent=None, title_text="Sunting Naskah Video", initial_text="", show_duration=True):
        super().__init__(parent)
        self.setWindowTitle(title_text)
        self.resize(550, 350)
        self.show_duration = show_duration
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        title_lbl = QLabel(title_text)
        title_lbl.setObjectName("section_title")
        layout.addWidget(title_lbl)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(initial_text)
        self.text_edit.setPlaceholderText("Tulis naskah video Anda di sini...")
        self.text_edit.setStyleSheet("font-size: 13px; line-height: 1.5; padding: 10px; background-color: #09090b;")
        layout.addWidget(self.text_edit)
        
        # Word counter label with optional estimated audio duration
        self.word_lbl = QLabel()
        self.word_lbl.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        self.text_edit.textChanged.connect(self.update_word_count)
        self.update_word_count()
        layout.addWidget(self.word_lbl)
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        # Style buttons inside button box
        self.button_box.button(QDialogButtonBox.Ok).setText("Simpan")
        self.button_box.button(QDialogButtonBox.Ok).setStyleSheet(
            "background-color: #2563eb; border: 1px solid #3b82f6; color: #ffffff; font-weight: bold; padding: 6px 16px; border-radius: 6px;"
        )
        self.button_box.button(QDialogButtonBox.Cancel).setText("Batal")
        self.button_box.button(QDialogButtonBox.Cancel).setStyleSheet(
            "background-color: #18181b; border: 1px solid #27272a; color: #e4e4e7; padding: 6px 16px; border-radius: 6px;"
        )
        layout.addWidget(self.button_box)
        
    def update_word_count(self):
        txt = self.text_edit.toPlainText().strip()
        words = len(txt.split()) if txt else 0
        chars = len(txt)
        if self.show_duration:
            # 0.28 seconds per word at +20% speed on edge-tts
            duration = words * 0.28
            self.word_lbl.setText(f"📊 Panjang: {words} kata | {chars} karakter | Estimasi Durasi Audio: ~{duration:.1f} detik")
        else:
            self.word_lbl.setText(f"📊 Panjang: {words} kata | {chars} karakter")
        
    def get_text(self):
        return self.text_edit.toPlainText()

# ==========================================
# 0.5 MOVIEPY COOPERATIVE STOP LOGGER
# ==========================================
class MoviePyStopLogger(proglog.ProgressBarLogger):
    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        
    def callback(self, *args, **kwargs):
        if self.worker._is_killed:
            raise RuntimeError("Rendering dihentikan oleh pengguna!")
            
    def log(self, *args, **kwargs):
        if self.worker._is_killed:
            raise RuntimeError("Rendering dihentikan oleh pengguna!")
            
    def update_bar(self, *args, **kwargs):
        if self.worker._is_killed:
            raise RuntimeError("Rendering dihentikan oleh pengguna!")
        super().update_bar(*args, **kwargs)

# ==========================================
# 1. THREADED BACKGROUND RENDER WORKER
# ==========================================
class RenderWorker(QThread):
    progress_signal = Signal(int, int) # Current index, Total
    status_signal = Signal(str)
    finished_signal = Signal(bool, str)
    
    def __init__(self, scripts_data, rvc_params, layout_params, workspace_folders):
        super().__init__()
        self.scripts_data = scripts_data
        self.rvc_params = rvc_params
        self.layout_params = layout_params
        self.workspace_folders = workspace_folders
        self._is_killed = False
        self._is_paused = False
        
    def stop(self):
        self._is_killed = True
        
    def pause(self):
        self._is_paused = True
        
    def resume(self):
        self._is_paused = False
        
    def check_paused(self):
        while self._is_paused:
            if self._is_killed:
                break
            self.msleep(100)
        
    def run(self):
        try:
            total_videos = len(self.scripts_data)
            self.status_signal.emit(f"[INFO] Memulai rendering massal sebanyak {total_videos} video...")
            
            # Dinamis load module batch_generator secara aman agar tidak mengunci thread
            import batch_generator
            
            # Sinkronisasi folder kerja dari setelan GUI
            batch_generator.VIDEO_INPUT_DIR = self.workspace_folders.get("video_input", batch_generator.VIDEO_INPUT_DIR)
            batch_generator.MUSIC_INPUT_DIR = self.workspace_folders.get("music_input", batch_generator.MUSIC_INPUT_DIR)
            batch_generator.OUTPUT_DIR = self.workspace_folders.get("output", batch_generator.OUTPUT_DIR)
            batch_generator.FONTS_DIR = self.workspace_folders.get("fonts", batch_generator.FONTS_DIR)
            
            # Ambil musik latar yang terdeteksi
            bgm_paths = glob.glob(os.path.join(batch_generator.MUSIC_INPUT_DIR, "*.mp3"))
            
            for idx_num, config in enumerate(self.scripts_data):
                # 1. Cooperative Stop / Pause check
                if self._is_killed:
                    self.finished_signal.emit(False, "Rendering dihentikan oleh pengguna!")
                    return
                self.check_paused()
                if self._is_killed:
                    self.finished_signal.emit(False, "Rendering dihentikan oleh pengguna!")
                    return
                
                idx = config["id"]
                product_name = config["product"]
                category = config["category"]
                naskah = config["naskah"]
                
                # Dinamis petakan nama subfolder video B-roll berdasarkan produk
                if "perisa" in product_name.lower():
                    folder_name = "Perisa Cabai"
                elif "poc" in product_name.lower():
                    folder_name = "POC Cabai"
                else:
                    # Fallback jika nama kategori adalah nama subfolder
                    folder_name = category
                
                self.progress_signal.emit(idx_num + 1, total_videos)
                self.status_signal.emit(f"\n[VIDEO {idx_num+1}/{total_videos}] Produk: {product_name} | Kategori: {category}...")
                
                # 1. Pindai video klip mentah untuk produk ini
                product_video_dir = os.path.join(batch_generator.VIDEO_INPUT_DIR, folder_name)
                
                # Fallback ke folder utama jika folder kategori spesifik kosong/tidak ditemukan
                if not os.path.exists(product_video_dir):
                    product_video_dir = batch_generator.VIDEO_INPUT_DIR
                    
                product_video_paths = []
                for ext in ["*.mp4", "*.mov", "*.avi", "*.mkv"]:
                    product_video_paths.extend(glob.glob(os.path.join(product_video_dir, ext)))
                    product_video_paths.extend(glob.glob(os.path.join(product_video_dir, ext.upper())))
                    
                if not product_video_paths:
                    self.status_signal.emit(f"[ERROR] Tidak ada file video B-roll di folder: '{product_video_dir}'!")
                    self.status_signal.emit(f"Melewati Video {idx}...")
                    continue
                
                self.status_signal.emit(f" -> Terdeteksi {len(product_video_paths)} klip B-roll untuk {folder_name}.")
                
                temp_audio = os.path.join(batch_generator.BASE_DIR, f"temp_vo_{idx}.wav")
                temp_vtt = os.path.join(batch_generator.BASE_DIR, f"temp_sub_{idx}.vtt")
                           # Inisialisasi variabel untuk resource disposal di blok finally
                vo_audio = None
                bgm_audio = None
                mixed_audio = None
                compiled_video = None
                subtitle_clips = []
                watermark_clip = None
                final_video = None
                
                try:
                    # 2. Cooperative Stop / Pause check
                    if self._is_killed:
                        self.finished_signal.emit(False, "Rendering dihentikan oleh pengguna!")
                        return
                    self.check_paused()
                    if self._is_killed:
                        self.finished_signal.emit(False, "Rendering dihentikan oleh pengguna!")
                        return
                    
                    # A. Buat Voiceover via RVC
                    self.status_signal.emit(" -> Menyintesis suara AI via edge-tts & RVC GPU...")
                    
                    # Menggunakan parameter RVC kustom yang dikirimkan dari Tab GUI
                    original_rvc_model = batch_generator.RVC_MODEL_PATH
                    original_rvc_index = batch_generator.RVC_INDEX_PATH
                    original_pitch_shift = getattr(batch_generator, "RVC_PITCH_SHIFT", 6)
                    original_index_rate = getattr(batch_generator, "RVC_INDEX_RATE", 0.2)
                    
                    if self.rvc_params.get("model_path"):
                        batch_generator.RVC_MODEL_PATH = self.rvc_params["model_path"]
                    if self.rvc_params.get("index_path"):
                        batch_generator.RVC_INDEX_PATH = self.rvc_params["index_path"]
                    if "f0up_key" in self.rvc_params:
                        batch_generator.RVC_PITCH_SHIFT = self.rvc_params["f0up_key"]
                    if "index_rate" in self.rvc_params:
                        batch_generator.RVC_INDEX_RATE = self.rvc_params["index_rate"]
                    
                    asyncio.run(batch_generator.generate_voiceover_rvc(naskah, temp_audio, temp_vtt))
                    
                    # Kembalikan model RVC bawaan setelah generasi audio
                    batch_generator.RVC_MODEL_PATH = original_rvc_model
                    batch_generator.RVC_INDEX_PATH = original_rvc_index
                    batch_generator.RVC_PITCH_SHIFT = original_pitch_shift
                    batch_generator.RVC_INDEX_RATE = original_index_rate
                    
                    # 3. Cooperative Stop / Pause check
                    if self._is_killed:
                        self.finished_signal.emit(False, "Rendering dihentikan oleh pengguna!")
                        return
                    self.check_paused()
                    if self._is_killed:
                        self.finished_signal.emit(False, "Rendering dihentikan oleh pengguna!")
                        return
                    
                    if not os.path.exists(temp_audio):
                        self.status_signal.emit(f"[ERROR] Generasi audio voiceover gagal untuk Video {idx}.")
                        continue
                        
                    vo_audio = batch_generator.AudioFileClip(temp_audio)
                    target_duration = vo_audio.duration
                    self.status_signal.emit(f" -> Voiceover siap. Durasi: {target_duration:.2f} detik.")
                    
                    # B. Assembly B-roll Video
                    self.status_signal.emit(" -> Menyusun klip B-roll dinamis (Anti-Duplikasi)...")
                    transition_type = self.layout_params.get("transition", "None")
                    limit_to_3s = self.layout_params.get("limit_to_3s", False)
                    compiled_video = batch_generator.buat_video_assembly(
                        target_duration, 
                        product_video_paths, 
                        transition_type=transition_type, 
                        transition_duration=0.5,
                        limit_to_3s=limit_to_3s
                    )
                    
                    # 4. Cooperative Stop / Pause check
                    if self._is_killed:
                        self.finished_signal.emit(False, "Rendering dihentikan oleh pengguna!")
                        return
                    self.check_paused()
                    if self._is_killed:
                        self.finished_signal.emit(False, "Rendering dihentikan oleh pengguna!")
                        return
                    
                    # C. Subtitle Rendering (Custom Font, Size, Color, Position, and Stroke)
                    self.status_signal.emit(" -> Merender subtitle estetik kata-per-kata...")
                    raw_subs = batch_generator.parse_vtt(temp_vtt)
                    grouped_subs = batch_generator.kelompokkan_subtitle(raw_subs, max_words=2, max_duration=1.2)
                    
                    # Modifikasi batch_generator fungsi buat_subtitle secara dinamis
                    original_font_path = batch_generator.dapatkan_font_path()
                    if self.layout_params.get("font_path"):
                        # Temporarily override font path
                        font_override = self.layout_params["font_path"]
                        def custom_font_path(): return font_override
                        batch_generator.dapatkan_font_path = custom_font_path
                    
                    # Decode layout styling parameters
                    color_map = {
                        "Kuning Cerah": (255, 255, 0, 255),
                        "Putih Bersih": (255, 255, 255, 255),
                        "Hijau Neon": (57, 255, 20, 255),
                        "Cyan Elektrik": (0, 255, 255, 255)
                    }
                    text_color = color_map.get(self.layout_params.get("subtitle_color"), (255, 255, 0, 255))
                    
                    size_val = self.layout_params.get("subtitle_size", 56)
                    font_size_scale = size_val / 1080.0
                    
                    stroke_val = self.layout_params.get("subtitle_stroke", 6)
                    stroke_width_scale = stroke_val / float(size_val) if size_val > 0 else 0.0
                    
                    vertical_position = self.layout_params.get("subtitle_pos", 74) / 100.0
                    
                    subtitle_clips = batch_generator.buat_subtitle_overlay_clip(
                        grouped_subs, 
                        batch_generator.OUTPUT_W, 
                        batch_generator.OUTPUT_H,
                        font_size_scale=font_size_scale,
                        text_color=text_color,
                        stroke_width_scale=stroke_width_scale,
                        vertical_position=vertical_position
                    )
                    
                    # Kembalikan fungsi font bawaan
                    def restore_font_path(): return original_font_path
                    batch_generator.dapatkan_font_path = restore_font_path
                    
                    # D. Composite & Audio Mixing
                    self.status_signal.emit(" -> Melakukan compositing audio-visual & backsound...")
                    
                    composite_layers = [compiled_video] + subtitle_clips
                    
                    # PNG Logo Watermark overlay
                    watermark_path = self.layout_params.get("watermark_path")
                    if watermark_path and os.path.exists(watermark_path):
                        try:
                            from PIL import Image
                            import numpy as np
                            logo_img = Image.open(watermark_path).convert("RGBA")
                            logo_w, logo_h = logo_img.size
                            target_w = self.layout_params.get("watermark_size", 150)
                            target_h = int(logo_h * (target_w / logo_w))
                            logo_img = logo_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                            
                            logo_rgba = np.array(logo_img)
                            logo_rgb = logo_rgba[:, :, :3]
                            opacity = self.layout_params.get("watermark_opacity", 0.7)
                            logo_alpha = ((logo_rgba[:, :, 3] / 255.0) * opacity).astype(np.float32)
                            
                            watermark_clip = batch_generator.ImageClip(logo_rgb).with_mask(
                                batch_generator.ImageClip(logo_alpha).with_is_mask(True)
                            )
                            watermark_clip = watermark_clip.with_duration(target_duration)
                            watermark_clip = watermark_clip.with_position((batch_generator.OUTPUT_W - target_w - 50, 50))
                            
                            composite_layers.append(watermark_clip)
                            self.status_signal.emit(" -> Menempelkan logo watermark kustom...")
                        except Exception as e:
                            self.status_signal.emit(f"[WARNING] Gagal menempelkan logo watermark: {str(e)}")
                    
                    final_video = batch_generator.CompositeVideoClip(composite_layers)
                    
                    if bgm_paths:
                        chosen_bgm = batch_generator.random.choice(bgm_paths)
                        bgm_audio = batch_generator.AudioFileClip(chosen_bgm)
                        
                        if bgm_audio.duration < target_duration:
                            bgm_audio = bgm_audio.with_effects([batch_generator.AudioLoop(duration=target_duration)])
                        else:
                            bgm_audio = bgm_audio.subclipped(0, target_duration)
                            
                        # Backsound volume dari parameter layout
                        bgm_volume = self.layout_params.get("bgm_volume", 0.08)
                        bgm_audio = bgm_audio.with_volume_scaled(bgm_volume)
                        mixed_audio = batch_generator.CompositeAudioClip([vo_audio.with_volume_scaled(1.0), bgm_audio])
                    else:
                        mixed_audio = vo_audio
                        
                    final_video = final_video.with_audio(mixed_audio)
                    
                    # E. Ekspor Video Final Dinamis
                    product_clean = product_name.replace(" ", "_")
                    cat_clean = category.replace(" ", "_")
                    output_path = os.path.join(batch_generator.OUTPUT_DIR, f"{product_clean}_{cat_clean}_{idx}.mp4")
                    
                    self.status_signal.emit(f" -> Mulai menulis file MP4 ke: {output_path}...")
                    
                    # 5. Cooperative Stop / Pause check right before export
                    if self._is_killed:
                        self.finished_signal.emit(False, "Rendering dihentikan oleh pengguna!")
                        return
                    self.check_paused()
                    if self._is_killed:
                        self.finished_signal.emit(False, "Rendering dihentikan oleh pengguna!")
                        return
                    
                    final_video.write_videofile(
                        output_path,
                        fps=24,
                        codec="libx264",
                        audio_codec="aac",
                        threads=4,
                        logger=MoviePyStopLogger(self)
                    )
                    
                    self.status_signal.emit(f"[SUCCESS] Video {idx} berhasil dirender!")
                except Exception as loop_err:
                    self.status_signal.emit(f"[ERROR] Gagal merender Video {idx}: {str(loop_err)}")
                    raise loop_err
                finally:
                    # MEMBERSIHKAN MEMORI SECARA TOTAL (Anti-Memory Leak & GC Force)
                    if vo_audio:
                        try: vo_audio.close()
                        except: pass
                    if bgm_audio:
                        try: bgm_audio.close()
                        except: pass
                    if mixed_audio and mixed_audio is not vo_audio:
                        try: mixed_audio.close()
                        except: pass
                    
                    if compiled_video:
                        # Tutup semua raw VideoFileClips yang dibuka di buat_video_assembly
                        for raw_c in getattr(compiled_video, 'opened_raw_clips', []):
                            try: raw_c.close()
                            except: pass
                        try: compiled_video.close()
                        except: pass
                        
                    for sub_clip in subtitle_clips:
                        try:
                            if sub_clip.mask:
                                sub_clip.mask.close()
                            sub_clip.close()
                        except: pass
                        
                    if watermark_clip:
                        try:
                            if watermark_clip.mask:
                                watermark_clip.mask.close()
                            watermark_clip.close()
                        except: pass
                        
                    if final_video:
                        try: final_video.close()
                        except: pass
                        
                    # Bersihkan temporary files
                    for temp_file in [temp_audio, temp_vtt]:
                        if os.path.exists(temp_file):
                            try: os.remove(temp_file)
                            except: pass
                            
                    # Paksa Garbage Collector membersihkan memori NumPy & PIL
                    import gc
                    gc.collect()
                
                self.status_signal.emit(f"[SUCCESS] Video {idx} berhasil dirender!")
                
            self.finished_signal.emit(True, "Seluruh rendering selesai!")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

# ==========================================
# 2. MAIN APPLICATION GUI (PYSIDE6)
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoVideo-RVC: AI Automated Video Studio 🚀")
        self.resize(1200, 800)
        self.setStyleSheet(app_style.dapatkan_style_sheet())
        
        # Inisialisasi folder default
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.video_input = os.path.join(self.base_dir, "video_input")
        self.music_input = os.path.join(self.base_dir, "music_input")
        self.fonts_dir = os.path.join(self.base_dir, "fonts")
        self.output_dir = os.path.join(self.base_dir, "output")
        self.rvc_dir = os.path.join(self.base_dir, "RVC")
        
        # Load Workspace Profiles
        self.profiles_file = os.path.join(self.base_dir, "workspace_profiles.json")
        self.profiles_data = self.load_profiles()
        
        # Override dengan setelan profil aktif
        active_prof = self.profiles_data.get("active_profile", "Default")
        prof = self.profiles_data["profiles"].get(active_prof, {})
        self.video_input = prof.get("video_input", self.video_input)
        self.music_input = prof.get("music_input", self.music_input)
        self.fonts_dir = prof.get("fonts", self.fonts_dir)
        self.output_dir = prof.get("output", self.output_dir)
        
        self.scanned_models = []
        self.scripts_list = [] # Menyimpan hasil naskah dinamis dari AI
        self.ai_drafts_list = [] # Menyimpan draf hasil AI sebelum dimasukkan ke Script Manager
        
        self.init_ui()
        self.scan_workspace()
        self.scan_local_rvc_models()
        self.detect_ollama_local()
        
        # Terapkan setelan profil lengkap setelah UI diinisialisasi
        self.on_profile_changed()
        
    def init_ui(self):
        # Master Widget & Layout - Horizontal Split for Left Sidebar Layout
        master_widget = QWidget()
        self.setCentralWidget(master_widget)
        master_layout = QHBoxLayout(master_widget)
        master_layout.setContentsMargins(0, 0, 0, 0)
        master_layout.setSpacing(0)
        
        # ==========================================
        # LEFT SIDEBAR NAVIGATION
        # ==========================================
        sidebar = QFrame()
        sidebar.setObjectName("sidebar_frame")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 24, 20, 24)
        sidebar_layout.setSpacing(6)
        
        # Logo Header (Mimicking premium design)
        logo_container = QHBoxLayout()
        logo_container.setSpacing(12)
        logo_container.setContentsMargins(0, 0, 0, 24)
        
        logo_icon = QLabel("AI")
        logo_icon.setFixedSize(36, 36)
        logo_icon.setAlignment(Qt.AlignCenter)
        logo_icon.setStyleSheet(
            "background-color: #2563eb; color: #ffffff; font-weight: 800; "
            "font-size: 15px; border-radius: 8px;"
        )
        
        logo_text = QLabel("AI VIDEO\nCREATOR")
        logo_text.setStyleSheet(
            "color: #ffffff; font-weight: 700; font-size: 13px; line-height: 1.1;"
        )
        
        logo_container.addWidget(logo_icon)
        logo_container.addWidget(logo_text)
        logo_container.addStretch()
        sidebar_layout.addLayout(logo_container)
        
        # Navigation Items mapped to SVG icons
        self.nav_buttons = []
        nav_items = [
            ("Workspace", "folder.svg"),
            ("Script Manager", "document.svg"),
            ("AI Writer", "pen.svg"),
            ("RVC Settings", "mic.svg"),
            ("Layout Editor", "palette.svg"),
            ("RVC Trainer", "activity.svg"),
            ("Batch Renderer", "video.svg")
        ]
        
        for idx, (name, icon_file) in enumerate(nav_items):
            btn = QPushButton("  " + name)
            btn.setIcon(QIcon(os.path.join(self.base_dir, "icons", icon_file)))
            btn.setIconSize(QSize(16, 16))
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setObjectName("sidebar_nav_btn")
            btn.setCursor(Qt.PointingHandCursor)
            
            # Connect click to switch tab
            btn.clicked.connect(lambda checked=False, i=idx: self.switch_page(i))
            
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)
            
        sidebar_layout.addStretch()
        
        # ==========================================
        # RIGHT MAIN CONTENT AREA
        # ==========================================
        main_content = QWidget()
        main_content_layout = QVBoxLayout(main_content)
        main_content_layout.setContentsMargins(24, 24, 24, 24)
        main_content_layout.setSpacing(16)
        
        # 1. TOP HEADER (Premium Glass Title)
        header_frame = QFrame()
        header_frame.setObjectName("glass_card")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 14, 20, 14)
        
        title_layout = QVBoxLayout()
        title_label = QLabel("AutoVideo-RVC Studio")
        title_label.setObjectName("header_label")
        sub_title = QLabel("Workspace Otomatisasi Video Marketing & AI Script Studio")
        sub_title.setObjectName("sub_header_label")
        title_layout.addWidget(title_label)
        title_layout.addWidget(sub_title)
        header_layout.addLayout(title_layout)
        
        header_layout.addStretch()
        
        # Workspace Profile Selector inside Header (Global Switcher)
        profile_card = QFrame()
        profile_card.setObjectName("glass_card")
        profile_layout = QHBoxLayout(profile_card)
        profile_layout.setContentsMargins(12, 6, 12, 6)
        profile_layout.setSpacing(8)
        
        lbl_prof = QLabel("Profile:")
        lbl_prof.setStyleSheet("font-size: 10px; font-weight: bold; color: #8c8c9e;")
        profile_layout.addWidget(lbl_prof)
        
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(160)
        self.profile_combo.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        profile_layout.addWidget(self.profile_combo)
        
        btn_new_profile = QPushButton("➕ New")
        btn_new_profile.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        btn_new_profile.clicked.connect(self.create_new_profile)
        profile_layout.addWidget(btn_new_profile)
        
        btn_save_profile = QPushButton("💾 Save")
        btn_save_profile.setStyleSheet(
            "background-color: #064e3b; border: 1px solid #059669; color: #a7f3d0; "
            "padding: 4px 8px; font-size: 12px; font-weight: bold;"
        )
        btn_save_profile.clicked.connect(self.save_current_profile_config)
        profile_layout.addWidget(btn_save_profile)
        
        btn_del_profile = QPushButton("🗑️ Delete")
        btn_del_profile.setObjectName("danger_button")
        btn_del_profile.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        btn_del_profile.clicked.connect(self.delete_profile)
        profile_layout.addWidget(btn_del_profile)
        
        header_layout.addWidget(profile_card)
        header_layout.addSpacing(10)
        
        # GPU Status Card
        gpu_card = QFrame()
        gpu_card.setObjectName("glass_card")
        gpu_card_layout = QVBoxLayout(gpu_card)
        gpu_card_layout.setContentsMargins(12, 6, 12, 6)
        gpu_status_title = QLabel("CUDA GPU ACCELERATION")
        gpu_status_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #8c8c9e;")
        
        # Cek ketersediaan RVC
        import batch_generator
        if batch_generator.RVC_ENABLED:
            gpu_status_val = QLabel("✅ ACTIVE (NVIDIA RTX)")
            gpu_status_val.setStyleSheet("font-weight: bold; color: #10b981;")
        else:
            gpu_status_val = QLabel("❌ INACTIVE (CPU FALLBACK)")
            gpu_status_val.setStyleSheet("font-weight: bold; color: #ef4444;")
            
        gpu_card_layout.addWidget(gpu_status_title)
        gpu_card_layout.addWidget(gpu_status_val)
        header_layout.addWidget(gpu_card)
        
        main_content_layout.addWidget(header_frame)
        
        # Stacked Pages Widget instead of QTabWidget
        self.tabs = QStackedWidget()
        main_content_layout.addWidget(self.tabs)
        
        master_layout.addWidget(sidebar)
        master_layout.addWidget(main_content)
        
        # Inisialisasi masing-masing Tab
        self.init_tab_workspace()
        self.init_tab_script_manager()
        self.init_tab_ai_generator()
        self.init_tab_rvc_parameters()
        self.init_tab_layout_editor()
        self.init_tab_rvc_trainer()
        self.init_tab_renderer()
        
        # Populate and connect profile switcher signals globally!
        self.populate_profiles()
        self.profile_combo.currentIndexChanged.connect(self.on_profile_changed)
        
        # Set default active page
        self.switch_page(0)

    def switch_page(self, index):
        self.tabs.setCurrentIndex(index)
        # Update active state style of buttons
        for i, btn in enumerate(self.nav_buttons):
            is_active = (i == index)
            btn.setChecked(is_active)
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def load_profiles(self):
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return {
            "active_profile": "Default",
            "profiles": {
                "Default": {
                    "video_input": self.video_input,
                    "music_input": self.music_input,
                    "fonts": self.fonts_dir,
                    "output": self.output_dir
                }
            }
        }

    def save_profiles_to_disk(self):
        try:
            with open(self.profiles_file, "w") as f:
                json.dump(self.profiles_data, f, indent=4)
        except Exception as e:
            print("Error saving workspace profiles:", str(e))

    def populate_profiles(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for name in self.profiles_data["profiles"].keys():
            self.profile_combo.addItem(name)
        active = self.profiles_data.get("active_profile", "Default")
        if active in self.profiles_data["profiles"]:
            self.profile_combo.setCurrentText(active)
        self.profile_combo.blockSignals(False)

    def on_profile_changed(self):
        name = self.profile_combo.currentText() if hasattr(self, "profile_combo") else self.profiles_data.get("active_profile", "Default")
        if not name or name not in self.profiles_data["profiles"]:
            return
        
        self.profiles_data["active_profile"] = name
        prof = self.profiles_data["profiles"][name]
        
        # Update Directory Inputs
        if hasattr(self, "dir_inputs"):
            if "video_input" in prof:
                self.dir_inputs["video_input"].setText(prof["video_input"])
            if "music_input" in prof:
                self.dir_inputs["music_input"].setText(prof["music_input"])
            if "fonts" in prof:
                self.dir_inputs["fonts"].setText(prof["fonts"])
            if "output" in prof:
                self.dir_inputs["output"].setText(prof["output"])
            
        # Update RVC settings if they were saved in the profile (with cross-slash normalization)
        if "rvc_model" in prof and hasattr(self, "rvc_pth_combo"):
            model_path = os.path.normpath(prof["rvc_model"])
            found = False
            for i in range(self.rvc_pth_combo.count()):
                if os.path.normpath(self.rvc_pth_combo.itemText(i)) == model_path:
                    self.rvc_pth_combo.setCurrentIndex(i)
                    found = True
                    break
            if not found and os.path.exists(model_path):
                self.rvc_pth_combo.addItem(model_path)
                self.rvc_pth_combo.setCurrentText(model_path)
                
        if "rvc_index" in prof and hasattr(self, "rvc_index_combo"):
            index_path = os.path.normpath(prof["rvc_index"])
            found = False
            for i in range(self.rvc_index_combo.count()):
                if os.path.normpath(self.rvc_index_combo.itemText(i)) == index_path:
                    self.rvc_index_combo.setCurrentIndex(i)
                    found = True
                    break
            if not found and os.path.exists(index_path):
                self.rvc_index_combo.addItem(index_path)
                self.rvc_index_combo.setCurrentText(index_path)
        if "pitch_shift" in prof and hasattr(self, "pitch_slider"):
            self.pitch_slider.setValue(prof["pitch_shift"])
        if "index_rate" in prof and hasattr(self, "index_slider"):
            self.index_slider.setValue(prof["index_rate"])
            
        # Update Layout settings if they were saved in the profile
        if "font_path" in prof and hasattr(self, "font_combo"):
            self.font_combo.setCurrentText(prof["font_path"])
        if "subtitle_color" in prof and hasattr(self, "subtitle_color_combo"):
            self.subtitle_color_combo.setCurrentText(prof["subtitle_color"])
        if "subtitle_size" in prof and hasattr(self, "subtitle_size_spin"):
            self.subtitle_size_spin.setValue(prof["subtitle_size"])
        if "subtitle_stroke" in prof and hasattr(self, "subtitle_stroke_spin"):
            self.subtitle_stroke_spin.setValue(prof["subtitle_stroke"])
        if "subtitle_pos" in prof and hasattr(self, "subtitle_pos_slider"):
            self.subtitle_pos_slider.setValue(prof["subtitle_pos"])
        if "watermark_path" in prof and hasattr(self, "watermark_input"):
            self.watermark_input.setText(prof["watermark_path"])
        if "watermark_opacity" in prof and hasattr(self, "opacity_slider"):
            self.opacity_slider.setValue(prof["watermark_opacity"])
        if "watermark_size" in prof and hasattr(self, "watermark_size_spin"):
            self.watermark_size_spin.setValue(prof["watermark_size"])
        if "bgm_volume" in prof and hasattr(self, "bgm_vol_spin"):
            self.bgm_vol_spin.setValue(prof["bgm_volume"])
        if "transition" in prof and hasattr(self, "transition_combo"):
            self.transition_combo.setCurrentText(prof["transition"])
        if "limit_to_3s" in prof and hasattr(self, "limit_to_3s_checkbox"):
            self.limit_to_3s_checkbox.setChecked(prof["limit_to_3s"])
        else:
            if hasattr(self, "limit_to_3s_checkbox"):
                self.limit_to_3s_checkbox.setChecked(False)
            
        # Update/Reset naskah scripts list specific to this profile!
        if "scripts_list" in prof:
            self.scripts_list = prof["scripts_list"]
        else:
            # Fallback for Original Settings profile to load the 40 original scripts automatically
            if name == "Original_Terminal_Settings":
                self.load_original_scripts()
                return # load_original_scripts handles table population and disk save
            else:
                self.scripts_list = []
                
        # Update the visual naskah table view
        if hasattr(self, "naskah_table"):
            self.naskah_table.blockSignals(True)
            self.naskah_table.setRowCount(len(self.scripts_list))
            for r, script in enumerate(self.scripts_list):
                self.naskah_table.setItem(r, 0, QTableWidgetItem(str(script["id"])))
                self.naskah_table.setItem(r, 1, QTableWidgetItem(script["category"]))
                self.naskah_table.setItem(r, 2, QTableWidgetItem(script["product"]))
                
                naskah_item = QTableWidgetItem(script["naskah"])
                self.naskah_table.setItem(r, 3, naskah_item)
            self.naskah_table.blockSignals(False)
            
            # Hubungkan cellChanged secara aman
            try:
                self.naskah_table.cellChanged.disconnect(self.on_naskah_cell_changed)
            except:
                pass
            self.naskah_table.cellChanged.connect(self.on_naskah_cell_changed)
            
        self.save_profiles_to_disk()
        self.scan_workspace()

    def save_current_profile_config(self):
        name = self.profile_combo.currentText()
        if not name:
            return
            
        # Gather all current UI values
        prof = {
            "video_input": self.dir_inputs["video_input"].text(),
            "music_input": self.dir_inputs["music_input"].text(),
            "fonts": self.dir_inputs["fonts"].text(),
            "output": self.dir_inputs["output"].text(),
            "scripts_list": self.scripts_list  # Simpan naskah unik milik profil ini!
        }
        
        # Gather RVC parameters if they exist (with normalization)
        if hasattr(self, "rvc_pth_combo"):
            val = self.rvc_pth_combo.currentText()
            prof["rvc_model"] = os.path.normpath(val) if val else ""
        if hasattr(self, "rvc_index_combo"):
            val = self.rvc_index_combo.currentText()
            prof["rvc_index"] = os.path.normpath(val) if val else ""
        if hasattr(self, "pitch_slider"):
            prof["pitch_shift"] = self.pitch_slider.value()
        if hasattr(self, "index_slider"):
            prof["index_rate"] = self.index_slider.value()
            
        # Gather Layout parameters if they exist
        if hasattr(self, "font_combo"):
            prof["font_path"] = self.font_combo.currentText()
        if hasattr(self, "subtitle_color_combo"):
            prof["subtitle_color"] = self.subtitle_color_combo.currentText()
        if hasattr(self, "subtitle_size_spin"):
            prof["subtitle_size"] = self.subtitle_size_spin.value()
        if hasattr(self, "subtitle_stroke_spin"):
            prof["subtitle_stroke"] = self.subtitle_stroke_spin.value()
        if hasattr(self, "subtitle_pos_slider"):
            prof["subtitle_pos"] = self.subtitle_pos_slider.value()
        if hasattr(self, "watermark_input"):
            prof["watermark_path"] = self.watermark_input.text()
        if hasattr(self, "opacity_slider"):
            prof["watermark_opacity"] = self.opacity_slider.value()
        if hasattr(self, "watermark_size_spin"):
            prof["watermark_size"] = self.watermark_size_spin.value()
        if hasattr(self, "bgm_vol_spin"):
            prof["bgm_volume"] = self.bgm_vol_spin.value()
        if hasattr(self, "transition_combo"):
            prof["transition"] = self.transition_combo.currentText()
        if hasattr(self, "limit_to_3s_checkbox"):
            prof["limit_to_3s"] = self.limit_to_3s_checkbox.isChecked()
            
        self.profiles_data["profiles"][name] = prof
        self.save_profiles_to_disk()
        QMessageBox.information(self, "Profile Saved", f"Workspace profile '{name}' successfully saved!")

    def create_new_profile(self):
        # pyrefly: ignore [missing-import]
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Workspace Profile", "Enter workspace profile name:")
        if ok and name.strip():
            name = name.strip()
            if name in self.profiles_data["profiles"]:
                QMessageBox.warning(self, "Error", f"Profile '{name}' already exists!")
                return
                
            active_name = self.profile_combo.currentText()
            if active_name and active_name in self.profiles_data["profiles"]:
                self.profiles_data["profiles"][name] = dict(self.profiles_data["profiles"][active_name])
            else:
                self.profiles_data["profiles"][name] = {
                    "video_input": self.video_input,
                    "music_input": self.music_input,
                    "fonts": self.fonts_dir,
                    "output": self.output_dir
                }
                
            self.profiles_data["active_profile"] = name
            self.save_profiles_to_disk()
            
            self.populate_profiles()
            self.profile_combo.setCurrentText(name)

    def delete_profile(self):
        name = self.profile_combo.currentText()
        if not name:
            return
        if name == "Default":
            QMessageBox.warning(self, "Error", "Cannot delete the Default workspace profile!")
            return
            
        confirm = QMessageBox.question(
            self, "Confirm Delete", 
            f"Are you sure you want to delete the profile '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            del self.profiles_data["profiles"][name]
            self.profiles_data["active_profile"] = "Default"
            self.save_profiles_to_disk()
            
            self.populate_profiles()
            self.profile_combo.setCurrentText("Default")

    # ==========================================
    # TAB 2: SCRIPT MANAGER (Master Grid)
    # ==========================================
    def init_tab_script_manager(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title = QLabel("WORKSPACE SCRIPT MANAGER (MASTER GRID)")
        title.setObjectName("section_title")
        layout.addWidget(title)
        
        # Spacious Table Grid
        self.naskah_table = QTableWidget(0, 4)
        self.naskah_table.setHorizontalHeaderLabels(["ID", "Kategori / Folder B-Roll", "Produk", "Naskah Video"])
        self.naskah_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.naskah_table.verticalHeader().setVisible(False)
        self.naskah_table.verticalHeader().setDefaultSectionSize(40)
        self.naskah_table.setEditTriggers(QTableWidget.NoEditTriggers) # Disable standard inline editing!
        self.naskah_table.cellDoubleClicked.connect(self.open_master_script_editor) # Double click modal editor!
        layout.addWidget(self.naskah_table)
        
        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        
        btn_add = QPushButton("➕ Add Row")
        btn_add.clicked.connect(self.add_manual_script_row)
        btn_layout.addWidget(btn_add)
        
        btn_del = QPushButton("🗑️ Delete Selected")
        btn_del.setObjectName("danger_button")
        btn_del.clicked.connect(self.delete_selected_script_row)
        btn_layout.addWidget(btn_del)
        

        
        btn_clear = QPushButton("🧹 Clear All Scripts")
        btn_clear.setObjectName("danger_button")
        btn_clear.clicked.connect(self.clear_all_scripts)
        btn_layout.addWidget(btn_clear)
        
        layout.addLayout(btn_layout)
        
        self.tabs.addWidget(tab)

    def add_manual_script_row(self):
        row = self.naskah_table.rowCount()
        self.naskah_table.insertRow(row)
        
        next_id = 1
        if self.scripts_list:
            next_id = max(s["id"] for s in self.scripts_list) + 1
            
        self.naskah_table.setItem(row, 0, QTableWidgetItem(str(next_id)))
        self.naskah_table.setItem(row, 1, QTableWidgetItem("POC Cabai"))
        self.naskah_table.setItem(row, 2, QTableWidgetItem("POC Cabai"))
        self.naskah_table.setItem(row, 3, QTableWidgetItem("Tulis naskah kustom Anda di sini..."))
        
        self.scripts_list.append({
            "id": next_id,
            "category": "POC Cabai",
            "product": "POC Cabai",
            "naskah": "Tulis naskah kustom Anda di sini..."
        })

    def delete_selected_script_row(self):
        cur_row = self.naskah_table.currentRow()
        if cur_row != -1:
            self.naskah_table.removeRow(cur_row)
            if cur_row < len(self.scripts_list):
                self.scripts_list.pop(cur_row)

    def clear_all_scripts(self):
        confirm = QMessageBox.question(
            self, "Confirm Clear", 
            "Apakah Anda yakin ingin menghapus semua naskah di workspace saat ini?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.scripts_list = []
            self.naskah_table.setRowCount(0)

    def append_ai_drafts_to_master(self):
        if not hasattr(self, "ai_drafts_list") or not self.ai_drafts_list:
            QMessageBox.warning(self, "No Drafts", "Tidak ada draf naskah hasil AI untuk dimasukkan!")
            return
            
        start_id = max([s["id"] for s in self.scripts_list]) + 1 if self.scripts_list else 1
        for idx, draft in enumerate(self.ai_drafts_list):
            new_id = start_id + idx
            self.scripts_list.append({
                "id": new_id,
                "category": draft["category"],
                "product": draft["product"],
                "naskah": draft["naskah"]
            })
            
        self.refresh_master_table()
        QMessageBox.information(self, "Success", f"Berhasil menambahkan {len(self.ai_drafts_list)} naskah ke Script Manager!")
        self.switch_page(1) # Switch to Script Manager

    def replace_master_with_ai_drafts(self):
        if not hasattr(self, "ai_drafts_list") or not self.ai_drafts_list:
            QMessageBox.warning(self, "No Drafts", "Tidak ada draf naskah hasil AI untuk dimasukkan!")
            return
            
        confirm = QMessageBox.question(
            self, "Confirm Replace", 
            "Apakah Anda yakin ingin menimpa seluruh naskah di Script Manager dengan hasil draf AI saat ini?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.scripts_list = []
            for idx, draft in enumerate(self.ai_drafts_list):
                self.scripts_list.append({
                    "id": idx + 1,
                    "category": draft["category"],
                    "product": draft["product"],
                    "naskah": draft["naskah"]
                })
                
            self.refresh_master_table()
            QMessageBox.information(self, "Success", f"Berhasil menimpa seluruh naskah dengan {len(self.ai_drafts_list)} naskah baru!")
            self.switch_page(1) # Switch to Script Manager

    def refresh_master_table(self):
        if not hasattr(self, "naskah_table"):
            return
        self.naskah_table.blockSignals(True)
        self.naskah_table.setRowCount(len(self.scripts_list))
        for r, script in enumerate(self.scripts_list):
            self.naskah_table.setItem(r, 0, QTableWidgetItem(str(script["id"])))
            self.naskah_table.setItem(r, 1, QTableWidgetItem(script["category"]))
            self.naskah_table.setItem(r, 2, QTableWidgetItem(script["product"]))
            
            naskah_item = QTableWidgetItem(script["naskah"])
            self.naskah_table.setItem(r, 3, naskah_item)
        self.naskah_table.blockSignals(False)

    def load_original_scripts(self):
        try:
            import batch_generator
            self.scripts_list = []
            for config in batch_generator.VIDEOS_CONFIG:
                idx = config["id"]
                
                # Tentukan kategori naskah asli dari batch_generator (Promo, ProblemSolution, dll)
                if idx in range(1, 5) or idx in range(21, 25):
                    category = "Promo"
                elif idx in range(5, 9) or idx in range(25, 29):
                    category = "ProblemSolution"
                elif idx in range(9, 13) or idx in range(29, 33):
                    category = "Edukasi"
                elif idx in range(13, 17) or idx in range(33, 37):
                    category = "Testimoni"
                elif idx in [17, 18, 19, 20, 37]:
                    category = "Hardselling"
                else:
                    category = "DuetBundling"
                
                self.scripts_list.append({
                    "id": idx,
                    "category": category,
                    "product": config["product"],
                    "naskah": config["naskah"]
                })
                
            self.refresh_master_table()
            
            # Hubungkan signal cellChanged secara aman
            try:
                self.naskah_table.cellChanged.disconnect(self.on_naskah_cell_changed)
            except:
                pass
            self.naskah_table.cellChanged.connect(self.on_naskah_cell_changed)
            
        except Exception as e:
            print("Gagal memuat naskah bawaan dari batch_generator:", str(e))

    def on_naskah_cell_changed(self, row, column):
        if column == 3:
            naskah_item = self.naskah_table.item(row, 3)
            if naskah_item and row < len(self.scripts_list):
                self.scripts_list[row]["naskah"] = naskah_item.text()

    def open_master_script_editor(self, row, column):
        if row < 0 or row >= len(self.scripts_list):
            return
            
        script = self.scripts_list[row]
        dialog = ScriptEditDialog(self, f"Sunting Naskah Video (ID: {script['id']})", script["naskah"])
        if dialog.exec() == QDialog.Accepted:
            new_text = dialog.get_text().strip()
            self.scripts_list[row]["naskah"] = new_text
            
            # Update table cell view
            self.naskah_table.blockSignals(True)
            self.naskah_table.setItem(row, 3, QTableWidgetItem(new_text))
            self.naskah_table.blockSignals(False)
            
            self.save_profiles_to_disk()

    def open_draft_script_editor(self, row, column):
        if not hasattr(self, "ai_drafts_list") or row < 0 or row >= len(self.ai_drafts_list):
            return
            
        script = self.ai_drafts_list[row]
        dialog = ScriptEditDialog(self, f"Sunting Draf Naskah (ID: {script['id']})", script["naskah"])
        if dialog.exec() == QDialog.Accepted:
            new_text = dialog.get_text().strip()
            self.ai_drafts_list[row]["naskah"] = new_text
            
            self.ai_draft_table.setItem(row, 3, QTableWidgetItem(new_text))
        
    def open_product_desc_modal(self):
        desc = self.product_desc_input.toPlainText()
        dialog = ScriptEditDialog(
            self, 
            title_text="Sunting Deskripsi & Fitur Utama Produk", 
            initial_text=desc, 
            show_duration=False
        )
        dialog.resize(600, 400)
        dialog.text_edit.setPlaceholderText("Masukkan deskripsi produk secara detail agar hasil AI maksimal...")
        if dialog.exec() == QDialog.Accepted:
            self.product_desc_input.setPlainText(dialog.get_text())
        
    # ==========================================
    # TAB 1: WORKSPACE CONFIG
    # ==========================================
    def init_tab_workspace(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title = QLabel("WORKSPACE DIRECTORIES")
        title.setObjectName("section_title")
        layout.addWidget(title)
        
        card = QFrame()
        card.setObjectName("glass_card")
        card_layout = QVBoxLayout(card)
        
        # 4 Selektor direktori
        self.dir_inputs = {}
        dirs_config = [
            ("Video Input Folder (B-Roll):", "video_input", self.video_input),
            ("Music Input Folder (BGM):", "music_input", self.music_input),
            ("Fonts Folder (.ttf):", "fonts", self.fonts_dir),
            ("Output Videos Folder:", "output", self.output_dir)
        ]
        
        for label_txt, key, default_val in dirs_config:
            row_layout = QHBoxLayout()
            lbl = QLabel(label_txt)
            lbl.setMinimumWidth(200)
            row_layout.addWidget(lbl)
            
            line_edit = QLineEdit(default_val)
            self.dir_inputs[key] = line_edit
            row_layout.addWidget(line_edit)
            
            btn = QPushButton("Browse")
            btn.clicked.connect(lambda checked=False, k=key: self.browse_folder(k))
            row_layout.addWidget(btn)
            card_layout.addLayout(row_layout)
            
        layout.addWidget(card)
        
        # Status scan aset
        scan_title = QLabel("WORKSPACE ASSETS MATRIX")
        scan_title.setObjectName("section_title")
        layout.addWidget(scan_title)
        
        self.assets_status_label = QLabel("Memindai direktori lokal...")
        self.assets_status_label.setStyleSheet("font-size: 13px; color: #a1a1aa; background: transparent;")
        layout.addWidget(self.assets_status_label)
        
        btn_scan = QPushButton("Scan & Refresh Assets")
        btn_scan.setObjectName("gradient_button")
        btn_scan.clicked.connect(self.scan_workspace)
        layout.addWidget(btn_scan)
        
        layout.addStretch()
        self.tabs.addWidget(tab)
        
    def browse_folder(self, key):
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder", self.dir_inputs[key].text())
        if folder:
            self.dir_inputs[key].setText(folder)
            self.scan_workspace()
            
    def scan_workspace(self):
        # Update path kerja lokal
        self.video_input = self.dir_inputs["video_input"].text()
        self.music_input = self.dir_inputs["music_input"].text()
        self.fonts_dir = self.dir_inputs["fonts"].text()
        self.output_dir = self.dir_inputs["output"].text()
        
        video_count = len(glob.glob(os.path.join(self.video_input, "**/*.mp4"), recursive=True)) + \
                      len(glob.glob(os.path.join(self.video_input, "**/*.mov"), recursive=True))
                      
        music_count = len(glob.glob(os.path.join(self.music_input, "*.mp3")))
        font_count = len(glob.glob(os.path.join(self.fonts_dir, "*.ttf")))
        
        status_txt = (
            f"🎬 Total B-Roll Video Terdeteksi: {video_count} file\n"
            f"🎵 Total Backsound BGM Terdeteksi: {music_count} file\n"
            f"🔤 Font Subtitle Terdeteksi: {font_count} file"
        )
        self.assets_status_label.setText(status_txt)
        
    # ==========================================
    # TAB 2: AI SCRIPT GENERATOR (Dinamis Kategori)
    # ==========================================
    def init_tab_ai_generator(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Splitter untuk UI Input & UI Naskah
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Panel Kiri: Input
        left_panel = QFrame()
        left_panel.setObjectName("glass_card")
        left_layout = QVBoxLayout(left_panel)
        
        lbl_t = QLabel("AI COPYWRITER SETTINGS")
        lbl_t.setObjectName("section_title")
        left_layout.addWidget(lbl_t)
        
        # 1. Pilih Mesin AI
        left_layout.addWidget(QLabel("AI Engine:"))
        self.engine_selector = QComboBox()
        self.engine_selector.addItems(["Gemini API (Flash)", "Ollama (Lokal)", "OpenRouter API"])
        self.engine_selector.currentIndexChanged.connect(self.toggle_ai_engine_inputs)
        left_layout.addWidget(self.engine_selector)
        
        # Input API Key (Gemini/OpenRouter)
        self.api_key_label = QLabel("API Key:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Masukkan API Key Anda...")
        left_layout.addWidget(self.api_key_label)
        left_layout.addWidget(self.api_key_input)
        
        # Selector Model LLM Dinamis
        left_layout.addWidget(QLabel("Pilih Model LLM:"))
        self.model_selector = QComboBox()
        left_layout.addWidget(self.model_selector)
        
        # Inisialisasi daftar model awal secara aman
        self.toggle_ai_engine_inputs()
        
        # 2. Input Detail Produk
        left_layout.addWidget(QLabel("Nama Produk:"))
        self.product_name_input = QLineEdit("Perisai Cabai")
        left_layout.addWidget(self.product_name_input)
        
        desc_label_layout = QHBoxLayout()
        desc_label = QLabel("Deskripsi & Fitur Utama Produk:")
        desc_label_layout.addWidget(desc_label)
        
        desc_label_layout.addStretch()
        
        self.btn_edit_desc_modal = QPushButton("🔍 Sunting di Modal")
        self.btn_edit_desc_modal.setStyleSheet(
            "background-color: #18181b; border: 1px solid #27272a; color: #a1a1aa; "
            "padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500;"
        )
        self.btn_edit_desc_modal.setCursor(Qt.PointingHandCursor)
        self.btn_edit_desc_modal.clicked.connect(self.open_product_desc_modal)
        desc_label_layout.addWidget(self.btn_edit_desc_modal)
        
        left_layout.addLayout(desc_label_layout)
        
        self.product_desc_input = QTextEdit(
            "Mencegah daun keriting, tanaman kerdil, dan daun layu kuning akibat infeksi virus kuning pembawa hama kutu. "
            "Mengandung asam amino esensial pelindung dinding sel."
        )
        self.product_desc_input.setMaximumHeight(80)
        left_layout.addWidget(self.product_desc_input)
        
        # 3. Kategori Kustom Dinamis Grid Manager
        left_layout.addWidget(QLabel("Video Content Plan & Frameworks:"))
        self.category_table = QTableWidget(3, 3)
        self.category_table.setHorizontalHeaderLabels(["Kategori", "Jumlah Video", "Copywriting Framework"])
        self.category_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # Sembunyikan vertical headers (nomor baris kaku) agar clean dan premium
        self.category_table.verticalHeader().setVisible(False)
        self.category_table.verticalHeader().setDefaultSectionSize(40) # Tinggi baris lega 40px
        self.category_table.setMinimumHeight(180)
        self.category_table.setMaximumHeight(260)
        
        # Isi data bawaan agar mudah
        default_categories = [
            ("Promo", "4", "AIDA"),
            ("Edukasi", "4", "FAB"),
            ("Review", "4", "PAS")
        ]
        for row, (cat, qty, fw) in enumerate(default_categories):
            self.category_table.setItem(row, 0, QTableWidgetItem(cat))
            
            # Gunakan QSpinBox untuk input kuantitas yang lebih intuitif & aman
            qty_spin = QSpinBox()
            qty_spin.setRange(1, 50)
            qty_spin.setValue(int(qty))
            qty_spin.setStyleSheet("margin: 2px; padding: 2px;")
            self.category_table.setCellWidget(row, 1, qty_spin)
            
            # Framework selector combobox
            fw_cb = QComboBox()
            fw_cb.addItems(["AIDA", "PAS", "FAB", "BAB", "TikTok Hook"])
            fw_cb.setCurrentText(fw)
            fw_cb.setStyleSheet("margin: 2px; padding: 2px;")
            self.category_table.setCellWidget(row, 2, fw_cb)
            
        left_layout.addWidget(self.category_table)
        
        # Tambah & Hapus Kategori Kustom
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ Add Category")
        btn_add.clicked.connect(self.add_custom_category_row)
        btn_layout.addWidget(btn_add)
        
        btn_del = QPushButton("❌ Remove Category")
        btn_del.setObjectName("danger_button")
        btn_del.clicked.connect(self.delete_category_row)
        btn_layout.addWidget(btn_del)
        left_layout.addLayout(btn_layout)
        
        # Button Generate & Load
        btn_gen_layout = QHBoxLayout()
        
        btn_gen = QPushButton("🚀 Generate AI Scripts")
        btn_gen.setObjectName("gradient_button")
        btn_gen.clicked.connect(self.generate_naskah_via_ai)
        btn_gen_layout.addWidget(btn_gen)
        
        left_layout.addLayout(btn_gen_layout)
        
        splitter.addWidget(left_panel)
        
        # Panel Kanan: Preview Hasil
        right_panel = QFrame()
        right_panel.setObjectName("glass_card")
        right_layout = QVBoxLayout(right_panel)
        
        lbl_r = QLabel("AI GENERATED DRAFTS (PREVIEW)")
        lbl_r.setObjectName("section_title")
        right_layout.addWidget(lbl_r)
        
        self.ai_draft_table = QTableWidget(0, 4)
        self.ai_draft_table.setHorizontalHeaderLabels(["ID", "Kategori", "Produk", "Naskah Video"])
        self.ai_draft_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.ai_draft_table.verticalHeader().setVisible(False)
        self.ai_draft_table.verticalHeader().setDefaultSectionSize(40)
        self.ai_draft_table.setEditTriggers(QTableWidget.NoEditTriggers) # Disable standard inline editing!
        self.ai_draft_table.cellDoubleClicked.connect(self.open_draft_script_editor) # Double click modal editor!
        right_layout.addWidget(self.ai_draft_table)
        
        # Action Buttons for applying drafts
        action_layout = QHBoxLayout()
        
        btn_insert = QPushButton("➕ Insert Drafts (Append)")
        btn_insert.setStyleSheet("background-color: #1e3a8a; border: 1px solid #3b82f6; color: #dbeafe; font-weight: bold;")
        btn_insert.clicked.connect(self.append_ai_drafts_to_master)
        action_layout.addWidget(btn_insert)
        
        btn_replace = QPushButton("🔄 Replace Master Grid (Overwrite)")
        btn_replace.setStyleSheet("background-color: #7f1d1d; border: 1px solid #f87171; color: #fee2e2; font-weight: bold;")
        btn_replace.clicked.connect(self.replace_master_with_ai_drafts)
        action_layout.addWidget(btn_replace)
        
        right_layout.addLayout(action_layout)
        
        splitter.addWidget(right_panel)
        
        self.tabs.addWidget(tab)
        
    def add_custom_category_row(self):
        row = self.category_table.rowCount()
        self.category_table.insertRow(row)
        self.category_table.setItem(row, 0, QTableWidgetItem("Kustom"))
        
        qty_spin = QSpinBox()
        qty_spin.setRange(1, 50)
        qty_spin.setValue(3)
        qty_spin.setStyleSheet("margin: 2px; padding: 2px;")
        self.category_table.setCellWidget(row, 1, qty_spin)
        
        fw_cb = QComboBox()
        fw_cb.addItems(["AIDA", "PAS", "FAB", "BAB", "TikTok Hook"])
        fw_cb.setStyleSheet("margin: 2px; padding: 2px;")
        self.category_table.setCellWidget(row, 2, fw_cb)
        
    def delete_category_row(self):
        cur_row = self.category_table.currentRow()
        if cur_row != -1:
            self.category_table.removeRow(cur_row)
            
    def toggle_ai_engine_inputs(self):
        engine = self.engine_selector.currentText()
        self.model_selector.clear()
        
        if engine == "Gemini API (Flash)":
            self.api_key_label.show()
            self.api_key_input.show()
            self.model_selector.addItems([
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-2.0-flash-exp"
            ])
        elif engine == "OpenRouter API":
            self.api_key_label.show()
            self.api_key_input.show()
            self.model_selector.addItems([
                "deepseek/deepseek-r1:free",
                "meta-llama/llama-3.3-70b-instruct:free",
                "google/gemini-2.5-flash",
                "google/gemini-flash-1.5",
                "meta-llama/llama-3-8b-instruct:free",
                "qwen/qwen-2.5-72b-instruct:free",
                "mistralai/mistral-7b-instruct:free",
                "deepseek/deepseek-chat"
            ])
        else: # Ollama lokal
            self.api_key_label.hide()
            self.api_key_input.hide()
            self.detect_ollama_local()
            
    def detect_ollama_local(self):
        # Scan otomatis tags Ollama
        models = ai_generator.get_ollama_models()
        self.model_selector.clear()
        if models:
            self.model_selector.addItems(models)
        else:
            self.model_selector.addItems(["Ollama Tidak Aktif (Aktifkan Ollama!)"])
            
    def generate_naskah_via_ai(self):
        engine = self.engine_selector.currentText()
        model_name = self.model_selector.currentText()
        product_name = self.product_name_input.text()
        product_desc = self.product_desc_input.toPlainText()
        
        # Kumpulkan kategori kustom dinamis
        categories = []
        for row in range(self.category_table.rowCount()):
            name_item = self.category_table.item(row, 0)
            qty_widget = self.category_table.cellWidget(row, 1)
            fw_widget = self.category_table.cellWidget(row, 2)
            
            if name_item and qty_widget and fw_widget:
                try:
                    categories.append({
                        "name": name_item.text(),
                        "count": qty_widget.value() if hasattr(qty_widget, "value") else int(self.category_table.item(row, 1).text()),
                        "framework": fw_widget.currentText()
                    })
                except ValueError:
                    pass
                    
        if not categories:
            QMessageBox.warning(self, "Warning", "Harap tentukan minimal satu baris kategori dan jumlah video!")
            return
            
        self.ai_draft_table.setRowCount(0)
        
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            if engine == "Gemini API (Flash)":
                api_key = self.api_key_input.text().strip()
                if not api_key: raise Exception("API Key Gemini wajib diisi!")
                self.ai_drafts_list = ai_generator.generate_scripts_gemini(api_key, model_name, product_name, product_desc, categories)
            elif engine == "OpenRouter API":
                api_key = self.api_key_input.text().strip()
                if not api_key: raise Exception("API Key OpenRouter wajib diisi!")
                self.ai_drafts_list = ai_generator.generate_scripts_openrouter(api_key, model_name, product_name, product_desc, categories)
            else: # Ollama lokal
                if model_name.startswith("Ollama Tidak Aktif"): raise Exception("Ollama tidak terdeteksi berjalan lokal!")
                self.ai_drafts_list = ai_generator.generate_scripts_ollama(model_name, product_name, product_desc, categories)
                
            QApplication.restoreOverrideCursor()
            
            # Tampilkan ke Grid Tabel Draf Kanan
            self.ai_draft_table.setRowCount(len(self.ai_drafts_list))
            for r, script in enumerate(self.ai_drafts_list):
                self.ai_draft_table.setItem(r, 0, QTableWidgetItem(str(script["id"])))
                self.ai_draft_table.setItem(r, 1, QTableWidgetItem(script["category"]))
                self.ai_draft_table.setItem(r, 2, QTableWidgetItem(script["product"]))
                self.ai_draft_table.setItem(r, 3, QTableWidgetItem(script["naskah"]))
                
            QMessageBox.information(self, "Success", f"Berhasil generate {len(self.ai_drafts_list)} naskah draf promosi dengan AI! Silakan pilih untuk Append atau Overwrite ke Script Manager.")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error", f"Generate naskah gagal: {str(e)}")

    # ==========================================
    # TAB 3: RVC PARAMETERS
    # ==========================================
    def init_tab_rvc_parameters(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title = QLabel("RVC INFERENCE SETTINGS")
        title.setObjectName("section_title")
        layout.addWidget(title)
        
        card = QFrame()
        card.setObjectName("glass_card")
        card_layout = QVBoxLayout(card)
        
        # Pemilih model RVC (.pth)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("RVC Model Weights (.pth):"))
        self.rvc_pth_combo = QComboBox()
        row1.addWidget(self.rvc_pth_combo)
        btn_pth = QPushButton("Browse .pth")
        btn_pth.clicked.connect(self.browse_pth)
        row1.addWidget(btn_pth)
        card_layout.addLayout(row1)
        
        # Pemilih index RVC (.index)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("RVC Index File (.index):"))
        self.rvc_index_combo = QComboBox()
        row2.addWidget(self.rvc_index_combo)
        btn_idx = QPushButton("Browse .index")
        btn_idx.clicked.connect(self.browse_index)
        row2.addWidget(btn_idx)
        card_layout.addLayout(row2)
        
        # Sliders parameters
        card_layout.addWidget(QLabel("Pitch Shift (f0up_key):"))
        self.pitch_slider = QSlider(Qt.Horizontal)
        self.pitch_slider.setRange(-12, 12)
        self.pitch_slider.setValue(6)
        self.pitch_label = QLabel("f0up_key: +6 (Voice Pitch Shift)")
        self.pitch_slider.valueChanged.connect(self.update_pitch_label)
        card_layout.addWidget(self.pitch_slider)
        card_layout.addWidget(self.pitch_label)
        
        card_layout.addWidget(QLabel("Index Rate (Voice Influence):"))
        self.index_slider = QDoubleSpinBox()
        self.index_slider.setRange(0.0, 1.0)
        self.index_slider.setSingleStep(0.05)
        self.index_slider.setValue(0.20)
        card_layout.addWidget(self.index_slider)
        
        layout.addWidget(card)
        layout.addStretch()
        self.tabs.addWidget(tab)
        
    def scan_local_rvc_models(self):
        # Scan otomatis folder RVC
        pth_files = glob.glob(os.path.join(self.rvc_dir, "**/*.pth"), recursive=True)
        idx_files = glob.glob(os.path.join(self.rvc_dir, "**/*.index"), recursive=True)
        
        self.rvc_pth_combo.clear()
        self.rvc_index_combo.clear()
        
        self.rvc_pth_combo.addItems(pth_files)
        self.rvc_index_combo.addItems(idx_files)
        
    def browse_pth(self):
        f, _ = QFileDialog.getOpenFileName(self, "Pilih File .pth", self.rvc_dir, "Weights (*.pth)")
        if f:
            self.rvc_pth_combo.addItem(f)
            self.rvc_pth_combo.setCurrentText(f)
            
    def browse_index(self):
        f, _ = QFileDialog.getOpenFileName(self, "Pilih File .index", self.rvc_dir, "Index (*.index)")
        if f:
            self.rvc_index_combo.addItem(f)
            self.rvc_index_combo.setCurrentText(f)
            
    def update_pitch_label(self, val):
        self.pitch_label.setText(f"f0up_key: {val:+d} (Voice Pitch Shift)")

    # ==========================================
    # TAB 4: VISUAL LAYOUT EDITOR
    # ==========================================
    def init_tab_layout_editor(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Panel Kiri: Form Setelan
        settings_panel = QFrame()
        settings_panel.setObjectName("glass_card")
        set_layout = QVBoxLayout(settings_panel)
        
        title = QLabel("LAYOUT & BRANDING")
        title.setObjectName("section_title")
        set_layout.addWidget(title)
        
        # Font selector
        set_layout.addWidget(QLabel("Font Subtitle (.ttf):"))
        self.font_combo = QComboBox()
        fonts = glob.glob(os.path.join(self.fonts_dir, "*.ttf"))
        self.font_combo.addItems(fonts)
        set_layout.addWidget(self.font_combo)
        
        # Subtitle Color
        set_layout.addWidget(QLabel("Warna Subtitle (Color):"))
        self.subtitle_color_combo = QComboBox()
        self.subtitle_color_combo.addItems(["Kuning Cerah", "Putih Bersih", "Hijau Neon", "Cyan Elektrik"])
        self.subtitle_color_combo.currentIndexChanged.connect(self.update_subtitle_preview)
        set_layout.addWidget(self.subtitle_color_combo)
        
        # Subtitle Font Size
        set_layout.addWidget(QLabel("Ukuran Font (Size):"))
        self.subtitle_size_spin = QSpinBox()
        self.subtitle_size_spin.setRange(20, 100)
        self.subtitle_size_spin.setValue(56)
        self.subtitle_size_spin.valueChanged.connect(self.update_subtitle_preview)
        set_layout.addWidget(self.subtitle_size_spin)
        
        # Subtitle Stroke Width
        set_layout.addWidget(QLabel("Tebal Stroke (Outline):"))
        self.subtitle_stroke_spin = QSpinBox()
        self.subtitle_stroke_spin.setRange(0, 20)
        self.subtitle_stroke_spin.setValue(6)
        self.subtitle_stroke_spin.valueChanged.connect(self.update_subtitle_preview)
        set_layout.addWidget(self.subtitle_stroke_spin)
        
        # Subtitle Vertical Position
        self.subtitle_pos_label = QLabel("Tinggi Subtitle (Vertical Pos): 74%")
        set_layout.addWidget(self.subtitle_pos_label)
        self.subtitle_pos_slider = QSlider(Qt.Horizontal)
        self.subtitle_pos_slider.setRange(50, 90)
        self.subtitle_pos_slider.setValue(74)
        self.subtitle_pos_slider.valueChanged.connect(self.update_sub_pos_label)
        set_layout.addWidget(self.subtitle_pos_slider)
        
        # Watermark logo
        set_layout.addWidget(QLabel("Logo Watermark (PNG):"))
        watermark_layout = QHBoxLayout()
        self.watermark_input = QLineEdit()
        self.watermark_input.textChanged.connect(self.update_logo_preview)
        watermark_layout.addWidget(self.watermark_input)
        btn_wt = QPushButton("Browse Image")
        btn_wt.clicked.connect(self.browse_watermark)
        watermark_layout.addWidget(btn_wt)
        set_layout.addLayout(watermark_layout)
        
        # Opacity watermark
        set_layout.addWidget(QLabel("Logo Opacity:"))
        self.opacity_slider = QDoubleSpinBox()
        self.opacity_slider.setRange(0.0, 1.0)
        self.opacity_slider.setValue(0.7)
        self.opacity_slider.setSingleStep(0.1)
        self.opacity_slider.valueChanged.connect(self.update_logo_preview)
        set_layout.addWidget(self.opacity_slider)
        
        # Watermark Size
        set_layout.addWidget(QLabel("Ukuran Logo Watermark (Lebar px):"))
        self.watermark_size_spin = QSpinBox()
        self.watermark_size_spin.setRange(50, 500)
        self.watermark_size_spin.setValue(150)
        self.watermark_size_spin.setSingleStep(10)
        self.watermark_size_spin.valueChanged.connect(self.update_logo_preview)
        set_layout.addWidget(self.watermark_size_spin)
        
        # BGM volume
        set_layout.addWidget(QLabel("Volume Backsound (BGM):"))
        self.bgm_vol_spin = QDoubleSpinBox()
        self.bgm_vol_spin.setRange(0.0, 0.5)
        self.bgm_vol_spin.setValue(0.08)
        self.bgm_vol_spin.setSingleStep(0.02)
        set_layout.addWidget(self.bgm_vol_spin)
        
        # Video Transitions
        set_layout.addWidget(QLabel("Transition Effect:"))
        self.transition_combo = QComboBox()
        self.transition_combo.addItems(["None", "Fade In/Out", "CrossFade"])
        set_layout.addWidget(self.transition_combo)
        
        # Max B-roll duration limit
        set_layout.addSpacing(10)
        self.limit_to_3s_checkbox = QCheckBox("Batasi Video Input Maksimal 3 Detik")
        set_layout.addWidget(self.limit_to_3s_checkbox)
        
        splitter.addWidget(settings_panel)
        
        # Panel Kanan: Canvas Simulator (9:16)
        preview_panel = QFrame()
        preview_panel.setObjectName("glass_card")
        pre_layout = QVBoxLayout(preview_panel)
        
        title_p = QLabel("9:16 PORTRAIT SIMULATOR")
        title_p.setObjectName("section_title")
        pre_layout.addWidget(title_p)
        
        # Visual simulator menggunakan absolute positioning
        self.phone_simulator = QFrame()
        self.phone_simulator.setFixedSize(280, 480)
        self.phone_simulator.setStyleSheet(
            "background-color: #09090b; border: 2px solid #27272a; border-radius: 24px;"
        )
        
        # Gunakan layout untuk menempatkan simulator secara rapi di tengah
        sim_outer = QHBoxLayout()
        sim_outer.addStretch()
        sim_outer.addWidget(self.phone_simulator)
        sim_outer.addStretch()
        pre_layout.addLayout(sim_outer)
        
        # DUMMY LOGO
        self.dummy_logo = QLabel("[LOGO WATERMARK]", self.phone_simulator)
        self.dummy_logo.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.dummy_logo.setGeometry(120, 20, 140, 30)
        self.dummy_logo.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 10px; font-weight: bold; background: transparent;")
        
        # DUMMY SUBTITLE
        self.dummy_subtitle = QLabel("PERAWATAN CABAI\nBEBAS HAMA!", self.phone_simulator)
        self.dummy_subtitle.setAlignment(Qt.AlignCenter)
        self.dummy_subtitle.setGeometry(20, 330, 240, 60)
        
        # Trigger update pertama
        self.update_subtitle_preview()
        self.update_logo_preview()
        
        splitter.addWidget(preview_panel)
        
        self.tabs.addWidget(tab)
        
    def update_sub_pos_label(self, val):
        self.subtitle_pos_label.setText(f"Posisi Vertikal Subtitle: {val}% dari atas")
        self.update_subtitle_preview()
        
    def update_subtitle_preview(self):
        color_map = {
            "Kuning Cerah": "#ffff00",
            "Putih Bersih": "#ffffff",
            "Hijau Neon": "#39ff14",
            "Cyan Elektrik": "#00ffff"
        }
        chosen_color = color_map.get(self.subtitle_color_combo.currentText(), "#ffff00")
        font_size = max(10, self.subtitle_size_spin.value() // 4)
        
        self.dummy_subtitle.setStyleSheet(
            f"color: {chosen_color}; font-size: {font_size}px; font-weight: bold; background: transparent; "
            f"border: 1px solid rgba(255,255,255,0.15); border-radius: 4px; padding: 4px;"
        )
        
        # Update vertical position
        pos_pct = self.subtitle_pos_slider.value()
        y_center = int(480 * (pos_pct / 100.0))
        y = y_center - 30 # 30 is half of the height (60)
        y = max(100, min(y, 410))
        self.dummy_subtitle.setGeometry(20, y, 240, 60)
        
    def update_logo_preview(self):
        opacity = self.opacity_slider.value()
        path = self.watermark_input.text().strip()
        
        # Update dynamic size on simulator
        final_size = self.watermark_size_spin.value() if hasattr(self, "watermark_size_spin") else 150
        sim_w = int(final_size * (280.0 / 1080.0))
        sim_w = max(60, min(sim_w, 200)) # Keep placeholder readable
        x_pos = 280 - sim_w - 20
        self.dummy_logo.setGeometry(x_pos, 20, sim_w, 30)
        
        if path and os.path.exists(path):
            self.dummy_logo.setStyleSheet(
                f"color: rgba(16, 185, 129, {opacity}); font-size: 10px; font-weight: bold; "
                f"border: 1px dashed rgba(16,185,129,0.3); padding: 4px; background: transparent;"
            )
            self.dummy_logo.setText("📷 [LOGO WATERMARK]")
        else:
            self.dummy_logo.setStyleSheet(f"color: rgba(255,255,255,{opacity * 0.7}); font-size: 10px; font-weight: bold; background: transparent;")
            self.dummy_logo.setText("[LOGO WATERMARK]")
            
    def browse_watermark(self):
        f, _ = QFileDialog.getOpenFileName(self, "Pilih Logo", self.video_input, "Logo (*.png *.jpg)")
        if f:
            self.watermark_input.setText(f)
            
    # ==========================================
    # TAB 5: RVC VOICE TRAINER
    # ==========================================
    def init_tab_rvc_trainer(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title = QLabel("🎤 RVC CUSTOM VOICE TRAINER")
        title.setObjectName("section_title")
        layout.addWidget(title)
        
        card = QFrame()
        card.setObjectName("glass_card")
        card_layout = QVBoxLayout(card)
        
        card_layout.addWidget(QLabel("Upload Dataset Rekaman Suara (Format WAV/MP3, durasi 5-10 menit):"))
        row1 = QHBoxLayout()
        self.dataset_input = QLineEdit()
        row1.addWidget(self.dataset_input)
        btn_ds = QPushButton("Browse Audio")
        btn_ds.clicked.connect(self.browse_dataset_audio)
        row1.addWidget(btn_ds)
        card_layout.addLayout(row1)
        
        # local GPU or Colab
        card_layout.addWidget(QLabel("Opsi Pelatihan Model Suara (Voice Training Settings):"))
        
        btn_colab = QPushButton("☁️ Export Dataset & Train on Google Colab (Free & Fast)")
        btn_colab.setObjectName("gradient_button")
        btn_colab.clicked.connect(self.open_google_colab_rvc)
        card_layout.addWidget(btn_colab)
        
        lbl_info = QLabel(
            "Note: Google Colab melatih model suara kustom Anda hanya dalam waktu 15 menit menggunakan GPU Awan.\n"
            "Setelah file .pth dan .index jadi, cukup letakkan ke folder RVC/ untuk langsung digunakan."
        )
        lbl_info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        card_layout.addWidget(lbl_info)
        
        layout.addWidget(card)
        layout.addStretch()
        self.tabs.addWidget(tab)
        
    def browse_dataset_audio(self):
        f, _ = QFileDialog.getOpenFileName(self, "Pilih File Rekaman", self.base_dir, "Audio (*.wav *.mp3)")
        if f:
            self.dataset_input.setText(f)
            
    def open_google_colab_rvc(self):
        import webbrowser
        # Buka Google Colaboratory langsung dengan file yang ter-link ke GitHub Anda!
        colab_url = "https://colab.research.google.com/github/brillianodhiya/AutoVideo-RVC/blob/main/RVC_Colab_Trainer.ipynb"
        webbrowser.open(colab_url)
        QMessageBox.information(
            self, "Cloud Trainer Instan Aktif! ☁️", 
            "Luar biasa! Kami baru saja membuka berkas notebook Google Colab kustom Anda langsung dari GitHub:\n\n"
            "🌐 RVC_Colab_Trainer.ipynb (AutoVideo-RVC)\n\n"
            "Langkah Penggunaan:\n"
            "1. Browser Anda baru saja membuka notebook Colab kustom Anda secara instan.\n"
            "2. Cukup jalankan sel (Step 1, Step 2, Step 3, Step 4) secara berurutan.\n"
            "3. Mekanisme 'Auto-Repair' dan 'Triple-Redundancy' kustom kita akan menangani semua instalasi secara instan tanpa error!"
        )

    # ==========================================
    # TAB 6: BATCH RENDERER (Engine Compositor)
    # ==========================================
    def init_tab_renderer(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title = QLabel("AI BATCH VIDEO COMPOSITOR & RENDERING QUEUE")
        title.setObjectName("section_title")
        layout.addWidget(title)
        
        # Horizontal layout for rendering controls
        render_ctrl_layout = QHBoxLayout()
        
        # Start button
        self.btn_render = QPushButton("🚀 LAUNCH BATCH RENDERING PROCESS")
        self.btn_render.setObjectName("gradient_button")
        self.btn_render.setStyleSheet("font-size: 13px; padding: 10px; font-weight: 600;")
        self.btn_render.clicked.connect(self.trigger_batch_rendering)
        render_ctrl_layout.addWidget(self.btn_render, stretch=3)
        
        # Pause/Resume button
        self.btn_pause = QPushButton("⏸️ PAUSE")
        self.btn_pause.setStyleSheet(
            "background-color: #18181b; border: 1px solid #27272a; color: #a1a1aa; "
            "padding: 10px; border-radius: 6px; font-weight: 600;"
        )
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.toggle_pause_rendering)
        render_ctrl_layout.addWidget(self.btn_pause, stretch=1)
        
        # Stop button
        self.btn_stop = QPushButton("🛑 STOP")
        self.btn_stop.setObjectName("danger_button")
        self.btn_stop.setStyleSheet("font-weight: 600; padding: 10px;")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_rendering)
        render_ctrl_layout.addWidget(self.btn_stop, stretch=1)
        
        layout.addLayout(render_ctrl_layout)
        
        # Overall Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Retro Terminal Console Log
        layout.addWidget(QLabel("Live System Console Log:"))
        self.console_log = QTextEdit()
        self.console_log.setReadOnly(True)
        self.console_log.setObjectName("console_card")
        self.console_log.setStyleSheet(
            "background-color: #09090b; color: #34d399; border: 1px solid #27272a; "
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; border-radius: 6px;"
        )
        layout.addWidget(self.console_log)
        
        self.tabs.addWidget(tab)
        
    def append_log(self, text):
        self.console_log.append(text)
        # Scroll otomatis ke bawah
        self.console_log.verticalScrollBar().setValue(self.console_log.verticalScrollBar().maximum())
        
    def trigger_batch_rendering(self):
        if not self.scripts_list:
            QMessageBox.warning(self, "Warning", "Harap generate naskah pemasaran menggunakan AI terlebih dahulu di Tab 'AI Writer'!")
            return
            
        # Matikan tombol saat proses berjalan, aktifkan kontrol pause/stop
        self.btn_render.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("⏸️ PAUSE")
        self.btn_stop.setEnabled(True)
        
        self.progress_bar.setValue(0)
        self.console_log.clear()
        
        # Kumpulkan parameter dari GUI
        rvc_params = {
            "model_path": self.rvc_pth_combo.currentText(),
            "index_path": self.rvc_index_combo.currentText(),
            "f0up_key": self.pitch_slider.value(),
            "index_rate": self.index_slider.value()
        }
        
        layout_params = {
            "font_path": self.font_combo.currentText(),
            "watermark_path": self.watermark_input.text(),
            "watermark_opacity": self.opacity_slider.value(),
            "watermark_size": self.watermark_size_spin.value() if hasattr(self, "watermark_size_spin") else 150,
            "bgm_volume": self.bgm_vol_spin.value(),
            "transition": self.transition_combo.currentText(),
            "subtitle_color": self.subtitle_color_combo.currentText(),
            "subtitle_size": self.subtitle_size_spin.value(),
            "subtitle_stroke": self.subtitle_stroke_spin.value(),
            "subtitle_pos": self.subtitle_pos_slider.value(),
            "limit_to_3s": self.limit_to_3s_checkbox.isChecked()
        }
        
        folders_config = {
            "video_input": self.video_input,
            "music_input": self.music_input,
            "fonts": self.fonts_dir,
            "output": self.output_dir
        }
        
        # Jalankan background worker QThread
        self.thread = RenderWorker(self.scripts_list, rvc_params, layout_params, folders_config)
        self.thread.progress_signal.connect(self.update_render_progress)
        self.thread.status_signal.connect(self.append_log)
        self.thread.finished_signal.connect(self.render_finished_handler)
        self.thread.start()
        
    def toggle_pause_rendering(self):
        if hasattr(self, "thread") and self.thread.isRunning():
            if self.thread._is_paused:
                self.thread.resume()
                self.btn_pause.setText("⏸️ PAUSE")
                self.append_log("\n[INFO] Rendering dilanjutkan (RESUMED)...")
            else:
                self.thread.pause()
                self.btn_pause.setText("▶️ RESUME")
                self.append_log("\n[INFO] Rendering ditangguhkan (PAUSED). Menunggu siklus video saat ini selesai...")
                
    def stop_rendering(self):
        if hasattr(self, "thread") and self.thread.isRunning():
            reply = QMessageBox.question(
                self, 
                "Konfirmasi Stop", 
                "Apakah Anda yakin ingin menghentikan seluruh proses rendering massal?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.append_log("\n[WARNING] Menghentikan proses rendering... Menutup file dan membersihkan temporary cache...")
                self.thread.stop()
                self.btn_stop.setEnabled(False)
                self.btn_pause.setEnabled(False)
        
    def update_render_progress(self, current, total):
        pct = int((current / total) * 100)
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"Memproses Video {current} dari {total} ({pct}%)")
        
    def render_finished_handler(self, success, message):
        self.btn_render.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("⏸️ PAUSE")
        self.btn_stop.setEnabled(False)
        
        if success:
            self.progress_bar.setValue(100)
            self.append_log("\n" + "="*50 + "\n[SUCCESS] SELURUH PROSES RENDERING SELESAI SEPENUHNYA!\n" + "="*50)
            QMessageBox.information(self, "Ekspor Selesai", "Seluruh video dalam antrean berhasil diekspor dengan sukses!")
        else:
            if "dihentikan oleh pengguna" in message:
                self.append_log(f"\n[INFO] Rendering dihentikan secara aman oleh pengguna. Semua file dan resources ditutup secara bersih.")
                QMessageBox.information(self, "Stopped", "Proses rendering telah dihentikan secara aman.")
            else:
                self.append_log(f"\n[ERROR] Rendering terputus akibat kesalahan: {message}")
                QMessageBox.critical(self, "Error", f"Proses rendering terputus: {message}")

# ==========================================
# 3. APPLICATION ENTRY POINT
# ==========================================
def main():
    app = QApplication(sys.argv)
    
    # Atur font global aplikasi agar premium
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
