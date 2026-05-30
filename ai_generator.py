import json
import re
import requests

# Cek ketersediaan SDK Google Gemini secara aman
GEMINI_AVAILABLE = False
try:
    # pyrefly: ignore [missing-import]
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    pass

# ==========================================
# 1. LOCAL OLLAMA MODELS SCANNER
# ==========================================
def get_ollama_models():
    """
    Memanggil API lokal Ollama untuk memindai seluruh LLM yang sudah terpasang di PC secara real-time.
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3.0)
        if response.status_code == 200:
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            return models
    except Exception:
        pass
    return []

# ==========================================
# 2. DYNAMIC SYSTEM PROMPT COMPILER
# ==========================================
def compile_prompt(product_name, product_desc, categories):
    """
    Merangkai prompt dinamis terstruktur berdasarkan input nama produk, deskripsi,
    serta kategori kustom beserta framework copywriting yang dipilih (AIDA, PAS, FAB, BAB).
    """
    total_videos = sum(cat["count"] for cat in categories)
    
    # Keterangan detail mengenai masing-masing framework copywriting
    framework_guidelines = {
        "AIDA": "AIDA (Attention, Interest, Desire, Action): Pikat perhatian di 3 detik pertama (Hook visual/audio tajam), bangun ketertarikan dengan keunikan, ciptakan hasrat emosional mendalam, lalu akhiri dengan Call to Action (CTA) variatif.",
        "PAS": "PAS (Problem, Agitate, Solve): Angkat masalah atau keresahan utama pengguna, dramatisasi/buat masalah tersebut terasa mendesak dan menakutkan jika dibiarkan (Agitate), lalu hadirkan produk sebagai solusi penyelamat terbaik (Solve).",
        "FAB": "FAB (Features, Advantages, Benefits): Kenalkan fitur utama produk (Features), jelaskan mengapa fitur ini lebih unggul dari opsi lain (Advantages), dan tekankan manfaat nyata yang langsung didapatkan pengguna (Benefits).",
        "BAB": "BAB (Before, After, Bridge): Gambarkan kondisi buruk/sedih sebelum menggunakan produk (Before), visualisasikan transformasi indah setelah menggunakan produk (After), lalu tunjukkan produk sebagai jembatan yang mewujudkan hal itu (Bridge).",
        "TikTok Hook": "Gunakan struktur modern video pendek TikTok: Hook kontroversial/menarik di 3 detik pertama, Story pendek yang relevan, dan akhiri dengan CTA interaktif yang unik."
    }
    
    composition_details = []
    video_counter = 1
    
    for cat in categories:
        name = cat["name"]
        count = cat["count"]
        fw = cat.get("framework", "AIDA")
        guideline = framework_guidelines.get(fw, framework_guidelines["AIDA"])
        
        start_id = video_counter
        end_id = video_counter + count - 1
        video_counter += count
        
        # Tambahkan variasi spesifik untuk promo keranjang kuning jika kategorinya adalah Promo
        promo_note = ""
        if name.lower() == "promo":
            promo_note = " (Tiap video wajib diakhiri dengan variasi ajakan cek/intip keranjang kuning)"
            
        composition_details.append(
            f"- Kategori \"{name}\": Video {start_id} sampai {end_id} ({count} video). "
            f"Wajib menggunakan framework {guideline}{promo_note}."
        )
        
    composition_str = "\n".join(composition_details)
    
    prompt = f"""Anda adalah pakar Copywriting Pemasaran Digital tingkat tinggi yang berspesialisasi dalam membuat naskah video pendek vertikal (TikTok/Reels/Shorts) dengan konversi penjualan yang luar biasa.

Tugas Anda adalah membuat naskah video promosi sebanyak tepat {total_videos} video pendek (masing-masing naskah berkisar antara 50 sampai 60 kata untuk durasi sekitar 15-20 detik) untuk produk berikut:
- Nama Produk: {product_name}
- Deskripsi/Fitur Utama: {product_desc}

Output naskah wajib ditulis dalam Bahasa Indonesia yang sangat natural, kekinian, mengalir, persuasif, dan bersahabat (hindari bahasa kaku/terlalu formal).

Komposisi kategori naskah yang wajib Anda buat adalah sebagai berikut:
{composition_str}

Format output WAJIB berupa JSON Array murni yang berisi tepat {total_videos} objek JSON, tanpa ada penjelasan basa-basi di luar kode JSON tersebut. Jangan sertakan teks percakapan pembuka atau penutup. Kembalikan HANYA array JSON yang valid.

