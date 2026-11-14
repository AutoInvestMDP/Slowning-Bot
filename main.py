import os, random, asyncio, json, requests, time, textwrap
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
    for version in ["v1beta", "v1"]:
        try:
            r = requests.get(f"https://generativelanguage.googleapis.com/{version}/models?key={GEMINI_KEY}", timeout=30)
            print(f"DEBUG ListModels {version} status: {r.status_code}")
            if r.status_code == 200:
                modelos = []
                for m in r.json().get("models", []):
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        nombre = m["name"].replace("models/", "")
                        bajo = nombre.lower()
                        if any(x in bajo for x in ["preview", "image", "tts", "audio", "embedding", "veo", "imagen", "live", "deep-research", "robotics", "aqa", "transcriber"]):
                            continue
                        if "gemini" not in bajo:
                            continue
                        modelos.append(nombre)
                print(f"DEBUG modelos filtrados: {modelos}")
                return version, modelos
        except Exception as e:
            print(f"Error listando {version}: {e}")
    return "v1beta", []

def llamar_gemini(prompt):
    version, modelos = listar_modelos()
    if not modelos:
        modelos = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
    modelos = sorted(modelos, key=lambda x: (0 if "flash" in x and "lite" not in x else 1, x))
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
                    time.sleep(10)
                    continue
                if r.status_code in [404, 400]:
                    break
                print(ultimo_error)
            except Exception as e:
                print(f"Error con {modelo}: {e}")
                time.sleep(5)
    raise Exception("Error Gemini, todos los modelos fallaron: " + ultimo_error)

def get_youtube():
    # Si el token no coincide con el CLIENT_ID/SECRET da unauthorized_client
    print(f"DEBUG YT_CLIENT_ID largo: {len(os.getenv('YT_CLIENT_ID',''))} YT_REFRESH largo: {len(os.getenv('YT_REFRESH_TOKEN',''))}")
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"].strip(),
        client_secret=os.environ["YT_CLIENT_SECRET"].strip(),
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
    from PIL import Image, ImageDraw, ImageFont
    from moviepy.editor import AudioFileClip, ImageClip
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), (15, 0, 30))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 68)
        font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
    except:
        font = ImageFont.load_default()
        font_sub = font
    lineas = textwrap.wrap(titulo, width=22)
    y = H // 2 - len(lineas) * 45
    for linea in lineas:
        bbox = draw.textbbox((0, 0), linea, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y), linea, fill=(255, 255, 255), font=font)
        y += 90
    draw.text((W//2 - 120, y + 60), "@Slowning", fill=(255, 200, 50), font=font_sub)
    img.save("fondo.png")
    audio = AudioFileClip("voz.mp3")
    dur = min(audio.duration, 58)
    clip = ImageClip("fondo.png").set_duration(dur).set_audio(audio)
    clip.write_videofile("short.mp4", fps=24, codec="libx264", audio_codec="aac")

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
    try:
        subir(yt, "short.mp4", data["titulo"], data["guion"][:200])
    except Exception as e:
        print("ERROR SUBIENDO A YOUTUBE: El Refresh Token no coincide con el Client ID/Secret. Regeneralo en OAuth Playground con el mismo Client ID/Secret que tenes en GitHub.")
        raise e

asyncio.run(main())
