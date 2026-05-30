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
    print(f"[ERROR] MoviePy 2.x import failed: {str(e)}")
    print("Mohon instal dependensi terlebih dahulu: pip install moviepy edge-tts Pillow numpy")
    sys.exit(1)

import edge_tts

# Cek apakah rvc-python terinstal untuk akselerasi GPU Furina RVC
RVC_ENABLED = False
try:
    # pyrefly: ignore [missing-import]
    from rvc_python.infer import RVCInference
    RVC_ENABLED = True
except ImportError:
    pass

# ==========================================
# KONFIGURASI FOLDER
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_INPUT_DIR = os.path.join(BASE_DIR, "video_input")
MUSIC_INPUT_DIR = os.path.join(BASE_DIR, "music_input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")

# RVC Model Furina
RVC_MODEL_PATH = os.path.join(BASE_DIR, "RVC", "Furina", "Furina_e170_s54910.pth")
RVC_INDEX_PATH = os.path.join(BASE_DIR, "RVC", "Furina", "added_IVF4312_Flat_nprobe_1_Furina_v2.index")

# Resolusi standard portrait 9:16 untuk Reels/Shorts/TikTok
OUTPUT_W = 1080
OUTPUT_H = 1920
DEFAULT_VOICE = "id-ID-GadisNeural" # Suara cewek premium alami (+20% speed)

