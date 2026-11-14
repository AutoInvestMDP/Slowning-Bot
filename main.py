import os, random, asyncio, json, requests, time, textwrap, math
import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from moviepy.editor import AudioFileClip, VideoClip

GEMINI_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()

def get_font(size, bold=True):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try: return ImageFont.truetype(p, size)
    except: return ImageFont.load_default()

def llamar_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    r = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}]}, timeout=120)
    if r.status_code != 200:
        print(r.text[:500]); raise Exception("Error Gemini")
    txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return txt.replace("```json","").replace("```","").strip()

def generar_shorts():
    prompt = """Dame 3 temas VIRALES de gaming de hoy, diferentes entre si. Nichos: easter eggs, noticias Ubisoft/Rockstar/Nintendo, curiosidades GTA/Fortnite/Minecraft/Roblox, trucos virales.
Devolveme SOLO JSON:
{"shorts": [{"titulo":"...", "guion":"..."}]}
Cada guion: 45-55 segundos, estilo Slowning, gancho fuerte en los primeros 3 segundos, en espanol. Titulo corto clickbait pero real."""
    return json.loads(llamar_gemini(prompt))["shorts"][:3]

def generar_largos():
    prompt = """Dame 2 ideas de videos largos de YouTube de gaming (4 a 6 minutos), muy virales.
Devolveme SOLO JSON:
{"videos": [{"titulo":"...", "guion":"..."}]}
Guion largo, intro con gancho, 3 partes, cierre con CTA a suscribirse. En espanol."""
    return json.loads(llamar_gemini(prompt))["videos"][:2]

async def crear_voz(texto):
    await edge_tts.Communicate(texto, "es-MX-JorgeNeural").save("voz_temp.mp3")

def crear_video_animado(titulo, guion, salida, es_short=True):
    W, H = (1080, 1920) if es_short else (1280, 720)
    audio = AudioFileClip("voz_temp.mp3")
    dur_max = 58 if es_short else 360
    dur = min(audio.duration, dur_max)
    audio = audio.subclip(0, dur)
    f_titulo = get_font(72 if es_short else 64, True)
    f_sub = get_font(44 if es_short else 38, True)
    f_marca = get_font(36, False)
    palabras = guion.split()
    pps = max(2, len(palabras)/max(1,dur))

    def make_frame(t):
        img = Image.new("RGB", (W,H), (10,0,30))
        draw = ImageDraw.Draw(img, "RGBA")
        for y in range(0,H,20):
            r = int(20+30*(0.5+0.5*math.sin(t*0.8+y*0.005)))
            g = int(20*(0.5+0.5*math.cos(t*0.6+y*0.004)))
            b = int(50+60*(0.5+0.5*math.sin(t*0.5+y*0.003)))
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        for i in range(30):
            x = (i*137 + int(t*60*(1+i%3))) % W
            y = H - ((i*211 + int(t*120*(1+i%2))) % (H+200)) + 100
            rad = 4+(i%5)*3
            draw.ellipse([x-rad,y-rad,x+rad,y+rad], fill=(255,200,50,90))
        if t < 4:
            lineas = textwrap.wrap(titulo, width=20 if es_short else 28)
            y = 180 if es_short else 80
            for linea in lineas:
                tw = draw.textbbox((0,0), linea, font=f_titulo)[2]
                draw.rectangle([(W-tw)//2-20, y-10, (W-tw)//2+tw+20, y+80], fill=(0,0,0,150))
                draw.text(((W-tw)//2, y), linea, fill=(255,255,255), font=f_titulo)
                y += 85
        else:
            idx = int(t*pps)
            chunk = " ".join(palabras[max(0,idx-4):idx+4])
            lineas = textwrap.wrap(chunk, width=22 if es_short else 38)
            y = H-450 if es_short else H-220
            for linea in lineas:
                tw = draw.textbbox((0,0), linea, font=f_sub)[2]
                draw.rectangle([(W-tw)//2-15, y-8, (W-tw)//2+tw+15, y+60], fill=(0,0,0,170))
                draw.text(((W-tw)//2, y), linea, fill=(255,255,0), font=f_sub)
                y += 65
        draw.text((40, H-90), "@Slowning", fill=(255,200,50), font=f_marca)
        draw.rectangle([0, H-20, W*(t/dur), H], fill=(255,0,80))
        return np.array(img)

    clip = VideoClip(make_frame, duration=dur).set_audio(audio)
    clip.write_videofile(salida, fps=24, codec="libx264", audio_codec="aac", preset="ultrafast")
    clip.close(); audio.close()

def get_youtube():
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"].strip(), token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["YT_CLIENT_ID"].strip(), client_secret=os.environ["YT_CLIENT_SECRET"].strip(), scopes=["https://www.googleapis.com/auth/youtube.upload"])
    return build("youtube", "v3", credentials=creds)

def subir(yt, archivo, titulo, desc, es_short):
    body = {"snippet": {"title": (titulo[:90]+" #Shorts") if es_short else titulo[:95], "description": desc[:800]+"\n\n@Slowning", "tags": ["gaming","slowning","shorts" if es_short else "videojuegos","easteregg"], "categoryId": "20"}, "status": {"privacyStatus": "public", "madeForKids": False}}
    yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(archivo, mimetype="video/mp4", resumable=True)).execute()
    print("Subido:", titulo)

async def main():
    yt = get_youtube()
    print("=== 3 SHORTS ===")
    for i, s in enumerate(generar_shorts()):
        print(f"Short {i+1}/3: {s['titulo']}")
        await crear_voz(s["guion"])
        crear_video_animado(s["titulo"], s["guion"], f"short_{i}.mp4", True)
        subir(yt, f"short_{i}.mp4", s["titulo"], s["guion"], True)
        time.sleep(5)
    print("=== 2 VIDEOS LARGOS ===")
    for i, v in enumerate(generar_largos()):
        print(f"Largo {i+1}/2: {v['titulo']}")
        await crear_voz(v["guion"])
        crear_video_animado(v["titulo"], v["guion"], f"largo_{i}.mp4", False)
        subir(yt, f"largo_{i}.mp4", v["titulo"], v["guion"], False)
        time.sleep(5)
    print("LISTO: 3 Shorts + 2 Largos subidos")

asyncio.run(main())
