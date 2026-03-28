import yt_dlp
import os
import time
import glob
from PIL import Image

MAX_REINTENTOS = 3
ESPERA_REINTENTO = 5
FRAGMENTOS_CONCURRENTES = 3

def convertir_webp_a_jpg(ruta_webp):
    try:
        ruta_jpg = ruta_webp.replace('.webp', '.jpg')
        with Image.open(ruta_webp) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                fondo = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                fondo.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                fondo.save(ruta_jpg, 'JPEG', quality=95)
            else:
                img.convert('RGB').save(ruta_jpg, 'JPEG', quality=95)
        os.remove(ruta_webp)
        return ruta_jpg
    except Exception as e:
        print(f"Error convirtiendo WEBP a JPG: {e}")
        return None

def descargar_video(url, output_path=None):
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            print(f"⬇ Intento {intento}/{MAX_REINTENTOS}...")
            
            if output_path:
                outtmpl = os.path.join(output_path, '%(title)s.%(ext)s')
            else:
                outtmpl = '%(title)s.%(ext)s'
            
            ydl_opts = {
                'outtmpl': outtmpl,
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'continuedl': True,
                'concurrent_fragment_downloads': FRAGMENTOS_CONCURRENTES,
                'retries': 10,
                'writethumbnail': True,
                'convert_thumbnails': 'jpg'
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                titulo = info.get('title', 'video')
                extension = info.get('ext', 'mp4')
                
                if output_path:
                    ruta_video = os.path.join(output_path, f"{titulo}.{extension}")
                else:
                    ruta_video = f"{titulo}.{extension}"
                
                ruta_thumb = None
                nombre_base = os.path.splitext(ruta_video)[0]
                
                archivos_thumb = glob.glob(f"{nombre_base}.jpg")
                if archivos_thumb:
                    ruta_thumb = archivos_thumb[0]
                    print(f"✅ Miniatura JPG encontrada: {ruta_thumb}")
                else:
                    archivos_thumb = glob.glob(f"{nombre_base}.webp")
                    if archivos_thumb:
                        print(f"🔄 Convirtiendo WEBP a JPG: {archivos_thumb[0]}")
                        ruta_thumb = convertir_webp_a_jpg(archivos_thumb[0])
                        if ruta_thumb:
                            print(f"✅ Miniatura convertida a JPG: {ruta_thumb}")
                        else:
                            print(f"⚠️ Error al convertir miniatura")
                            ruta_thumb = None
                    else:
                        print(f"⚠️ No se encontró miniatura para: {titulo}")
                        ruta_thumb = None
                
                print(f"✅ Video descargado: {ruta_video}")
                return ruta_video, ruta_thumb
            
        except Exception as e:
            print(f"❌ Error: {e}")
            if intento < MAX_REINTENTOS:
                print(f"🔄 Reintentando en {ESPERA_REINTENTO} segundos...")
                time.sleep(ESPERA_REINTENTO)
            else:
                print("🚫 No se pudo completar la descarga.")
                return None
