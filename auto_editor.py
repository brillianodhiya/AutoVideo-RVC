import edge_tts
import os
import sys
import glob
import random
import re
import asyncio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Load moviepy 2.x direct imports
try:
    from moviepy import (
        VideoFileClip, 
        AudioFileClip, 
        CompositeAudioClip, 
        concatenate_videoclips, 
        ImageClip, 
        CompositeVideoClip
    )
    from moviepy.audio.fx import AudioLoop
except ImportError as e:
    print(f"[WARNING] MoviePy 2.x import failed: {str(e)}")
    print("Silakan instal dependensi terlebih dahulu menggunakan:")
    print("pip install moviepy edge-tts Pillow numpy\n")

# ==========================================
# 1. KONFIGURASI & STRUKTUR FOLDER
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_INPUT_DIR = os.path.join(BASE_DIR, "video_input")
GAMBAR_INPUT_DIR = os.path.join(BASE_DIR, "gambar_input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")

# Suara Default Bahasa Indonesia (Edge-TTS)
DEFAULT_VOICE = "id-ID-GadisNeural" # Suara perempuan premium alami

# ==========================================
# 2. INISIALISASI FOLDER
# ==========================================
def inisialisasi_folder():
    for folder in [VIDEO_INPUT_DIR, GAMBAR_INPUT_DIR, OUTPUT_DIR, FONTS_DIR]:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"[INFO] Membuat folder: {folder}")
            
    # Buat file naskah contoh jika belum ada
    naskah_path = os.path.join(BASE_DIR, "input_naskah.txt")
    if not os.path.exists(naskah_path):
        contoh_naskah = (
            "Halo! Kamu bosan dengan kerjaan editing video yang memakan waktu berjam-jam?\n"
            "Sekarang, ada solusi otomatisasi video pintar menggunakan Python!\n"
            "Cukup masukkan naskah, letakkan klip mentah, dan biarkan komputer bekerja untukmu.\n"
            "Kerja lebih cepat, hasil tetap profesional, dan waktu luangmu jadi lebih banyak!"
        )
        with open(naskah_path, "w", encoding="utf-8") as f:
            f.write(contoh_naskah)
        print(f"[INFO] Membuat contoh file naskah: {naskah_path}")

# ==========================================
# 3. GENERATE VOICEOVER & SUBTITLE (EDGE-TTS)
# ==========================================
async def generate_voiceover_and_vtt(text, voice, audio_out, vtt_out):
    print(f"[INFO] Menghasilkan Voiceover menggunakan suara: {voice}...")
    communicate = edge_tts.Communicate(text, voice, rate="+20%", boundary="WordBoundary")
    submaker = edge_tts.SubMaker()
    
    with open(audio_out, "wb") as fp:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
                
    with open(vtt_out, "w", encoding="utf-8") as fp:
        fp.write(submaker.get_srt())
    print("[SUCCESS] Voiceover dan Subtitle WebVTT berhasil dibuat!")

# ==========================================
# 4. PARSER WEBVTT (SUBTITLE TIME DECODER)
# ==========================================
def parse_time(time_str):
    # Standardize commas to periods (SRT uses commas, VTT uses periods)
    time_str = time_str.replace(",", ".")
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
    else:
        h = 0
        m, s = parts
    s_parts = s.split(".")
    sec = int(s_parts[0])
    milli = int(s_parts[1]) if len(s_parts) > 1 else 0
    return int(h) * 3600 + int(m) * 60 + sec + milli / 1000.0

