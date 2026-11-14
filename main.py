import os, random, asyncio, json
from google import genai
import edge_tts
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Cliente Gemini nuevo, ya corregido
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

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
    prompt = f"Dame 1 tema MUY viral de hoy sobre {random.choice(nichos)}, en {idioma}. Devolveme solo JSON, sin markdown: {{\"titulo\": \"...\", \"guion\": \"...\"}} El guion debe ser para un Short de 50 segundos, estilo Slowning, directo, con gancho fuerte al inicio."
    resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt).text
    resp = resp.replace("```json", "").replace("```", "").strip()
    return json.loads(resp)

async def crear_voz(texto, idioma):
    voz = "es-MX-JorgeNeural" if idioma == "espanol" else "en-US-GuyNeural"
    await edge_tts.Communicate(texto, voz).save("voz.mp3")

def crear_video(titulo):
    from moviepy.editor import ColorClip, AudioFileClip, TextClip, CompositeVideoClip
    audio = AudioFileClip("voz.mp3")
    dur = min(audio.duration, 58)
    clip = ColorClip(size=(1080, 1920), color=(15, 0, 30), duration=dur)
    txt = TextClip(titulo, fontsize=70, color='white', size=(900, None), method='caption')
    txt = txt.set_position('center').set_duration(dur)
    video = CompositeVideoClip([clip, txt]).set_audio(audio)
    video.write_videofile("short.mp4", fps=24, codec="libx264", audio_codec="aac")

def subir(youtube, archivo, titulo, desc):
    body = {
        "snippet": {
            "title": (titulo[:95] + " #Shorts"),
            "description": desc + "\n\n@Slowning",
            "tags": ["gaming", "easteregg", "slowning", "shorts"],
            "categoryId": "20"
        },
        "status": {"privacyStatus": "public", "madeForKids": False}
    }
    media = MediaFileUpload(archivo, mimetype="video/mp4", resumable=True)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    req.execute()
    print("Subido:", titulo)

async def main():
    idioma = random.choice(["espanol", "espanol", "ingles"])
    print(f"Idioma elegido: {idioma}")
    data = generar_tema(idioma)
    print(f"Titulo: {data['titulo']}")
    await crear_voz(data["guion"], idioma)
    crear_video(data["titulo"])
    yt = get_youtube()
    subir(yt, "short.mp4", data["titulo"], data["guion"][:200])

asyncio.run(main())
