import os, random, asyncio, json, requests, time
import edge_tts
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

GEMINI_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
print(f"DEBUG: key encontrada? {'SI' if GEMINI_KEY else 'NO'} largo: {len(GEMINI_KEY)}")
if not GEMINI_KEY:
    print("ERROR: El Secret GEMINI_API_KEY esta vacio en GitHub.")
    raise SystemExit(1)

def listar_modelos():
    # Pregunta a Google que modelos tenes disponibles, no adivina
    for version in ["v1beta", "v1"]:
        try:
            r = requests.get(f"https://generativelanguage.googleapis.com/{version}/models?key={GEMINI_KEY}", timeout=30)
            print(f"DEBUG ListModels {version} status: {r.status_code}")
            if r.status_code == 200:
                modelos = []
                for m in r.json().get("models", []):
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        # m['name'] viene como "models/gemini-xxx"
                        modelos.append(m["name"].replace("models/", ""))
                print(f"DEBUG modelos disponibles: {modelos}")
                return version, modelos
        except Exception as e:
            print(f"Error listando {version}: {e}")
    return "v1beta", []

def llamar_gemini(prompt):
    version, modelos = listar_modelos()
    if not modelos:
        # Si no pudo listar, prueba con los mas nuevos que si existen
        modelos = ["gemini-3.8-flash", "gemini-3-flash-preview", "gemini-2.5-flash"]
    
    # Priorizar flash, que son los mas baratos y menos saturados
    modelos = sorted(modelos, key=lambda x: ("flash" not in x, x))
    print(f"DEBUG voy a probar: {modelos}")

    ultimo_error = ""
    for modelo in modelos:
        for intento in range(2):
            url = f"https://generativelanguage.googleapis.com/{version}/models/{modelo}:generateContent?key={GEMINI_KEY}"
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            try:
                r = requests.post(url, json=data, timeout=120)
                print(f"DEBUG {modelo} intento {intento+1} status: {r.status_code}")
                if r.status_code == 200:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                ultimo_error = r.text[:500]
                if r.status_code in [503, 429]:
                    print(f"{modelo} saturado, espero 10s y pruebo siguiente")
                    time.sleep(10)
                    continue
                if r.status_code == 404:
                    break
                print(ultimo_error)
            except Exception as e:
                print(f"Error con {modelo}: {e}")
                time.sleep(5)
    raise Exception("Error Gemini, todos los modelos fallaron: " + ultimo_error)

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
    resp = llamar_gemini(prompt)
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
