import os
import sys
import argparse
import threading
import yt_dlp
import uuid
import shutil
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

class NekoTelegram:
    def __init__(self, api_id, api_hash, bot_token, debug=False):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.debug = debug
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
                        if ruta_thumb and os.path.exists(ruta_thumb):
                            await client.send_video(
                                chat_id=message.chat.id,
                                video=ruta_video,
                                file_name=os.path.basename(ruta_video),
                                duration=info['duracion'],
                                width=info['ancho'],
                                height=info['alto'],
                                thumb=ruta_thumb,
                                caption=f"✅ {info['titulo']}"
                            )
                            if self.debug:
                                await message.reply(f"🐛 Debug: Video enviado con miniatura")
                        else:
                            await client.send_video(
                                chat_id=message.chat.id,
                                video=ruta_video,
                                file_name=os.path.basename(ruta_video),
                                duration=info['duracion'],
                                width=info['ancho'],
                                height=info['alto'],
                                caption=f"✅ {info['titulo']}"
                            )
                            if self.debug:
                                await message.reply(f"🐛 Debug: Video enviado sin miniatura")
                        
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
    args = parser.parse_args()

    api_id = args.api or os.environ.get("API_ID")
    api_hash = args.hash or os.environ.get("API_HASH")
    bot_token = args.token or os.environ.get("BOT_TOKEN")
    
    if not all([api_id, api_hash, bot_token]):
        print("Error: Faltan credenciales")
        sys.exit(1)
    
    bot = NekoTelegram(api_id, api_hash, bot_token, debug=args.debug)

    if args.flask:
        bot.start_flask()
    
    bot.run()

if __name__ == "__main__":
    main()