# ==========================================
# 40 NASKAH PENJUALAN (20 POC Cabai + 20 Perisai Cabai)
# ==========================================
VIDEOS_CONFIG = [
    # ----------------------------------------------------
    # BATCH 1: POC CABAI (Video 1 - 20)
    # ----------------------------------------------------
    # -- 4 PROMO --
    {
        "id": 1, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Pengen pohon cabai kamu di rumah subur dan berbuah lebat menggelantung tanpa perlu pusing mikirin biaya pupuk kimia yang mahal? Dapatkan nutrisi organik lengkap khusus tanaman cabai di sini! Setiap botol POC Cabai dari Infarm siap membantu menyuburkan tanaman kesayanganmu dari akar sampai pucuk. Buruan cek keranjang kuning banyak promo menarik menantimu!"
    },
    {
        "id": 2, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Kabar gembira buat kamu pencinta tanaman hortikultura yang ingin berkebun cabai sendiri di halaman rumah! Sekarang gak perlu lagi khawatir tanaman kerdil atau buah hambar. Gunakan pupuk organik cair nomor satu dari Infarm yang kaya akan vitamin dan nutrisi lengkap khusus cabai. Yuk intip keranjang kuning sekarang selagi banyak promo heboh!"
    },
    {
        "id": 3, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Mau panen cabai segar yang merah merona dan melimpah ruah setiap hari dengan modal super irit? Langkah rahasianya adalah menggunakan nutrisi organik alami yang diproses khusus untuk merangsang pembungaan dini. Tanaman jadi lebih subur, tangguh, dan rajin berbuah lebat sepanjang musim. Buruan amankan promonya di keranjang kuning sekarang juga!"
    },
    {
        "id": 4, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Berkebun di pekarangan rumah kini jadi jauh lebih seru dan menyenangkan kalau pohon cabaimu selalu dipenuhi buah yang lebat dan pedas nampol! Jaga kualitas pertumbuhannya dari awal tanam menggunakan nutrisi organik premium dari Infarm yang sudah terbukti khasiatnya secara nyata. Klik keranjang kuning di bawah untuk melihat kejutan promo hari ini!"
    },
    # -- 4 PROBLEM SOLUTION --
    {
        "id": 5, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Tanaman cabai kamu di rumah terlihat sangat subur, daunnya rimbun berwarna hijau pekat, tapi kok heran gak kunjung muncul bunga apalagi buahnya? Jangan dibiarkan stres kelaparan! Masalah utamanya adalah tanaman kekurangan hormon perangsang buah. Berikan kocor rutin POC Cabai Infarm yang kaya nutrisi mikro untuk mempercepat proses pembuahan secara massal!"
    },
    {
        "id": 6, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Udah senang banget melihat bunga cabai mulai bermunculan di setiap sela ranting daun, eh besok paginya malah rontok semua berserakan di tanah? Pasti nyesek banget kan! Cegah bunga rontok sejak dini dengan rutin menyiramkan POC Cabai Infarm seminggu sekali untuk memperkuat jaringan tangkai tanaman agar buah tumbuh maksimal bebas gugur!"
    },
    {
        "id": 7, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Kenapa sih cabai rawit yang kamu tanam sendiri di pot rumah rasanya kurang pedas, tipis, dan hambar saat dimakan? Hal itu terjadi karena media tanam kamu kekurangan unsur urea nitrogen alami yang memicu zat capsaicin. Segera kocor media tanah menggunakan POC Cabai Infarm agar buahnya tebal, berkilau, dan memiliki rasa pedas yang nampol!"
    },
    {
        "id": 8, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Pohon cabai kesayanganmu di halaman rumah terlihat loyo, daunnya letoy, gampang layu saat siang hari, dan sering banget ditempeli hama kutu putih daun? Selamatkan kelangsungan hidupnya dengan POC Cabai Infarm! Kandungan zat pengatur tumbuh dan tambahan pestisida nabati alaminya sangat ampuh membangun daya tahan tubuh tanaman agar kebal penyakit!"
    },
    # -- 4 EDUKASI --
    {
        "id": 9, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Bagi kamu pemula yang baru belajar berkebun cabai, ini dia cara mudah mengocor pupuk organik cair yang benar agar tanaman tumbuh subur! Cukup larutkan dua pump formula POC Cabai Infarm ke dalam satu liter air bersih. Aduk perlahan hingga merata, lalu siramkan langsung ke sekeliling media tanam seminggu sekali. Hasil panen dijamin lebat!"
    },
    {
        "id": 10, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Tahukah kamu kalau nutrisi tanaman cabai itu sebenarnya bisa diserap langsung lewat pori-pori daun? Benar sekali! Selain disiram ke tanah, larutkan dua pump POC Cabai Infarm per liter air, lalu semprotkan tipis-tipis merata ke seluruh permukaan daun tanaman setiap seminggu sekali di pagi hari sebelum terik matahari menyengat. Praktis dan hemat!"
    },
    {
        "id": 11, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Penting banget untuk dipahami bahwa tanaman cabai sangat membutuhkan unsur urea nitrogen alami untuk memicu zat hijau daun dan menaikkan rasa pedas capsaicin yang khas. Kabar baiknya, semua kebutuhan zat gizi penting tersebut sudah lengkap terpadu dalam satu botol praktis POC Cabai Infarm. Cukup kocor rutin untuk hasil kebun yang menakjubkan!"
    },
    {
        "id": 12, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Banyak yang penasaran apa sih sebenarnya fungsi dari zat pengatur tumbuh atau ZPT pada tanaman cabai? ZPT berfungsi merangsang pembelahan sel tanaman agar batang tumbuh kokoh berdiri tegak, memicu pertumbuhan tunas baru, sekaligus mempercepat pembuahan secara massal. Dapatkan seluruh manfaat ZPT organik terbaik ini hanya di dalam POC Cabai Infarm!"
    },
    # -- 4 TESTIMONI --
    {
        "id": 13, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Senang dan puas banget rasanya sejak rutin menggunakan POC Cabai Infarm di pekarangan rumah! Pohon cabai rawit yang saya tanam di pot plastik ukuran kecil sekarang buahnya merah lebat menggelantung sampai batangnya meliuk. Tetangga rumah pada heran dan nanya apa rahasianya kok bisa sesubur ini. Terima kasih banyak Infarm!"
    },
    {
        "id": 14, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Jujur saja awalnya saya sempat ragu dan takut untuk mulai mencoba menanam pohon cabai sendiri di rumah karena terkenal gampang gagal dan rumit. Tapi untungnya setelah rutin menggunakan POC Cabai Infarm satu minggu sekali, hasilnya benar-benar di luar ekspektasi! Bahkan pemula seperti saya pun kini bisa panen cabai segar melimpah setiap hari."
    },
    {
        "id": 15, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Hasil panen cabai di kebun belakang rumah saya sekarang kualitasnya beda jauh banget dengan yang dulu! Buahnya jadi jauh lebih panjang, mengkilap, padat berisi, dan rasa pedasnya benar-benar menendang lidah. Itu semua karena nutrisi urea nitrogen alami dari POC Cabai Infarm terpenuhi dengan sempurna setiap minggunya. Produk ini benar-benar juara!"
    },
    {
        "id": 16, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Dulu daun pohon cabai saya sering banget rusak berlubang dan keriting parah akibat serangan ulat tanah serta hama tanaman. Tapi sejak rutin saya semprotkan POC Cabai Infarm yang mengandung ekstrak pestisida nabati alami, daunnya berangsur pulih tumbuh segar, lebar, tebal, dan bebas dari hama pengganggu tanaman. Sangat puas dengan hasilnya!"
    },
    # -- 4 HARDSELLING --
    {
        "id": 17, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Mulai sekarang stop buang-buang waktu berharga kamu menyiram tanaman cabai hanya dengan air biasa yang sama sekali tidak mengandung zat gizi! Saatnya tingkatkan produktivitas kebun rumahmu dengan nutrisi canggih POC Cabai Infarm. Rasakan perubahan pertumbuhannya dalam hitungan minggu. Klik tombol keranjang kuning sekarang juga sebelum kehabisan stok!"
    },
    {
        "id": 18, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Ingin merasakan sensasi seru panen cabai segar melimpah di halaman rumah tanpa perlu repot mengeluarkan uang banyak untuk membeli pupuk kimia sintetis berbahaya? Cukup andalkan POC Cabai Infarm! Solusi praktis satu botol dengan sejuta manfaat bagi kesuburan tanaman cabaimu. Buruan checkout hari ini dan rasakan sendiri kehebatannya!"
    },
    {
        "id": 19, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Stok produk semakin menipis setiap harinya! POC Cabai Infarm merupakan produk paling laris dan dicari oleh para pencinta tanaman buah karena khasiat organiknya yang terbukti mempercepat pembuahan secara alami dan sehat. Jangan biarkan pohon cabaimu tumbuh kerdil tanpa buah, segera amankan botol kesayanganmu sekarang juga!"
    },
    {
        "id": 20, "product": "POC Cabai", "folder": "POC Cabai",
        "naskah": "Saatnya buktikan sendiri kehebatan luar biasa dari pupuk organik cair khusus tanaman cabai nomor satu di Indonesia! POC Cabai Infarm diformulasikan secara khusus untuk memberikan suplai gizi terlengkap agar pohon cabaimu mampu berbuah lebat sepanjang tahun tanpa kenal musim. Tunggu apa lagi, segera checkout botolmu sekarang!"
    },

    # ----------------------------------------------------
    # BATCH 2: PERISAI CABAI (Video 21 - 40)
    # ----------------------------------------------------
    # -- 4 PROMO --
    {
        "id": 21, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Mau daun tanaman cabai kesayanganmu di rumah tumbuh sehat, hijau segar, lebar, dan bebas dari segala serangan penyakit berbahaya? Saatnya kamu berikan perlindungan khusus dari luar dan dalam! Gunakan formula tameng pelindung tanaman terbaik yang aman dan ramah lingkungan dari Infarm. Jangan lewatkan, langsung kepoin keranjang kuning buat dapatkan promonya!"
    },
    {
        "id": 22, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Menanam cabai di rumah sering gagal karena daunnya mendadak menguning dan rontok terserang virus penyakit pembawa layu? Tenang, sekarang ada solusi tameng pertahanan alami khusus tanaman cabai yang siap menjaga tanamanmu tetap aman sepanjang hari agar bebas gagal panen. Segera amankan stok tanaman sehatmu di keranjang kuning selagi banyak promo!"
    },
    {
        "id": 23, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Membentengi tanaman cabai dari serangan hama pembawa virus jahat kini jadi jauh lebih mudah dan praktis tanpa perlu racikan pestisida kimia berbahaya yang merusak alam. Dapatkan kebaikan nutrisi asam amino pembentuk imun tanaman terbaik dari Infarm agar kebunmu subur aman. Langsung klik keranjang kuning untuk berburu promo gila-gilaan!"
    },
    {
        "id": 24, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Luncurkan pertahanan maksimal untuk bibit cabai di pekarangan rumahmu sejak masa awal tanam agar kekebalan alaminya terbentuk kuat sejak dini! Formula khusus dari Infarm siap membentengi dinding sel tanaman dari ancaman segala macam virus kuning merusak. Yuk kepoin keranjang kuning sekarang biar gak kehabisan promo serunya!"
    },
    # -- 4 PROBLEM SOLUTION --
    {
        "id": 25, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Pusing kepala melihat daun tanaman cabai kesayanganmu yang mulai terlihat keriting, meliuk-liuk, dan perlahan menguning padahal sudah rajin kamu sirami dan beri pupuk mahal setiap harinya? Ingat, itu adalah tanda infeksi virus kuning! Segera semprotkan Perisai Cabai Infarm untuk menghentikan serangan virus tersebut sampai ke akar-akarnya secara tuntas!"
    },
    {
        "id": 26, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Pernah heran kenapa pohon cabai yang kamu rawat tumbuh kerdil, batangnya kurus, dan daunnya tidak mau berkembang lebar seperti tanaman tetangga? Masalah utamanya adalah serangan virus kerdil pembawa penyakit tanaman. Segera semprotkan Perisai Cabai Infarm agar protein antibodi tanaman terbentuk sempurna dan tunas baru tumbuh subur tegak berdiri!"
    },
    {
        "id": 27, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Perawatan tanaman cabai memang terkenal memiliki tantangan yang sangat sulit bagi pemula karena risikonya yang tinggi akan ancaman gagal panen akibat cuaca. Tapi sekarang kamu tidak perlu cemas lagi! Kehadiran Perisai Cabai Infarm bertindak sebagai tameng pelindung tangguh yang terbukti nyata mampu menekan persentase risiko gagal panen hingga tingkat terendah!"
    },
    {
        "id": 28, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Memasuki kondisi cuaca ekstrem pancaroba yang tidak menentu, tanaman cabai di luar ruangan sangat rentan mengalami stres fisiologis, layu daun, dan mati mendadak. Bentengi pertahanan tubuh tanaman cabai kesayanganmu dari serangan penyakit musiman menggunakan semprotan rutin formula aktif Perisai Cabai Infarm setiap seminggu sekali secara merata!"
    },
    # -- 4 EDUKASI --
    {
        "id": 29, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Bagaimana sih cara kerja ilmiah dari formula Perisai Cabai dalam melindungi dan membentengi kesehatan tanaman cabai? Kandungan asam amino esensial di dalamnya bekerja merangsang sintesis enzim pertahanan khusus yang memperkuat membran dan dinding sel tanaman sehingga tanaman menjadi sangat tangguh dan kebal dari infeksi virus pembawa penyakit!"
    },
    {
        "id": 30, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Ini dia tips rahasia paling penting dalam menyemprotkan Perisai Cabai Infarm agar hasilnya maksimal! Semprotkan cairan secara merata ke seluruh bagian daun, terutama pada bagian bawah permukaan daun tanaman karena di situlah area favorit tempat persembunyian virus dan kutu daun penghisap nutrisi. Lakukan penyemprotan seminggu sekali ya!"
    },
    {
        "id": 31, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Kapan waktu paling ideal dan terbaik untuk mulai menyemprotkan cairan Perisai Cabai ke tanaman kesayanganmu? Langkah paling bijak dan efektif adalah menyemprotkannya sejak tanaman masih berada dalam fase pembibitan atau awal vegetatif. Hal ini bertujuan agar sistem imun alami tanaman sudah terlatih kuat sejak usia dini!"
    },
    {
        "id": 32, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Pernahkah kamu mendengar istilah vaksinasi pada dunia tumbuh-tumbuhan? Benar sekali, konsep Perisai Cabai Infarm ini bertindak layaknya vaksin bagi tanaman cabai. Kandungan protein aktifnya bekerja melatih sistem antibodi alami tanaman agar selalu siap mendeteksi dan menolak serangan virus kerdil yang menyebabkan layu pada tanaman!"
    },
    # -- 4 TESTIMONI --
    {
        "id": 33, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Sebagai seorang pemula yang baru pertama kali belajar menanam cabai sendiri di pekarangan rumah, produk Perisai Cabai Infarm ini benar-benar penyelamat hidup tanaman saya! Sekarang pohon cabai saya sukses tumbuh tegak, kokoh berdiri, dan subur tanpa ada drama daun keriting meliuk ataupun layu menguning. Sangat direkomendasikan!"
    },
    {
        "id": 34, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Hasilnya benar-benar luar biasa nyata! Meskipun saya menanam pohon cabai di media pot sempit dengan kondisi cuaca yang sering diguyur hujan lebat akhir-akhir ini, daun cabai saya tetap terlihat hijau segar, lebar, tebal, dan bebas dari gangguan hama kutu daun yang menyebalkan. Perisai Cabai Infarm memang tameng pelindung terbaik!"
    },
    {
        "id": 35, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Dulu sebelum kenal produk ini, saya sering banget mengalami gagal panen karena daun cabai tiba-tiba menguning rontok dalam semalam. Tapi semenjak rutin menyemprotkan Perisai Cabai Infarm satu minggu sekali, semua pohon cabai saya sukses tumbuh dengan subur hingga masa panen raya tiba dengan hasil yang berlimpah ruah!"
    },
    {
        "id": 36, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Tanaman cabai rawit saya yang tadinya sempat keriting parah dan hampir mati lemas akibat terserang hama kutu, perlahan-lahan mulai pulih sehat kembali setelah rutin saya semprotkan formula Perisai Cabai seminggu sekali. Produk ini benar-benar terbukti ampuh bertindak sebagai tameng pelindung tanaman yang wajib dimiliki oleh semua pekebun!"
    },
    # -- 4 HARDSELLING --
    {
        "id": 37, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Jangan pernah menunggu sampai daun tanaman cabaimu terlanjur keriting parah, layu menguning, dan mati mengenaskan baru kamu menyesal di kemudian hari! Segera ambil tindakan pencegahan dan bentengi pertahanan tubuh tanamanmu sekarang menggunakan formula khusus Perisai Cabai Infarm. Klik tombol keranjang kuning sekarang untuk memesan produk aslinya!"
    },
    {
        "id": 38, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Mau tanaman cabai kesayanganmu di rumah berbuah sangat lebat sekaligus memiliki pertahanan tubuh yang kuat bebas dari penyakit daun keriting? Jangan hanya mengandalkan satu jenis produk saja! Ini dia duet pertahanan terbaik dari Infarm, kombinasi dahsyat POC Cabai dan Perisai Cabai! POC Cabai bertugas merangsang pembungaan agar buahnya tumbuh lebat dan pedas nampol, sedangkan Perisai Cabai bertindak sebagai tameng pertahanan yang membentengi daun dari infeksi virus kuning dan layu kerdil. Gunakan perpaduan harmonis keduanya seminggu sekali untuk menjamin panen melimpah ruah sepanjang tahun. Buruan checkout paket hemat bundlingnya sekarang juga!"
    },
    {
        "id": 39, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Ini dia rahasia sukses para pemula bisa panen cabai melimpah ruah di halaman rumah tanpa perlu takut gagal panen atau mati layu! Kuncinya terletak pada sistem perlindungan ganda luar dalam dari Infarm dengan mengombinasikan POC Cabai dan Perisai Cabai. POC Cabai menyuplai nutrisi makro terlengkap agar buah cabai tumbuh gemuk, lebat, dan berbobot padat, sedangkan Perisai Cabai merangsang sistem imun alami tanaman agar kebal menghadapi serangan virus kerdil pembawa layu. Kombinasi terbaik agar aktivitas berkebun di rumah terasa mudah, menyenangkan, dan sukses menghasilkan panen melimpah. Yuk dapatkan promo paket hemat bundling ini di keranjang kuning sekarang juga!"
    },
    {
        "id": 40, "product": "Perisai Cabai", "folder": "Perisa Cabai",
        "naskah": "Spesial bagi kamu yang ingin mendapatkan hasil panen maksimal, dapatkan segera duet pertahanan cabai terlengkap ini dengan penawaran paket hemat khusus hari ini! Paket bundling super hemat POC Cabai dan Perisai Cabai dari Infarm! Perlindungan total menyeluruh mulai dari akar, batang, daun, hingga buahnya agar tanaman tumbuh subur bergairah, berbuah lebat menggelantung, serta kebal dari ancaman segala macam virus daun keriting yang merusak. Sangat mudah diaplikasikan oleh pemula sekalipun demi memberikan jaminan panen segar berlimpah di halaman rumah. Buruan klik tombol keranjang kuning dan checkout paket bundlingnya sekarang juga sebelum kehabisan!"
    }
]