def parse_vtt(vtt_path):
    subs = []
    with open(vtt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    current_time = None
    current_text = []
    
    for line in lines:
        line = line.strip()
        if not line or line == "WEBVTT":
            continue
        # Skip numeric index lines in SRT (like "1", "2")
        if line.isdigit():
            continue
        
        if "-->" in line:
            if current_time and current_text:
                subs.append((current_time[0], current_time[1], " ".join(current_text)))
                current_text = []
            parts = line.split("-->")
            start = parse_time(parts[0].strip())
            end = parse_time(parts[1].strip())
            current_time = (start, end)
        elif current_time:
            clean_line = re.sub(r'<[^>]*>', '', line)
            if clean_line:
                current_text.append(clean_line)
                
    if current_time and current_text:
        subs.append((current_time[0], current_time[1], " ".join(current_text)))
        
    return subs

def kelompokkan_subtitle(subs, max_words=3, max_duration=2.0):
    grouped = []
    if not subs:
        return grouped
        
    current_start = subs[0][0]
    current_end = subs[0][1]
    current_words = subs[0][2].split()
    
    for i in range(1, len(subs)):
        start, end, text = subs[i]
        words = text.split()
        
        if len(current_words) + len(words) <= max_words and (end - current_start) <= max_duration:
            current_end = end
            current_words.extend(words)
        else:
            grouped.append((current_start, current_end, " ".join(current_words)))
            current_start = start
            current_end = end
            current_words = words
            
    grouped.append((current_start, current_end, " ".join(current_words)))
    return grouped

# ==========================================
# 5. RENDER SUBTITLE KE GAMBAR TRANSPARAN (PILLOW)
# ==========================================
def dapatkan_font_path():
    custom_fonts = glob.glob(os.path.join(FONTS_DIR, "*.ttf"))
    if custom_fonts:
        return custom_fonts[0]
        
    windows_fonts = [
        "C:\\Windows\\Fonts\\arialbd.ttf",   # Arial Bold
        "C:\\Windows\\Fonts\\tahomabd.ttf",  # Tahoma Bold
        "C:\\Windows\\Fonts\\impact.ttf"      # Impact
    ]
    for font_path in windows_fonts:
        if os.path.exists(font_path):
            return font_path
            
    return None

def wrap_text(text, font, max_width):
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = " ".join(current_line + [word])
        dummy_img = Image.new("RGBA", (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        if hasattr(dummy_draw, "textbbox"):
            bbox = dummy_draw.textbbox((0, 0), test_line, font=font)
            line_w = bbox[2] - bbox[0]
        else:
            line_w, _ = dummy_draw.textsize(test_line, font=font)
            
        if line_w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            
    if current_line:
        lines.append(" ".join(current_line))
    return lines

def buat_subtitle_overlay_clip(subs, video_w, video_h):
    font_path = dapatkan_font_path()
    font_size = int(video_w * 0.052) # 5.2% dari lebar video
    
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()
        
    overlay_clips = []
    
    for start, end, text in subs:
        img = Image.new("RGBA", (video_w, video_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        text = text.upper()
        
        # Batasi lebar teks maksimum 82% dari lebar video agar tidak tembus pinggir
        max_text_width = int(video_w * 0.82)
        lines = wrap_text(text, font, max_text_width)
        
        # Hitung tinggi setiap baris dan total tinggi paragraf
        line_heights = []
        for line in lines:
            if hasattr(draw, "textbbox"):
                bbox = draw.textbbox((0, 0), line, font=font)
                line_h = bbox[3] - bbox[1]
            else:
                _, line_h = draw.textsize(line, font=font)
            line_heights.append(line_h)
            
        line_spacing = int(font_size * 0.2)
        total_h = sum(line_heights) + (len(lines) - 1) * line_spacing
        
        # Posisikan center secara vertikal di 74% tinggi video
        current_y = int(video_h * 0.74) - (total_h // 2)
        
        for idx_line, line in enumerate(lines):
            if hasattr(draw, "textbbox"):
                bbox = draw.textbbox((0, 0), line, font=font)
                line_w = bbox[2] - bbox[0]
                line_h = bbox[3] - bbox[1]
            else:
                line_w, line_h = draw.textsize(line, font=font)
                
            x = (video_w - line_w) // 2
            
            # Draw stroke/outline
            draw.text(
                (x, current_y), 
                line, 
                font=font, 
                fill=(255, 255, 0, 255), # Kuning cerah
                stroke_width=int(font_size * 0.12), 
                stroke_fill=(0, 0, 0, 255)
            )
            current_y += line_h + line_spacing
        
        rgba_np = np.array(img)
        rgb_np = rgba_np[:, :, :3]
        alpha_np = rgba_np[:, :, 3] / 255.0
        
        txt_clip = ImageClip(rgb_np).with_mask(ImageClip(alpha_np).with_is_mask(True))
        txt_clip = txt_clip.with_start(start).with_end(end)
        overlay_clips.append(txt_clip)
        
    return overlay_clips


# ==========================================
# 6. PENYUSUNAN VIDEO UTAMA (ASSEMBLY)
# ==========================================
def buat_video_assembly(target_duration, output_w, output_h, limit_to_3s=False):
    video_extensions = ["*.mp4", "*.mov", "*.avi", "*.mkv"]
    raw_video_paths = []
    for ext in video_extensions:
        raw_video_paths.extend(glob.glob(os.path.join(VIDEO_INPUT_DIR, ext)))
        raw_video_paths.extend(glob.glob(os.path.join(VIDEO_INPUT_DIR, ext.upper())))
        
    if not raw_video_paths:
        print("[ERROR] Tidak ada file video mentah di video_input/!")
        sys.exit(1)
        
    random.shuffle(raw_video_paths)
    
    clips = []
    current_duration = 0.0
    
    print(f"[INFO] Menyusun klip video mentah untuk memenuhi durasi target: {target_duration:.2f}s...")
    
    while current_duration < target_duration:
        for path in raw_video_paths:
            if current_duration >= target_duration:
                break
                
            try:
                clip = VideoFileClip(path)
                clip_duration = clip.duration
                
                min_dur = 1.5 if limit_to_3s else 3.0
                max_dur = 3.0 if limit_to_3s else 5.0
                
                # subclipped di MoviePy 2.x
                if clip_duration > (max_dur + 1.0):
                    start_time = random.uniform(1.0, clip_duration - max_dur)
                    end_time = start_time + min(random.uniform(min_dur, max_dur), target_duration - current_duration)
                    sub_clip = clip.subclipped(start_time, end_time)
                else:
                    end_time = min(clip_duration, target_duration - current_duration)
                    if limit_to_3s and end_time > 3.0:
                        end_time = 3.0
                    sub_clip = clip.subclipped(0, end_time)
                
                sub_clip = sub_clip.without_audio()
                
                # resized & cropped di MoviePy 2.x
                clip_w, clip_h = sub_clip.size
                scale = max(output_w / clip_w, output_h / clip_h)
                new_w = int(clip_w * scale)
                new_h = int(clip_h * scale)
                
                sub_clip = sub_clip.resized(new_size=(new_w, new_h))
                x1 = (new_w - output_w) // 2
                y1 = (new_h - output_h) // 2
                sub_clip = sub_clip.cropped(x1=x1, y1=y1, width=output_w, height=output_h)
                
                clips.append(sub_clip)
                current_duration += sub_clip.duration
                print(f" -> Menambahkan klip '{os.path.basename(path)}' durasi {sub_clip.duration:.2f}s")
                
            except Exception as e:
                print(f"[WARNING] Gagal memproses klip {path}: {str(e)}")
                continue
                
    return concatenate_videoclips(clips, method="compose")

# ==========================================
# 7. PROSES UTAMA (MAIN ENGINE)
# ==========================================
def main():
    inisialisasi_folder()
    
    naskah_path = os.path.join(BASE_DIR, "input_naskah.txt")
    with open(naskah_path, "r", encoding="utf-8") as f:
        naskah = f.read().strip()
        
    if not naskah:
        print("[ERROR] File 'input_naskah.txt' kosong!")
        sys.exit(1)
        
    print("\n" + "="*50)
    print("      AI AUTO-EDITOR VIDEO RUNNING (MoviePy 2.x)...")
    print("="*50)
    
    temp_audio = os.path.join(BASE_DIR, "temp_vo.mp3")
    temp_vtt = os.path.join(BASE_DIR, "temp_sub.vtt")
    
    asyncio.run(generate_voiceover_and_vtt(naskah, DEFAULT_VOICE, temp_audio, temp_vtt))
    
    vo_audio = AudioFileClip(temp_audio)
    target_duration = vo_audio.duration
    
    output_w = 1080
    output_h = 1920
    
    compiled_video = buat_video_assembly(target_duration, output_w, output_h)
    
    print("[INFO] Parsing subtitle WebVTT dan me-render text overlay...")
    raw_subs = parse_vtt(temp_vtt)
    # Tampilkan subtitle maks 2 kata per tampilan agar pas saat diucapkan (dinamika tinggi!)
    grouped_subs = kelompokkan_subtitle(raw_subs, max_words=2, max_duration=1.2)
    subtitle_clips = buat_subtitle_overlay_clip(grouped_subs, output_w, output_h)
    
    final_video = CompositeVideoClip([compiled_video] + subtitle_clips)
    
    # Audio Mixing dengan v2.x methods
    bgm_path = os.path.join(BASE_DIR, "bgm.mp3")
    if os.path.exists(bgm_path):
        bgm_audio = AudioFileClip(bgm_path)
        
        if bgm_audio.duration < target_duration:
            # AudioLoop di MoviePy 2.x
            bgm_audio = bgm_audio.with_effects([AudioLoop(duration=target_duration)])
        else:
            bgm_audio = bgm_audio.subclipped(0, target_duration)
            
        bgm_audio = bgm_audio.with_volume_scaled(0.08)
        mixed_audio = CompositeAudioClip([vo_audio.with_volume_scaled(1.0), bgm_audio])
    else:
        mixed_audio = vo_audio
        
    final_video = final_video.with_audio(mixed_audio)
    
    output_path = os.path.join(OUTPUT_DIR, "final_output_video.mp4")
    
    print("\n" + "="*50)
    print(f"[RENDER] Memulai rendering ke: {output_path}")
    print("="*50 + "\n")
    
    final_video.write_videofile(
        output_path, 
        fps=24, 
        codec="libx264", 
        audio_codec="aac",
        threads=4
    )
    
    vo_audio.close()
    if os.path.exists(bgm_path):
        bgm_audio.close()
    compiled_video.close()
    final_video.close()
    
    try:
        os.remove(temp_audio)
        os.remove(temp_vtt)
    except:
        pass
        
    print("\n[SUCCESS] VIDEO EDITING BERHASIL DISELESAIKAN!")

if __name__ == "__main__":
    main()
