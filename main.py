import os, asyncio, json, requests, time, textwrap, math, random
import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
try:
    from moviepy.editor import AudioFileClip, VideoClip, VideoFileClip, CompositeVideoClip, concatenate_videoclips, ImageClip
except ImportError:
    from moviepy import AudioFileClip, VideoClip, VideoFileClip, CompositeVideoClip, concatenate_videoclips, ImageClip

GEMINI_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
PIXABAY_KEY = (os.getenv("PIXABAY_API_KEY") or "").strip()

def get_font(size, bold=True):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try: return ImageFont.truetype(p, size)
    except: return ImageFont.load_default()

def llamar_gemini(prompt):
    modelos = ["gemini-3.8-flash", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    for modelo in modelos:
        for version in ["v1beta", "v1"]:
            url = f"https://generativelanguage.googleapis.com/{version}/models/{modelo}:generateContent?key={GEMINI_KEY}"
            try:
                r = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}]}, timeout=120)
                print(f"DEBUG {modelo} {version} status: {r.status_code}")
                if r.status_code == 200:
                    txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return txt.replace("```json","").replace("```","").strip()
                if r.status_code in [404, 400]: break
            except Exception as e: print(f"Error {modelo}: {e}")
    raise Exception("Error Gemini")

# ===== PERSONAJE =====
def generar_personaje():
    if os.path.exists("personaje.png"):
        return "personaje.png"
    print("Generando personaje Slowning...")
    prompt = "3D cartoon gamer character, young man with headphones, purple hoodie, smiling, confident, Pixar style, upper body, looking at camera, solid dark purple background, high quality"
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=512&height=512&model=flux&seed=12345&nologo=true"
    try:
        data = requests.get(url, timeout=120).content
        open("personaje.png","wb").write(data)
        return "personaje.png"
    except Exception as e:
        print("No se pudo generar personaje:", e)
        return None

def generar_shorts():
    prompt = """Dame 3 temas VIRALES de gaming de hoy, diferentes entre si.
Devolveme SOLO JSON:
{"shorts": [{"titulo":"...", "guion":"...", "escenas":[{"texto":"...", "busqueda":"..."}, {"texto":"...", "busqueda":"..."}, {"texto":"...", "busqueda":"..."}]}]}
- guion: 45-55 seg, estilo Slowning, gancho fuerte, en espanol
- Dividilo en 3 escenas. Cada escena tiene su texto y su busqueda en INGLES para buscar video real, ej: "minecraft gameplay", "gta car city", "fortnite gameplay".
- La busqueda TIENE que ser exactamente lo que se dice en ese texto. Si el texto habla de Minecraft, la busqueda es Minecraft. Si habla de un auto, la busqueda es auto.
- titulo corto clickbait pero real."""
    return json.loads(llamar_gemini(prompt))["shorts"][:3]

def generar_largos():
    prompt = """Dame 2 videos largos de YouTube de gaming (4 a 6 minutos), muy virales.
Devolveme SOLO JSON:
{"videos": [{"titulo":"...", "guion":"...", "escenas":[{"texto":"...", "busqueda":"..."}, {"texto":"...", "busqueda":"..."}, {"texto":"...", "busqueda":"..."}, {"texto":"...", "busqueda":"..."}]}]}
- guion largo, intro con gancho, 3-4 partes, cierre con CTA
- Cada escena con su busqueda en INGLES coherente con lo que dice.
En espanol."""
    return json.loads(llamar_gemini(prompt))["videos"][:2]

async def crear_voz(texto):
    await edge_tts.Communicate(texto, "es-MX-JorgeNeural").save("voz_temp.mp3")