Setiap objek di dalam JSON Array wajib memiliki tepat 4 field kunci berikut:
- "id": (integer, mulai dari 1 sampai {total_videos})
- "product": "{product_name}"
- "category": (string, nama kategori yang bersangkutan, misal: "Promo", "Edukasi", dll)
- "naskah": (string, naskah video promosi lengkap hasil tulisan Anda)

Ingat, jangan bungkus JSON dengan teks penjelasan lain, mulailah langsung dengan tanda [ dan akhiri dengan tanda ]."""
    
    return prompt

# ==========================================
# 3. ROBUST JSON PARSER & SANITIZER
# ==========================================
def sanitize_and_parse_json(raw_text):
    """
    Parser tangguh untuk mengekstrak dan mem-parsing array JSON dari respon LLM,
    meskipun terbungkus oleh teks percakapan atau blok kode markdown ```json ... ```.
    """
    clean_text = raw_text.strip()
    
    # 1. Cari blok kode markdown ```json ... ``` atau ``` ... ```
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', clean_text, re.DOTALL)
    if match:
        clean_text = match.group(1).strip()
        
    # 2. Jika tidak ada blok markdown, cari karakter kurung siku pertama [ dan terakhir ]
    else:
        start_idx = clean_text.find('[')
        end_idx = clean_text.rfind(']')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            clean_text = clean_text[start_idx:end_idx + 1].strip()
            
    # 3. Lakukan parsing JSON
    try:
        parsed_data = json.loads(clean_text)
        if isinstance(parsed_data, list):
            return parsed_data
        else:
            raise ValueError("Output JSON bukan merupakan sebuah list/array.")
    except Exception as e:
        raise ValueError(f"Gagal mem-parsing format JSON dari respon AI. Error: {str(e)}\nRespon mentah AI: {raw_text[:300]}...")

# ==========================================
# 4. LLM INFERENCE CONNECTORS
# ==========================================
def generate_scripts_ollama(model_name, product_name, product_desc, categories):
    """
    Meminta generasi naskah ke Ollama lokal via REST API.
    """
    prompt = compile_prompt(product_name, product_desc, categories)
    url = "http://localhost:11434/api/generate"
    
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "format": "json", # Meminta Ollama mengembalikan JSON secara ketat
        "options": {
            "temperature": 0.7
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=90.0)
        if response.status_code == 200:
            raw_response = response.json().get("response", "")
            return sanitize_and_parse_json(raw_response)
        else:
            raise Exception(f"HTTP Error {response.status_code} dari Ollama.")
    except Exception as e:
        raise Exception(f"Koneksi ke Ollama gagal: {str(e)}")

def generate_scripts_gemini(api_key, model_name, product_name, product_desc, categories):
    """
    Meminta generasi naskah ke Google Gemini API via official SDK atau REST fallback.
    """
    prompt = compile_prompt(product_name, product_desc, categories)
    
    if GEMINI_AVAILABLE:
        try:
            genai.configure(api_key=api_key)
            # Konfigurasi agar Gemini membalas dengan format JSON murni
            generation_config = {
                "temperature": 0.7,
                "response_mime_type": "application/json"
            }
            model = genai.GenerativeModel(model_name, generation_config=generation_config)
            response = model.generate_content(prompt)
            return sanitize_and_parse_json(response.text)
        except Exception as e:
            raise Exception(f"Generasi Gemini SDK Gagal: {str(e)}")
    
    # Fallback ke REST API jika SDK tidak terinstal
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60.0)
        if response.status_code == 200:
            data = response.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return sanitize_and_parse_json(raw_text)
        else:
            err_msg = response.json().get("error", {}).get("message", "Unknown error")
            raise Exception(f"Gemini API Error: {err_msg}")
    except Exception as e:
        raise Exception(f"Koneksi ke Gemini API gagal: {str(e)}")

def generate_scripts_openrouter(api_key, model_name, product_name, product_desc, categories):
    """
    Meminta generasi naskah ke OpenRouter API via REST.
    """
    prompt = compile_prompt(product_name, product_desc, categories)
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/AutoVideo-RVC", # OpenRouter requires this
        "X-Title": "AutoVideo-RVC"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"} # Meminta beberapa model OpenRouter merespon dengan JSON
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60.0)
        if response.status_code == 200:
            data = response.json()
            raw_text = data["choices"][0]["message"]["content"]
            return sanitize_and_parse_json(raw_text)
        else:
            err_msg = response.json().get("error", {}).get("message", f"HTTP {response.status_code}")
            raise Exception(f"OpenRouter Error: {err_msg}")
    except Exception as e:
        raise Exception(f"Koneksi ke OpenRouter gagal: {str(e)}")
