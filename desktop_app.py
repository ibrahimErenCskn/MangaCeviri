import os
import io
import time
import requests
import threading
from collections import Counter
from PIL import Image, ImageDraw, ImageFont, ImageTk
import customtkinter as ctk
from tkinter import filedialog, messagebox

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

API_URL = "http://127.0.0.1:8899/api/translate"

def wrap_text_to_fit(draw, text, font, max_width):
    lines = []
    words = text.split()
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        w = draw.textlength(test_line, font=font)
        if w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

class ManhwaTranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Manhwa Çeviri - Masaüstü Asistanı")
        self.geometry("700x750")
        self.resizable(False, False)

        self.image_paths = []

        # Title
        self.title_label = ctk.CTkLabel(self, text="Webtoon Sayfa Çevirici", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=10)

        # File Select
        self.select_btn = ctk.CTkButton(self, text="🖼️ Görselleri Seç...", height=40, font=("", 16), command=self.select_images)
        self.select_btn.pack(pady=5)

        self.file_label = ctk.CTkLabel(self, text="Henüz görsel seçilmedi.", text_color="gray")
        self.file_label.pack(pady=5)

        # Scrollable Frame for Image Previews
        self.preview_frame = ctk.CTkScrollableFrame(self, height=150, orientation="horizontal")
        self.preview_frame.pack(pady=10, fill="x", padx=20)
        
        self.preview_labels = []

        # Output Folder
        self.out_btn = ctk.CTkButton(self, text="📂 Çıktı Klasörünü Seç", height=30, font=("", 14), fg_color="gray", command=self.select_output_folder)
        self.out_btn.pack(pady=5)
        
        self.out_dir = os.path.join(os.path.expanduser("~"), "Desktop", "Manhwa_Ceviri_Ciktilari")
        if not os.path.exists(self.out_dir):
            os.makedirs(self.out_dir)

        self.out_label = ctk.CTkLabel(self, text=f"Çıktı: {self.out_dir}", text_color="gray")
        self.out_label.pack(pady=5)

        # OCR Engine & Font Options Frame
        opt_frame = ctk.CTkFrame(self, fg_color="transparent")
        opt_frame.pack(pady=10)

        # OCR Engine Selection
        self.engine_var = ctk.StringVar(value="glm-ocr")
        self.engine_menu = ctk.CTkOptionMenu(
            opt_frame, 
            values=["GLM-OCR + Gemini 3 27B", "PaddleOCR"], 
            variable=self.engine_var, 
            font=("", 13),
            width=220,
            command=self.on_engine_change
        )
        self.engine_menu.pack(side="left", padx=10)

        # Font Selection
        self.font_var = ctk.StringVar(value="Arial (Varsayılan)")
        self.font_menu = ctk.CTkOptionMenu(
            opt_frame, 
            values=["Arial (Varsayılan)", "Comic Sans MS", "Impact", "Georgia", "Verdana", "Tahoma"], 
            variable=self.font_var, 
            font=("", 13),
            width=200
        )
        self.font_menu.pack(side="left", padx=10)

        # Translate Button
        self.translate_btn = ctk.CTkButton(self, text="⚡ Seçili Tüm Sayfaları Çevir", height=50, font=("", 18, "bold"), fg_color="#28a745", hover_color="#218838", command=self.start_translation)
        self.translate_btn.pack(pady=15)

        # Status
        self.status_label = ctk.CTkLabel(self, text="Durum: Bekleniyor...", text_color="gray", font=("", 14))
        self.status_label.pack(pady=5)
        
        # ProgressBar
        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)
        
        # İlk açılışta backend kontrolü
        self.check_backend_status()

    def check_backend_status(self):
        try:
            res = requests.get("http://127.0.0.1:8899/api/health", timeout=1)
            if res.status_code == 200:
                self.status_label.configure(text="Sistem Hazır. Görselleri seçebilirsiniz.", text_color="green")
                # Backendden aktif motoru çek
                try:
                    engine_res = requests.get("http://127.0.0.1:8899/api/ocr-engine", timeout=1)
                    active = engine_res.json().get("active")
                    if active == "paddle":
                        self.engine_var.set("PaddleOCR")
                    else:
                        self.engine_var.set("GLM-OCR + Gemini 3 27B")
                except:
                    pass
        except:
            self.status_label.configure(text="Uyarı: Backend kapalı ('start_backend.bat' çalıştırın)", text_color="red")

    def on_engine_change(self, choice):
        engine_str = "paddle" if choice == "PaddleOCR" else "glm-ocr"
        try:
            requests.post("http://127.0.0.1:8899/api/ocr-engine", data={"engine": engine_str}, timeout=2)
            self.status_label.configure(text=f"Motor {choice} olarak ayarlandı.", text_color="green")
        except:
            self.status_label.configure(text="Motor değiştirilemedi, backend kapalı olabilir.", text_color="orange")

    def select_images(self):
        filetypes = (
            ("Resim Dosyaları", "*.png *.jpg *.jpeg *.webp"),
            ("Tüm Dosyalar", "*.*")
        )
        filepaths = filedialog.askopenfilenames(title="Çevrilecek sayfaları seçin", filetypes=filetypes)
        if filepaths:
            self.image_paths = list(filepaths)
            self.file_label.configure(text=f"{len(self.image_paths)} adet görsel seçildi.")
            self.status_label.configure(text="Görseller hazır. Çeviriye başlayabilirsiniz.", text_color="green")
            self.update_previews()
            
    def update_previews(self):
        # Önceki önizlemeleri temizle
        for lbl in self.preview_labels:
            lbl.destroy()
        self.preview_labels.clear()
        
        # Yeni seçilen resimlerin küçültülmüş versiyonlarını ekle
        for path in self.image_paths:
            try:
                img = Image.open(path)
                img.thumbnail((120, 150)) # aspect ratio korunarak küçültülür
                ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                
                lbl = ctk.CTkLabel(self.preview_frame, image=ctk_image, text="")
                lbl.pack(side="left", padx=5)
                self.preview_labels.append(lbl)
            except Exception as e:
                print(f"Önizleme yüklenemedi: {path} - {e}")

    def select_output_folder(self):
        folder = filedialog.askdirectory(title="Çıktı Klasörünü Seç")
        if folder:
            self.out_dir = folder
            self.out_label.configure(text=f"Çıktı: {self.out_dir}")

    def start_translation(self):
        if not self.image_paths:
            messagebox.showwarning("Uyarı", "Lütfen önce en az bir görsel seçin!")
            return

        self.translate_btn.configure(state="disabled", text="⏳ İşleniyor...")
        self.progress_bar.set(0)
        
        # Thread içinde çalıştır ki arayüz donmasın
        t = threading.Thread(target=self.process_images_job)
        t.start()

    def process_images_job(self):
        total_images = len(self.image_paths)
        success_count = 0
        
        try:
            # 1. Bağlantı ve motor kontrolü
            try:
                requests.get("http://127.0.0.1:8899/api/health", timeout=2)
                engine_str = "paddle" if self.engine_var.get() == "PaddleOCR" else "glm-ocr"
                requests.post("http://127.0.0.1:8899/api/ocr-engine", data={"engine": engine_str}, timeout=2)
            except Exception as e:
                raise Exception("Backend kapalı veya motor güncellenemiyor.")

            for i, img_path in enumerate(self.image_paths):
                # UI Güncellemesi
                self.after(0, lambda idx=i: self.status_label.configure(
                    text=f"İşleniyor: {idx+1} / {total_images} görsel yapay zekaya gönderildi...", 
                    text_color="orange"
                ))
                
                try:
                    self.process_single_image(img_path)
                    success_count += 1
                except Exception as img_exc:
                    print(f"Hata ({os.path.basename(img_path)}): {img_exc}")
                    
                # Progress Güncelle
                progress = (i + 1) / total_images
                self.after(0, lambda p=progress: self.progress_bar.set(p))

            # Döngü Bitti
            msg = f"✅ Çeviri Tamamlandı! ({success_count}/{total_images} başarılı)\nKayıt Yeri: {self.out_dir}"
            self.after(0, lambda: self.finish_processing(msg, "green"))

        except Exception as e:
            error_msg = f"HATA: {str(e)}"
            self.after(0, lambda: self.finish_processing(error_msg, "red"))

    def process_single_image(self, image_path):
        with open(image_path, "rb") as f:
            files = {"image": (os.path.basename(image_path), f, "image/png")}
            data = {"target_lang": "tr"}
            response = requests.post(API_URL, files=files, data=data, timeout=120)

        if response.status_code != 200:
            raise Exception(f"Backend API Hatası ({response.status_code})")

        res_json = response.json()
        if not res_json.get("success"):
            raise Exception(res_json.get("message", "Bilinmeyen API hatası."))

        translations = res_json.get("translations", [])
        if not translations:
            return # Metin yoksa orijinalini kaydetmeye bile gerek yok veya kopyalayabiliriz, atlıyoruz.

        # 2. Resmi çiz (Pillow)
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        # Kullanıcının seçtiği fontu al
        selected_font_raw = self.font_var.get()
        font_map = {
            "Arial (Varsayılan)": "arialbd.ttf",
            "Comic Sans MS": "comicbd.ttf", # Çizgi romanlarda sık kullanılır
            "Impact": "impact.ttf",
            "Georgia": "georgiab.ttf",
            "Verdana": "verdanab.ttf",
            "Tahoma": "tahoma.ttf"
        }
        font_name = font_map.get(selected_font_raw, "arialbd.ttf")

        try:
            ImageFont.truetype(font_name, 20)
        except:
            font_name = "arial.ttf" # Fallback

        for t in translations:
            pts = t['bbox']
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)
            
            # Padding
            pad = 12
            x1 = max(0, x1 - pad)
            y1 = max(0, y1 - pad)
            x2 = min(img.width, x2 + pad)
            y2 = min(img.height, y2 + pad)
            
            bw = x2 - x1
            bh = y2 - y1

            if bw <= 0 or bh <= 0:
                continue

            # Arka plan rengini otomatik algıla (Kutunun kenarlarından örnek alarak)
            border_pixels = []
            for px in range(x1, x2, max(1, bw//10)):
                border_pixels.append(img.getpixel((px, y1)))
                border_pixels.append(img.getpixel((px, max(y1, y2 - 1))))
            for py in range(y1, y2, max(1, bh//10)):
                border_pixels.append(img.getpixel((x1, py)))
                border_pixels.append(img.getpixel((max(x1, x2 - 1), py)))
            
            # En çok tekrar eden rengi bul
            if border_pixels:
                bg_color = Counter(border_pixels).most_common(1)[0][0]
            else:
                bg_color = (255, 255, 255)
            
            # Yazı rengini arka plana zıt seç (Parlaklık formülü)
            luminance = (0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2])
            text_color = (0, 0, 0) if luminance > 128 else (255, 255, 255)

            # Konuşma balonunu dinamik renkle ört
            draw.rounded_rectangle([x1, y1, x2, y2], radius=15, fill=bg_color)

            translated_text = t.get('translated_text', '')
            if not translated_text or "[Çeviri hatası" in translated_text:
                translated_text = t.get('original_text', '') # Eğer çeviri boş veya hatalı döndüyse en kötü orijinal / ingilizce metni beyazlaştırıp üstüne yaz ki balonlar boş beyaz kalmasın.
                if not translated_text:
                    continue

            font_size = 40
            selected_font = None
            lines = []
            
            while font_size > 12:
                try:
                    fnt = ImageFont.truetype(font_name, font_size)
                except:
                    fnt = ImageFont.load_default()
                
                lines = wrap_text_to_fit(draw, translated_text, fnt, max_width=bw * 0.90)
                margin_y = 6
                total_h = sum([fnt.getbbox(l)[3] - fnt.getbbox(l)[1] for l in lines]) + (len(lines) - 1) * margin_y
                
                if total_h < bh * 0.85:
                    selected_font = fnt
                    break
                font_size -= 2
            
            if not selected_font:
                selected_font = ImageFont.truetype(font_name, 12) if font_name else ImageFont.load_default()
                lines = wrap_text_to_fit(draw, translated_text, selected_font, bw * 0.95)
                margin_y = 4
                total_h = sum([selected_font.getbbox(l)[3] - selected_font.getbbox(l)[1] for l in lines]) + (len(lines) - 1) * margin_y

            current_y = y1 + (bh - total_h) / 2
            for line in lines:
                line_w = draw.textlength(line, font=selected_font)
                line_x = x1 + (bw - line_w) / 2
                draw.text((line_x, current_y), line, font=selected_font, fill=text_color)
                current_y += (selected_font.getbbox(line)[3] - selected_font.getbbox(line)[1]) + margin_y

        # 3. Kaydet
        base_name = os.path.basename(image_path)
        name_part, ext_part = os.path.splitext(base_name)
        save_name = f"{name_part}_tr{ext_part}"
        final_path = os.path.join(self.out_dir, save_name)

        img.save(final_path)

    def finish_processing(self, msg, color):
        self.translate_btn.configure(state="normal", text="⚡ Seçili Tüm Sayfaları Çevir")
        self.status_label.configure(text=msg, text_color=color)
        if color == "green":
            messagebox.showinfo("Başarılı", msg)
        elif color == "red":
            messagebox.showerror("Hata", msg)

if __name__ == "__main__":
    app = ManhwaTranslatorApp()
    app.mainloop()