# ===== FOOTAGE REAL: PIXABAY + OPENVERSE =====
def buscar_clip_pixabay(query, dur_necesaria, es_short):
    # 1. Pixabay VIDEO
    if PIXABAY_KEY:
        try:
            orient = "vertical" if es_short else "horizontal"
            url = f"https://pixabay.com/api/videos/?key={PIXABAY_KEY}&q={requests.utils.quote(query)}&orientation={orient}&per_page=6&safesearch=true"
            r = requests.get(url, timeout=20)
            hits = r.json().get("hits", [])
            print(f"  Pixabay Video '{query}': {len(hits)} videos")
            if hits:
                v = random.choice(hits[:3])
                link = v["videos"].get("medium", {}).get("url") or v["videos"]["small"]["url"]
                path = f"clip_{random.randint(0,99999)}.mp4"
                open(path, "wb").write(requests.get(link, timeout=60).content)
                c = VideoFileClip(path)
                if c.duration < dur_necesaria:
                    veces = int(dur_necesaria / c.duration) + 1
                    c = concatenate_videoclips([c]*veces, method="compose")
                return c.subclip(0, dur_necesaria)
        except Exception as e:
            print("  Error Pixabay video:", e)
    # 2. Pixabay FOTO con zoom
    if PIXABAY_KEY:
        try:
            orient = "vertical" if es_short else "horizontal"
            url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q={requests.utils.quote(query)}&orientation={orient}&per_page=3&image_type=photo&safesearch=true"
            r = requests.get(url, timeout=20)
            hits = r.json().get("hits", [])
            if hits:
                foto_url = hits[0]["largeImageURL"]
                open("fondo_temp.jpg","wb").write(requests.get(foto_url, timeout=30).content)
                return ImageClip("fondo_temp.jpg").set_duration(dur_necesaria)
        except Exception as e:
            print("  Error Pixabay foto:", e)
    # 3. Respaldo SIN KEY: Openverse
    try:
        r = requests.get(f"https://api.openverse.org/v1/images/?q={requests.utils.quote(query)}&page_size=3&license_type=all", timeout=20)
        results = r.json().get("results", [])
        print(f"  Openverse '{query}': {len(results)} imagenes")
        if results:
            foto_url = results[0]["url"]
            open("fondo_temp.jpg","wb").write(requests.get(foto_url, timeout=30).content)
            return ImageClip("fondo_temp.jpg").set_duration(dur_necesaria)
    except Exception as e:
        print("  Error Openverse:", e)
    return None

def crear_video(titulo, guion, escenas, salida, es_short=True):
    W, H = (1080, 1920) if es_short else (1280, 720)
    audio = AudioFileClip("voz_temp.mp3")
    dur_max = 58 if es_short else 360
    dur = min(audio.duration, dur_max)
    audio = audio.subclip(0, dur)
    palabras = guion.split()
    pps = max(2, len(palabras)/max(1,dur))
    f_titulo = get_font(72 if es_short else 64, True)
    f_sub = get_font(44 if es_short else 38, True)
    personaje_path = generar_personaje()

    clips_escenas = []
    if not escenas:
        escenas = [{"texto": guion, "busqueda": "gaming"}]
    dur_escena = dur / len(escenas)
    for esc in escenas:
        c = buscar_clip_pixabay(esc.get("busqueda","gaming"), dur_escena, es_short)
        if c is None:
            c = VideoClip(lambda t: np.zeros((H, W, 3), dtype=np.uint8), duration=dur_escena)
        try: c = c.resize((W, H))
        except: pass
        clips_escenas.append(c)

    base = concatenate_videoclips(clips_escenas, method="compose")
    base = base.subclip(0, dur)

    personaje_img = None
    if personaje_path and os.path.exists(personaje_path):
        try:
            personaje_img = Image.open(personaje_path).convert("RGBA")
            size = 320 if es_short else 260
            personaje_img = personaje_img.resize((size, size))
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0,0,size,size), fill=255)
            personaje_img.putalpha(mask)
        except: personaje_img = None

    def make_overlay(t):
        img = Image.new("RGBA", (W, H), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        if personaje_img:
            rebote = int(8 * abs(math.sin(t*6)))
            pos_x = W - personaje_img.width - 30
            pos_y = H - personaje_img.height - 180 if es_short else H - personaje_img.height - 150
            img.paste(personaje_img, (pos_x, pos_y - rebote), personaje_img)
            if int(t*2) % 2 == 0:
                draw.ellipse([pos_x-15, pos_y-25-rebote, pos_x+15, pos_y+5-rebote], fill=(0,255,100,255))
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
        draw.rectangle([0, H-20, W*(t/dur), H], fill=(255,0,80,255))
        draw.text((40, H-90), "@Slowning", fill=(255,200,50,255), font=get_font(36, False))
        return np.array(img)

    overlay = VideoClip(make_overlay, duration=dur)
    final = CompositeVideoClip([base, overlay], size=(W,H)).set_audio(audio)
    final.write_videofile(salida, fps=24, codec="libx264", audio_codec="aac", preset="ultrafast")
    final.close(); audio.close(); base.close()

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
        crear_video(s["titulo"], s["guion"], s.get("escenas", []), f"short_{i}.mp4", True)
        subir(yt, f"short_{i}.mp4", s["titulo"], s["guion"], True)
        time.sleep(5)
    print("=== 2 LARGOS ===")
    for i, v in enumerate(generar_largos()):
        print(f"Largo {i+1}/2: {v['titulo']}")
        await crear_voz(v["guion"])
        crear_video(v["titulo"], v["guion"], v.get("escenas", []), f"largo_{i}.mp4", False)
        subir(yt, f"largo_{i}.mp4", v["titulo"], v["guion"], False)
        time.sleep(5)
    print("LISTO: 3 Shorts + 2 Largos subidos")

asyncio.run(main())
