import yt_dlp
import os
import time

MAX_REINTENTOS = 3
ESPERA_REINTENTO = 5
FRAGMENTOS_CONCURRENTES = 3

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
                'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                'quiet': True,
                'no_warnings': True,
                'continuedl': True,
                'concurrent_fragment_downloads': FRAGMENTOS_CONCURRENTES,
                'retries': 10
            }
            
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                titulo = info.get('title', 'video')
                
                if output_path:
                    ruta_esperada = os.path.join(output_path, f"{titulo}.mp4")
                else:
                    ruta_esperada = f"{titulo}.mp4"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            print(f"✅ Video descargado: {ruta_esperada}")
            return ruta_esperada
            
        except Exception as e:
            print(f"❌ Error: {e}")
            if intento < MAX_REINTENTOS:
                print(f"🔄 Reintentando en {ESPERA_REINTENTO} segundos...")
                time.sleep(ESPERA_REINTENTO)
            else:
                print("🚫 No se pudo completar la descarga.")
                return None