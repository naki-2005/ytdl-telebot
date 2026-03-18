import os
import sys
import argparse
import threading
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

class NekoTelegram:
    def __init__(self, api_id, api_hash, bot_token):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.app = Client("nekobot", api_id=int(api_id), api_hash=api_hash, bot_token=bot_token)
        self.flask_thread = None
        self.cookies_path = "cookies.txt"
        
        @self.app.on_message(filters.private)
        async def handle_message(client: Client, message: Message):
            await self._handle_message(client, message)
    
    async def _handle_message(self, client: Client, message: Message):
        if not message.text and not message.document:
            return
        
        text = message.text.strip() if message.text else ""

        if text.startswith("/start"):
            await message.reply("Bot is running!\nUsa /set para subir un archivo de cookies (máx 10MB)")
        
        elif text.startswith("/set"):
            await message.reply("Envía el archivo cookies.txt (máx 10MB)")
        
        elif message.document:
            if message.document.file_size > 10 * 1024 * 1024:
                await message.reply("❌ El archivo es mayor de 10MB")
                return
            
            if message.reply_to_message and message.reply_to_message.text == "Envía el archivo cookies.txt (máx 10MB)":
                await message.reply("⬇ Guardando cookies...")
                await message.download(file_name=self.cookies_path)
                await message.reply("✅ Cookies guardadas correctamente")
        
        elif text.startswith("https://you"):
            if not os.path.exists(self.cookies_path):
                await message.reply("❌ No hay cookies guardadas. Usa /set primero")
                return
            
            await message.reply("⬇ Procesando tu enlace...")
            try:
                ruta = helper.descargar_video(text, cookies_file=self.cookies_path)
                if ruta and os.path.exists(ruta):
                    await message.reply_document(document=ruta, caption="✅ Video descargado")
                    os.remove(ruta)
                else:
                    await message.reply("❌ Error al descargar el video")
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
    args = parser.parse_args()

    api_id = args.api or os.environ.get("API_ID")
    api_hash = args.hash or os.environ.get("API_HASH")
    bot_token = args.token or os.environ.get("BOT_TOKEN")
    
    if not all([api_id, api_hash, bot_token]):
        print("Error: Faltan credenciales")
        sys.exit(1)
    
    bot = NekoTelegram(api_id, api_hash, bot_token)

    if args.flask:
        bot.start_flask()
    
    bot.run()

if __name__ == "__main__":
    main()
