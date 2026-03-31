import os
import sys
import argparse
import threading
import yt_dlp
import uuid
import shutil
import subprocess
import math
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message
import helper

app = Flask(__name__)

@app.route("/")
def base_flask():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

def obtener_info_youtube(url):
    try:
        opciones = {
            'quiet': True,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'duracion': info.get('duration', 0),
                'ancho': info.get('width', 0),
                'alto': info.get('height', 0),
                'titulo': info.get('title', '')
            }
    except Exception as e:
        print(f"Error obteniendo info: {e}")
        return {'duracion': 0, 'ancho': 0, 'alto': 0, 'titulo': ''}

def obtener_bitrate_video(ruta_video):
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=bit_rate', '-of', 'default=noprint_wrappers=1:nokey=1',
            ruta_video
        ]
        resultado = subprocess.run(cmd, capture_output=True, text=True)
        
        if resultado.stdout.strip():
            return int(resultado.stdout.strip())
        
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=bit_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1', ruta_video
        ]
        resultado = subprocess.run(cmd, capture_output=True, text=True)
        return int(resultado.stdout.strip()) if resultado.stdout.strip() else 0
    except:
        return 0

def obtener_duracion_video(ruta_video):
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', ruta_video
        ]
        resultado = subprocess.run(cmd, capture_output=True, text=True)
        return float(resultado.stdout.strip())
    except:
        return 0

def dividir_video_por_tamano(ruta_video, tamano_mb, output_dir, nombre_base):
    try:
        bitrate = obtener_bitrate_video(ruta_video)
        duracion_total = obtener_duracion_video(ruta_video)
        
        if bitrate == 0 or duracion_total == 0:
            return None
        
        tamano_bytes = tamano_mb * 1024 * 1024
        segundos_por_parte = tamano_bytes / (bitrate / 8)
        num_partes = math.ceil(duracion_total / segundos_por_parte)
        duracion_parte = duracion_total / num_partes
        
        partes_generadas = []
        
        for i in range(num_partes):
            inicio = i * duracion_parte
            duracion = duracion_parte
            
            if i == num_partes - 1:
                duracion = duracion_total - inicio
            
            salida = os.path.join(output_dir, f"{nombre_base}_parte_{i+1:03d}.mp4")
            
            cmd = [
                'ffmpeg', '-i', ruta_video,
                '-ss', str(inicio),
                '-t', str(duracion),
                '-c', 'copy',
                '-avoid_negative_ts', 'make_zero',
                salida,
                '-y'
            ]
            
            subprocess.run(cmd, capture_output=True)
            
            if os.path.exists(salida):
                partes_generadas.append(salida)
        
        return partes_generadas
    except:
        return None

