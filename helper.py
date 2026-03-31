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

def descargar_video_con_formato(url, format_id, output_path=None):
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            print(f"⬇ Intento {intento}/{MAX_REINTENTOS}...")
            
            if output_path:
                os.makedirs(output_path, exist_ok=True)
                outtmpl = os.path.join(output_path, '%(title)s.%(ext)s')
            else:
                outtmpl = '%(title)s.%(ext)s'
            
            ydl_opts = {
                'outtmpl': outtmpl,
                'format': format_id,
                'quiet': True,
                'no_warnings': True,
                'continuedl': True,
                'retries': 10,
                'writethumbnail': True,
                'postprocessors': [{
                    'key': 'FFmpegThumbnailsConvertor',
                    'format': 'jpg',
                    'when': 'before_dl'
                }]
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                titulo = info.get('title', 'video')
                extension = info.get('ext', 'mp4')
                
                if output_path:
                    ruta_video = os.path.join(output_path, f"{titulo}.{extension}")
                else:
                    ruta_video = f"{titulo}.{extension}"
                
                if not os.path.exists(ruta_video):
                    posibles = glob.glob(os.path.join(output_path, f"{titulo}.*")) if output_path else glob.glob(f"{titulo}.*")
                    if posibles:
                        ruta_video = posibles[0]
                    else:
                        return None, None
                
                ruta_thumb = None
                nombre_base = os.path.splitext(ruta_video)[0]
                
                archivos_thumb = glob.glob(f"{nombre_base}.jpg")
                if archivos_thumb:
                    ruta_thumb = archivos_thumb[0]
                else:
                    archivos_thumb = glob.glob(f"{nombre_base}.webp")
                    if archivos_thumb:
                        ruta_thumb = convertir_webp_a_jpg(archivos_thumb[0])
                
                return ruta_video, ruta_thumb
            
        except Exception as e:
            print(f"❌ Error en intento {intento}: {e}")
            if intento < MAX_REINTENTOS:
                print(f"🔄 Reintentando en {ESPERA_REINTENTO} segundos...")
                time.sleep(ESPERA_REINTENTO)
            else:
                return None, None
    
    return None, None
