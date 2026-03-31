import os
import sys
import argparse
import threading
import yt_dlp
import uuid
import shutil
import subprocess
import math
import random
import string
import asyncio
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import helper

app = Flask(__name__)

download_options = {}
active_callbacks = {}

async def cleanup_callback(callback_id, chat_id, message_id):
    await asyncio.sleep(60)
    if callback_id in active_callbacks:
        del active_callbacks[callback_id]
    if callback_id in download_options:
        del download_options[callback_id]

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
            formats = []
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    height = f.get('height', 0)
                    if height:
                        size_mb = None
                        if f.get('filesize'):
                            size_mb = f.get('filesize') / (1024 * 1024)
                        elif f.get('filesize_approx'):
                            size_mb = f.get('filesize_approx') / (1024 * 1024)
                        
                        formats.append({
                            'format_id': f['format_id'],
                            'height': height,
                            'size_mb': size_mb
                        })
            
            formats.sort(key=lambda x: x['height'], reverse=True)
            unique_formats = []
            seen_heights = set()
            for f in formats:
                if f['height'] not in seen_heights:
                    seen_heights.add(f['height'])
                    unique_formats.append(f)
            
            return {
                'duracion': info.get('duration', 0),
                'ancho': info.get('width', 0),
                'alto': info.get('height', 0),
                'titulo': info.get('title', ''),
                'formats': unique_formats[:5]
            }
    except Exception as e:
        print(f"Error obteniendo info: {e}")
        return {'duracion': 0, 'ancho': 0, 'alto': 0, 'titulo': '', 'formats': []}

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
        
        partes_generadas = []
        for archivo in os.listdir(output_dir):
            if archivo.startswith(nombre_base) and "_parte_" in archivo and archivo.endswith('.mp4'):
                partes_generadas.append(os.path.join(output_dir, archivo))
        
        partes_generadas.sort()
        return partes_generadas if partes_generadas else None
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
        
        @self.app.on_callback_query()
        async def handle_callback(client: Client, callback_query: CallbackQuery):
            await self._handle_callback(client, callback_query)
    
    async def _handle_callback(self, client: Client, callback_query: CallbackQuery):
        data = callback_query.data
        
        if data.startswith("download_"):
            parts = data.split("_")
            if len(parts) >= 3:
                callback_id = parts[1]
                format_id = "_".join(parts[2:])
            else:
                await callback_query.answer("Error en el formato")
                return
            
            if callback_id in download_options:
                info = download_options[callback_id]
                
                await callback_query.answer("⬇ Iniciando descarga...")
                await callback_query.message.edit_text("⬇ Procesando tu descarga...")
                
                temp_dir = None
                
                try:
                    temp_dir = os.path.join(os.getcwd(), f"temp_{uuid.uuid4().hex}")
                    os.makedirs(temp_dir, exist_ok=True)
                    
                    resultado = helper.descargar_video_con_formato(info['url'], format_id, output_path=temp_dir)
                    
                    if resultado and resultado[0] and os.path.exists(resultado[0]):
                        ruta_video, ruta_thumb = resultado
                        tamano_video = os.path.getsize(ruta_video) / (1024 * 1024)
                        
                        if tamano_video > self.tamano_limite:
                            await callback_query.message.reply(f"📦 Video de {tamano_video:.1f} MB excede el límite de {self.tamano_limite} MB. Dividiendo en partes...")
                            
                            nombre_base = os.path.splitext(os.path.basename(ruta_video))[0]
                            partes = dividir_video_por_tamano(ruta_video, self.tamano_limite, temp_dir, nombre_base)
                            
                            if partes:
                                await callback_query.message.reply(f"✅ Video dividido en {len(partes)} partes")
                                
                                for idx, parte in enumerate(partes):
                                    duracion_parte = obtener_duracion_video(parte)
                                    tamano_parte = os.path.getsize(parte) / (1024 * 1024)
                                    
                                    caption = f"📹 {info['titulo']} - Parte {idx+1}/{len(partes)}\n⏱️ Duración: {int(duracion_parte // 60)}:{int(duracion_parte % 60):02d}\n📦 Tamaño: {tamano_parte:.1f} MB"
                                    
                                    if ruta_thumb and os.path.exists(ruta_thumb):
                                        await client.send_video(
                                            chat_id=callback_query.message.chat.id,
                                            video=parte,
                                            file_name=os.path.basename(parte),
                                            duration=int(duracion_parte),
                                            width=info['ancho'],
                                            height=info['alto'],
                                            thumb=ruta_thumb,
                                            caption=caption
                                        )
                                    else:
                                        await client.send_video(
                                            chat_id=callback_query.message.chat.id,
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
                                await callback_query.message.reply("❌ Error al dividir el video")
                        else:
                            if ruta_thumb and os.path.exists(ruta_thumb):
                                await client.send_video(
                                    chat_id=callback_query.message.chat.id,
                                    video=ruta_video,
                                    file_name=os.path.basename(ruta_video),
                                    duration=info['duracion'],
                                    width=info['ancho'],
                                    height=info['alto'],
                                    thumb=ruta_thumb,
                                    caption=f"✅ {info['titulo']}\n⏱️ Duración: {info['duracion']//60}:{info['duracion']%60:02d}\n📦 Tamaño: {tamano_video:.1f} MB"
                                )
                            else:
                                await client.send_video(
                                    chat_id=callback_query.message.chat.id,
                                    video=ruta_video,
                                    file_name=os.path.basename(ruta_video),
                                    duration=info['duracion'],
                                    width=info['ancho'],
                                    height=info['alto'],
                                    caption=f"✅ {info['titulo']}\n⏱️ Duración: {info['duracion']//60}:{info['duracion']%60:02d}\n📦 Tamaño: {tamano_video:.1f} MB"
                                )
                        
                        if not self.debug:
                            if os.path.exists(ruta_video):
                                os.remove(ruta_video)
                            if ruta_thumb and os.path.exists(ruta_thumb):
                                os.remove(ruta_thumb)
                            if temp_dir and os.path.exists(temp_dir):
                                shutil.rmtree(temp_dir)
                    else:
                        await callback_query.message.reply("❌ Error al descargar el video")
                        
                except Exception as e:
                    await callback_query.message.reply(f"❌ Error: {str(e)}")
                    if self.debug and temp_dir:
                        await callback_query.message.reply(f"🐛 Debug: Error, archivos conservados en: {temp_dir}")
                
                if callback_id in download_options:
                    del download_options[callback_id]
                if callback_id in active_callbacks:
                    del active_callbacks[callback_id]
                
                await callback_query.message.delete()
        
        elif data.startswith("cancel_"):
            callback_id = data.replace("cancel_", "")
            
            if callback_id in download_options:
                del download_options[callback_id]
            if callback_id in active_callbacks:
                del active_callbacks[callback_id]
            
            await callback_query.answer("Descarga cancelada")
            await callback_query.message.edit_text("❌ Descarga cancelada")
            await asyncio.sleep(3)
            await callback_query.message.delete()
    
    async def _handle_message(self, client: Client, message: Message):
        if not message.text:
            return
        
        text = message.text.strip()

        if text.startswith("/start"):
            await message.reply("Bot is running!")
        
        elif text.startswith("https://you") or text.startswith("https://www.youtube"):
            await message.reply("⬇ Obteniendo información del video...")
            
            try:
                info = obtener_info_youtube(text)
                
                if not info['formats']:
                    await message.reply("❌ No se encontraron formatos disponibles")
                    return
                
                callback_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
                
                download_options[callback_id] = {
                    'url': text,
                    'titulo': info['titulo'],
                    'duracion': info['duracion'],
                    'ancho': info['ancho'],
                    'alto': info['alto']
                }
                
                active_callbacks[callback_id] = {
                    'chat_id': message.chat.id,
                    'message_id': None
                }
                
                buttons = []
                for fmt in info['formats']:
                    size_text = f" - {fmt['size_mb']:.1f} MB" if fmt['size_mb'] else ""
                    button_text = f"{fmt['height']}p{size_text}"
                    buttons.append([InlineKeyboardButton(button_text, callback_data=f"download_{callback_id}_{fmt['format_id']}")])
                
                buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data=f"cancel_{callback_id}")])
                
                keyboard = InlineKeyboardMarkup(buttons)
                
                msg = await message.reply(
                    f"📹 {info['titulo']}\n⏱️ Duración: {info['duracion']//60}:{info['duracion']%60:02d}\n\nSelecciona la calidad:",
                    reply_markup=keyboard
                )
                
                active_callbacks[callback_id]['message_id'] = msg.id
                
                asyncio.create_task(cleanup_callback(callback_id, message.chat.id, msg.id))
                
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
    
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
