import os, random, asyncio, json
import google.generativeai as genai
import edge_tts
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def get_youtube():
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    return build("youtube", "v3", credentials=creds)

def generar_tema(idioma):
    nichos = [
        "easter egg oculto en GTA, Fortnite, Minecraft, Roblox, Warzone",
        "curiosidad viral de E-Sports",
        "secreto o truco viral de juego popular",
        "noticia viral de gaming de hoy"
    ]
    prompt = f"Dame 1 tema MUY viral de hoy sobre {random.choice(nichos)}, en {idioma}. Devolveme solo JSON: {{\"titulo\": \"...\", \"guion\": \"...\"}}"
    resp = model.generate_content(prompt).text
    # Limpia el JSON si viene con ```json
    resp = resp.replace("```json","").replace("```","").strip()
    return json.loads(resp)

async def crear_voz(texto, idioma):
    voz = "es-MX-JorgeNeural" if idioma == "espanol" else "en-US-GuyNeural"
    await edge_tts.Communicate(texto, voz).save("voz.mp3")

def crear_video(titulo):
    # Aca usa moviepy: fondo + subtitulos grandes
    # Para la version simple usamos un fondo de color + audio
    # En la version full podes poner gameplay de fondo
    from moviepy.editor import ColorClip, AudioFileClip, TextClip, CompositeVideoClip
    audio = AudioFileClip("voz.mp3")
    dur = min(audio.duration, 58) # Short
    clip = ColorClip(size=(1080,1920), color=(15,0,30), duration=dur)
    txt = TextClip(titulo, fontsize=70, color='white', size=(900,None), method='caption')
    txt = txt.set_position('center').set_duration(dur)
    video = CompositeVideoClip([clip, txt]).set_audio(audio)
    video.write_videofile("short.mp4", fps=24, codec="libx264", audio_codec="aac")

def subir(youtube, archivo, titulo, desc, es_short):
    body = {
        "snippet": {"title": titulo[:100], "description": desc, "tags": ["gaming","easteregg","slowning"], "categoryId": "20"},
        "status": {"privacyStatus": "public", "madeForKids": False}
    }
    if es_short:
        body["snippet"]["title"] = titulo[:95] + " #Shorts"
    media = MediaFileUpload(archivo, mimetype="video/mp4", resumable=True)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    req.execute()
    print("Subido:", titulo)

async def main():
    # Varia idioma: 50% español, 50% ingles
    idioma = random.choice(["espanol", "espanol", "ingles"])
    data = generar_tema(idioma)
    await crear_voz(data["guion"], idioma)
    crear_video(data["titulo"])
    yt = get_youtube()
    subir(yt, "short.mp4", data["titulo"], data["guion"][:200] + "\n\n@Slowning", True)

asyncio.run(main())