class NekoTelegram:
    def __init__(self, api_id, api_hash, bot_token, debug=False, modo_grande=False):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.debug = debug
        self.modo_grande = modo_grande
        self.tamano_limite = 3995 if modo_grande else 1995
        self.app = Client("nekobot", api_id=int(api_id), api_hash=api_hash, bot_token=bot_token)
        self.flask_thread = None
        
        @self.app.on_message(filters.private)
        async def handle_message(client: Client, message: Message):
            await self._handle_message(client, message)
    
    async def _handle_message(self, client: Client, message: Message):
        if not message.text:
            return
        
        text = message.text.strip()

        if text.startswith("/start"):
            await message.reply("Bot is running!")
        
        elif text.startswith("https://you"):
            await message.reply("⬇ Procesando tu enlace...")
            
            temp_dir = None
            
            try:
                info = obtener_info_youtube(text)
                
                temp_dir = os.path.join(os.getcwd(), f"temp_{uuid.uuid4().hex}")
                os.makedirs(temp_dir, exist_ok=True)
                
                if self.debug:
                    await message.reply(f"🐛 Debug: Carpeta temporal creada en {temp_dir}")
                    await message.reply(f"🐛 Debug: Límite de tamaño: {self.tamano_limite} MB")
                
                resultado = helper.descargar_video(text, output_path=temp_dir)
                
                if resultado:
                    ruta_video, ruta_thumb = resultado
                    
                    if self.debug:
                        await message.reply(f"🐛 Debug: Video: {ruta_video}")
                        if ruta_thumb:
                            await message.reply(f"🐛 Debug: Thumb: {ruta_thumb}")
                        else:
                            await message.reply(f"🐛 Debug: No se encontró miniatura")
                    
                    if ruta_video and os.path.exists(ruta_video):
                        tamano_video = os.path.getsize(ruta_video) / (1024 * 1024)
                        
                        if self.debug:
                            await message.reply(f"🐛 Debug: Tamaño del video: {tamano_video:.1f} MB")
                        
                        if tamano_video > self.tamano_limite:
                            await message.reply(f"📦 Video de {tamano_video:.1f} MB excede el límite de {self.tamano_limite} MB. Dividiendo en partes...")
                            
                            nombre_base = os.path.splitext(os.path.basename(ruta_video))[0]
                            partes = dividir_video_por_tamano(ruta_video, self.tamano_limite, temp_dir, nombre_base)
                            
                            if partes:
                                await message.reply(f"✅ Video dividido en {len(partes)} partes")
                                
                                for idx, parte in enumerate(partes):
                                    duracion_parte = obtener_duracion_video(parte)
                                    tamano_parte = os.path.getsize(parte) / (1024 * 1024)
                                    minutos = int(duracion_parte // 60)
                                    segundos = int(duracion_parte % 60)
                                    
                                    caption = f"📹 {info['titulo']} - Parte {idx+1}/{len(partes)}\n⏱️ Duración: {minutos}:{segundos:02d}\n📦 Tamaño: {tamano_parte:.1f} MB"
                                    
                                    if ruta_thumb and os.path.exists(ruta_thumb):
                                        with open(ruta_thumb, 'rb') as f:
                                            thumb_data = f.read()
                                        await client.send_video(
                                            chat_id=message.chat.id,
                                            video=parte,
                                            file_name=os.path.basename(parte),
                                            duration=int(duracion_parte),
                                            width=info['ancho'],
                                            height=info['alto'],
                                            thumb=thumb_data,
                                            caption=caption
                                        )
                                    else:
                                        await client.send_video(
                                            chat_id=message.chat.id,
                                            video=parte,
                                            file_name=os.path.basename(parte),
                                            duration=int(duracion_parte),
                                            width=info['ancho'],
                                            height=info['alto'],
                                            caption=caption
                                        )
                                    
                                    if not self.debug:
                                        os.remove(parte)
                            else:
                                await message.reply("❌ Error al dividir el video")
                        else:
                            minutos = int(info['duracion'] // 60)
                            segundos = int(info['duracion'] % 60)
                            caption = f"✅ {info['titulo']}\n⏱️ Duración: {minutos}:{segundos:02d}\n📦 Tamaño: {tamano_video:.1f} MB"
                            
                            if ruta_thumb and os.path.exists(ruta_thumb):
                                with open(ruta_thumb, 'rb') as f:
                                    thumb_data = f.read()
                                await client.send_video(
                                    chat_id=message.chat.id,
                                    video=ruta_video,
                                    file_name=os.path.basename(ruta_video),
                                    duration=info['duracion'],
                                    width=info['ancho'],
                                    height=info['alto'],
                                    thumb=thumb_data,
                                    caption=caption
                                )
                            else:
                                await client.send_video(
                                    chat_id=message.chat.id,
                                    video=ruta_video,
                                    file_name=os.path.basename(ruta_video),
                                    duration=info['duracion'],
                                    width=info['ancho'],
                                    height=info['alto'],
                                    caption=caption
                                )
                        
                        if not self.debug:
                            if os.path.exists(ruta_video):
                                os.remove(ruta_video)
                            if ruta_thumb and os.path.exists(ruta_thumb):
                                os.remove(ruta_thumb)
                            if temp_dir and os.path.exists(temp_dir):
                                shutil.rmtree(temp_dir)
                        else:
                            await message.reply(f"🐛 Debug: Modo debug activado. Archivos conservados en: {temp_dir}")
                    else:
                        await message.reply("❌ No se encontró el archivo de video")
                else:
                    await message.reply("❌ Error al descargar el video")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
                if self.debug and temp_dir:
                    await message.reply(f"🐛 Debug: Error, archivos conservados en: {temp_dir}")
    
    def start_flask(self):
        if self.flask_thread and self.flask_thread.is_alive():
            return
            
        self.flask_thread = threading.Thread(target=run_flask, daemon=True)
        self.flask_thread.start()
    
    def run(self):
        self.app.run()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-A", "--api", help="API ID")
    parser.add_argument("-H", "--hash", help="API Hash")
    parser.add_argument("-T", "--token", help="Bot Token")
    parser.add_argument("-F", "--flask", action="store_true", help="Incluir Flask")
    parser.add_argument("-D", "--debug", action="store_true", help="Modo debug: no eliminar archivos")
    parser.add_argument("-P", "--grande", action="store_true", help="Modo grande: límite de 3995 MB en lugar de 1995 MB")
    args = parser.parse_args()

    api_id = args.api or os.environ.get("API_ID")
    api_hash = args.hash or os.environ.get("API_HASH")
    bot_token = args.token or os.environ.get("BOT_TOKEN")
    
    if not all([api_id, api_hash, bot_token]):
        print("Error: Faltan credenciales")
        sys.exit(1)
    
    bot = NekoTelegram(api_id, api_hash, bot_token, debug=args.debug, modo_grande=args.grande)

    if args.flask:
        bot.start_flask()
    
    bot.run()

if __name__ == "__main__":
    main()
