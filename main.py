import os, random, subprocess, json
import google.generativeai as genai
import edge_tts

# Secrets desde GitHub, NUNCA en el codigo
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
YT_CLIENT_ID = os.environ["YT_CLIENT_ID"]
YT_CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
YT_REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

NICHOS = [
    "curiosidad viral de GTA, Fortnite, Minecraft, Free Fire, Warzone, Roblox",
    "easter egg oculto en juego conocido",
    "noticia viral de E-Sports",
    "truco secreto de juego popular"
]

def elegir_tema(idioma):
    prompt = f"Eres experto en YouTube. Dame 1 tema MUY viral hoy sobre {random.choice(NICHOS)}, en {idioma}. Solo titulo + 3 datos curiosos."
    return model.generate_content(prompt).text

def generar_guion(tema, idioma, duracion="short"):
    prompt = f"Escribe un guion para un {'Short de 50 segundos' if duracion=='short' else 'video de 7 minutos'} en {idioma} sobre: {tema}. Estilo Slowning, directo, con gancho fuerte al inicio, voz masculina. Incluye titulo viral y descripcion con hashtags."
    return model.generate_content(prompt).text

async def generar_voz(texto, idioma, salida="voz.mp3"):
    voz = "es-MX-JorgeNeural" if idioma == "espanol" else "en-US-GuyNeural"
    communicate = edge_tts.Communicate(texto, voz)
    await communicate.save(salida)
    return salida

# Aca despues conectamos: guion -> voz -> video con moviepy + subtitulos -> subida a YouTube con YouTube Data API v3
# Por ahora este archivo ya genera tema + guion + voz gratis