# ==========================================
# PARSER WEBVTT & TIME DECODER
# ==========================================
def parse_time(time_str):
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
    if not os.path.exists(vtt_path):
        return subs
    with open(vtt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    current_time = None
    current_text = []
    
    for line in lines:
        line = line.strip()
        if not line or line == "WEBVTT":
            continue
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

def kelompokkan_subtitle(subs, max_words=3, max_duration=1.8):
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
# RENDER SUBTITLE KE PNG & PILLOW
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
        
        max_text_width = int(video_w * 0.82)
        lines = wrap_text(text, font, max_text_width)
        
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
# DYNAMIC VIDEO STITCHER (MoviePy 2.x compatible)
# ==========================================
def buat_video_assembly(target_duration, raw_video_paths):
    # Pisahkan klip yang menampilkan botol produk/aksi berdasarkan kata kunci utama (produk, product, poc, perisai, infarm)
    keywords = ["produk", "product", "poc", "perisai", "infarm"]
    product_clips = [p for p in raw_video_paths if any(k in os.path.basename(p).lower() for k in keywords)]
    broll_clips = [p for p in raw_video_paths if p not in product_clips]
    
    random.shuffle(product_clips)
    random.shuffle(broll_clips)
    
    # Rencana susunan klip agar alur visualnya pas
    selected_paths = []
    
    # 1. Prioritaskan taruh klip produk di HOOK (detik-detik pertama video)
    if product_clips:
        selected_paths.append(product_clips.pop(0))
        
    # 2. Prioritaskan taruh klip produk di akhir (CTA / ajakan beli) jika masih ada klip produk sisa
    cta_clip = None
    if product_clips:
        cta_clip = product_clips.pop(0)
        
    # 3. Klip tengah diisi oleh B-roll detail (tanaman, kocor pupuk, hama, dll) + sisa klip produk
    middle_clips = broll_clips + product_clips
    random.shuffle(middle_clips)
    selected_paths.extend(middle_clips)
    
    # Masukkan CTA klip produk di ujung video
    if cta_clip:
        selected_paths.append(cta_clip)
        
    # Fallback jika folder kosong dari label produk, gunakan seluruh klip secara acak seperti biasa
    if not selected_paths:
        selected_paths = raw_video_paths
        random.shuffle(selected_paths)
        
    clips = []
    current_duration = 0.0
    
    # Gunakan pool agar tidak ada duplikasi scene kecuali terpaksa karena klip unik habis
    pool = list(selected_paths)
    last_path = None
    
    while current_duration < target_duration:
        if not pool:
            # Jika semua klip unik sudah dipakai, lakukan isi ulang (reuse)
            pool = list(selected_paths)
            random.shuffle(pool)
            # Cegah klip berulang berturut-turut (back-to-back)
            if len(pool) > 1 and pool[0] == last_path:
                pool.append(pool.pop(0))
                
        path = pool.pop(0)
        last_path = path
        
        try:
            clip = VideoFileClip(path)
            clip_duration = clip.duration
            
            # Potong klip mentah secara acak antara 2.5 sampai 4.2 detik
            if clip_duration > 5.5:
                start_time = random.uniform(1.0, clip_duration - 4.5)
                duration_needed = min(random.uniform(2.5, 4.2), target_duration - current_duration)
                sub_clip = clip.subclipped(start_time, start_time + duration_needed)
            else:
                duration_needed = min(clip_duration, target_duration - current_duration)
                sub_clip = clip.subclipped(0, duration_needed)
            
            sub_clip = sub_clip.without_audio()
            
            # Resize & Crop ke Portrait
            clip_w, clip_h = sub_clip.size
            scale = max(OUTPUT_W / clip_w, OUTPUT_H / clip_h)
            new_w = int(clip_w * scale)
            new_h = int(clip_h * scale)
            
            sub_clip = sub_clip.resized(new_size=(new_w, new_h))
            x1 = (new_w - OUTPUT_W) // 2
            y1 = (new_h - OUTPUT_H) // 2
            sub_clip = sub_clip.cropped(x1=x1, y1=y1, width=OUTPUT_W, height=OUTPUT_H)
            
            clips.append(sub_clip)
            current_duration += sub_clip.duration
        except Exception as e:
            print(f"[WARNING] Gagal memproses klip {path}: {str(e)}")
            continue
            
    return concatenate_videoclips(clips, method="compose")

# ==========================================
# ASYNC EDGE-TTS & RVC GENERATOR
# ==========================================
async def generate_voiceover_rvc(text, audio_out, vtt_out):
    temp_mp3 = audio_out.replace(".wav", "_temp_raw.mp3")
    temp_raw_wav = audio_out.replace(".wav", "_temp_raw.wav")
    
    # 1. Edge-TTS membuat suara pemandu (raw) dengan presisi kata-per-kata (WordBoundary)
    communicate = edge_tts.Communicate(text, DEFAULT_VOICE, rate="+20%", boundary="WordBoundary")
    submaker = edge_tts.SubMaker()
    with open(temp_mp3, "wb") as fp:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
                
    # Simpan file subtitle
    with open(vtt_out, "w", encoding="utf-8") as fp:
        fp.write(submaker.get_srt())
        
    # Konversi MP3 ke WAV menggunakan MoviePy (aman, local, tanpa external parser)
    print(" -> Mengonversi audio pemandu ke WAV...")
    temp_mp3_clip = AudioFileClip(temp_mp3)
    temp_mp3_clip.write_audiofile(temp_raw_wav, fps=44100, logger=None)
    temp_mp3_clip.close()
    
    # 2. Konversi menggunakan RVC Furina (RTX 3060 CUDA) jika modul & file lengkap
    rvc_success = False
    if RVC_ENABLED and os.path.exists(RVC_MODEL_PATH):
        print(" -> Mengonversi suara ke Furina RVC via GPU RTX 3060...")
        try:
            rvc_inf = RVCInference(
                device="cuda:0",
                model_path=RVC_MODEL_PATH,
                index_path=RVC_INDEX_PATH if os.path.exists(RVC_INDEX_PATH) else "",
                version="v2"
            )
            # Furina (Jepang): f0up_key=6 untuk vokal imut bergaya anime, index_rate=0.2 untuk mempertahankan kesempurnaan logat Indonesia GadisNeural
            rvc_inf.set_params(f0up_key=6, f0method="rmvpe", index_rate=0.2, protect=0.33)
            rvc_inf.infer_file(temp_raw_wav, audio_out)
            rvc_inf.unload_model()
            rvc_success = True
            print(" -> [SUCCESS] Konversi RVC Furina Berhasil!")
        except Exception as e:
            print(f"[WARNING] Konversi RVC Gagal: {str(e)}. Menggunakan suara default perempuan.")
            
    # Fallback jika RVC gagal atau tidak terdeteksi
    if not rvc_success:
        if os.path.exists(audio_out):
            os.remove(audio_out)
        os.rename(temp_raw_wav, audio_out)
        
    # Bersihkan file temporer
    for temp_file in [temp_mp3, temp_raw_wav]:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

# ==========================================
# MAIN BATCH EXECUTION
# ==========================================
def run_batch():
    # Cek ketersediaan musik
    bgm_paths = glob.glob(os.path.join(MUSIC_INPUT_DIR, "*.mp3"))
    if not bgm_paths:
        print("[WARNING] Tidak ada file musik (.mp3) di music_input/!")
        
    print("\n" + "="*75)
    print(f"      AI BATCH AUTO-EDITOR: MEMPROSES TOTAL 40 VIDEO DUAL-PRODUK (MoviePy 2.x)")
    if RVC_ENABLED and os.path.exists(RVC_MODEL_PATH):
        print("      RVC DETECTED: MENGGUNAKAN SUARA AI FURINA via GPU RTX 3060")
    else:
        print("      RVC FALLBACK: MENGGUNAKAN SUARA AI PEREMPUAN PREMIUM (+20% Speed)")
    print("="*75)
    print(f"Aset Musik Latar Terdeteksi: {len(bgm_paths)} file.\n")
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    for config in VIDEOS_CONFIG:
        idx = config["id"]
        product_name = config["product"]
        folder_name = config["folder"]
        naskah = config["naskah"]
        
        # Tentukan kategori berdasarkan ID video agar nama file lebih mudah dibaca
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
            
        print(f"\n[VIDEO {idx}/40] Produk: {product_name} | Kategori: {category}...")
        
        # 1. Pindai video klip khusus untuk produk ini
        product_video_dir = os.path.join(VIDEO_INPUT_DIR, folder_name)
        product_video_paths = []
        for ext in ["*.mp4", "*.mov", "*.avi", "*.mkv"]:
            product_video_paths.extend(glob.glob(os.path.join(product_video_dir, ext)))
            product_video_paths.extend(glob.glob(os.path.join(product_video_dir, ext.upper())))
            
        if not product_video_paths:
            print(f"[ERROR] Tidak ada file video B-roll di folder: '{product_video_dir}'!")
            print(f"Melewati Video {idx}...")
            continue
            
        print(f" -> Terdeteksi {len(product_video_paths)} klip B-roll khusus {product_name}.")
        
        temp_audio = os.path.join(BASE_DIR, f"temp_vo_{idx}.wav") # WAV untuk kualitas RVC optimal
        temp_vtt = os.path.join(BASE_DIR, f"temp_sub_{idx}.vtt")
        
        # A. Buat Voiceover (RVC Furina atau Perempuan Natural)
        asyncio.run(generate_voiceover_rvc(naskah, temp_audio, temp_vtt))
        
        vo_audio = AudioFileClip(temp_audio)
        target_duration = vo_audio.duration
        print(f" -> Voiceover berhasil disiapkan. Durasi: {target_duration:.2f} detik.")
        
        # B. Susun Video B-Roll khusus produk tersebut
        compiled_video = buat_video_assembly(target_duration, product_video_paths)
        
        # C. Buat Subtitle Overlay (Montserrat-Bold otomatis!)
        raw_subs = parse_vtt(temp_vtt)
        # Tampilkan subtitle maks 2 kata per tampilan agar pas saat diucapkan (dinamika tinggi!)
        grouped_subs = kelompokkan_subtitle(raw_subs, max_words=2, max_duration=1.2)
        subtitle_clips = buat_subtitle_overlay_clip(grouped_subs, OUTPUT_W, OUTPUT_H)
        
        # D. Gabungkan Subtitle di atas Video
        final_video = CompositeVideoClip([compiled_video] + subtitle_clips)
        
        # E. Audio Mixing dengan Background Music Acak
        if bgm_paths:
            chosen_bgm = random.choice(bgm_paths)
            print(f" -> Menggunakan musik latar acak: {os.path.basename(chosen_bgm)}")
            bgm_audio = AudioFileClip(chosen_bgm)
            
            if bgm_audio.duration < target_duration:
                bgm_audio = bgm_audio.with_effects([AudioLoop(duration=target_duration)])
            else:
                bgm_audio = bgm_audio.subclipped(0, target_duration)
                
            # Set volume musik latar sangat rendah (8%)
            bgm_audio = bgm_audio.with_volume_scaled(0.08)
            mixed_audio = CompositeAudioClip([vo_audio.with_volume_scaled(1.0), bgm_audio])
        else:
            mixed_audio = vo_audio
            
        final_video = final_video.with_audio(mixed_audio)
        
        # F. Rendering Hasil Akhir
        product_clean_name = product_name.replace(" ", "_")
        output_path = os.path.join(OUTPUT_DIR, f"{product_clean_name}_{category}_{idx}.mp4")
        print(f" -> Merender file final ke: {output_path}...")
        
        final_video.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            logger=None # Matikan logger detail agar konsol bersih dan rapi
        )
        
        # Bersihkan resource
        vo_audio.close()
        if bgm_paths:
            bgm_audio.close()
        compiled_video.close()
        final_video.close()
        
        # Hapus file temporary
        for temp_file in [temp_audio, temp_vtt]:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            
        print(f"[SUCCESS] Video {idx} selesai dibuat!")

    print("\n" + "="*75)
    print("      🎉 SELURUH 40 VIDEO DUAL-PRODUK BERHASIL DI-RENDER OTOMATIS!")
    print(f"      Silakan cek folder hasil: {OUTPUT_DIR}")
    print("="*75 + "\n")

if __name__ == "__main__":
    run_batch()
