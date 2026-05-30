import os
import uuid
import base64
import time
import io
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageFilter, ImageEnhance

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

load_dotenv()

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LANDSCAPE_SIZE = (1536, 1024)


def make_landscape_image(image_bytes: bytes) -> bytes:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    target_width, target_height = LANDSCAPE_SIZE

    if image.size == LANDSCAPE_SIZE:
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    # Fill the wide canvas with a soft extension of the generated image so the
    # final file is truly landscape even when the image API returns a square.
    background = image.copy()
    bg_scale = max(target_width / background.width, target_height / background.height)
    bg_size = (
        int(background.width * bg_scale),
        int(background.height * bg_scale),
    )
    background = background.resize(bg_size, Image.Resampling.LANCZOS)
    left = (background.width - target_width) // 2
    top = (background.height - target_height) // 2
    background = background.crop((left, top, left + target_width, top + target_height))
    background = background.filter(ImageFilter.GaussianBlur(34))
    background = ImageEnhance.Brightness(background).enhance(0.78)
    background = ImageEnhance.Color(background).enhance(0.92)

    foreground = image.copy()
    max_foreground_width = int(target_width * 0.72)
    max_foreground_height = int(target_height * 0.9)
    fg_scale = min(
        max_foreground_width / foreground.width,
        max_foreground_height / foreground.height,
        1.0,
    )
    fg_size = (
        int(foreground.width * fg_scale),
        int(foreground.height * fg_scale),
    )
    foreground = foreground.resize(fg_size, Image.Resampling.LANCZOS)

    canvas = background
    x = (target_width - foreground.width) // 2
    y = (target_height - foreground.height) // 2
    canvas.paste(foreground, (x, y))

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    job: str = Form(...),
    child_image: UploadFile = File(...)
):
    image_url = None
    error = None

    try:
        original_name = child_image.filename
        child_name = os.path.splitext(original_name)[0]

        upload_path = f"temp_{uuid.uuid4()}_{original_name}"

        with open(upload_path, "wb") as f:
            f.write(await child_image.read())

        prompt = f"""
Create a wholesome premium keepsake portrait inspired by the uploaded child photo.

Use the uploaded child photo as a respectful visual reference for the person's
overall identity, warmth, and natural charm. Show this person as a grown-up
adult working in the profession: {job}. This is an imaginative family-friendly
keepsake image, not a factual prediction.

Most important:
- Create a respectful, positive, career-themed portrait that a family could
  print, frame, and give as a special present.
- Create a horizontal landscape image, like a premium event photo card or movie
  poster, with enough space to show the career-themed background.
- The person should be the clear main subject, shown in a medium upper-body
  composition with a warm smile and confident expression.
- Keep the full head visible with comfortable space above the hair. Do not crop
  the top of the head, face, shoulders, or important career details.
- Keep the result natural, wholesome, and connected to the reference photo.
- Use bright lighting, clean composition, neat styling, and a print-worthy
  premium keepsake finish.

Person presentation:
- Use polished professional portrait lighting and neat styling.
- Keep the facial expression warm, calm, confident, and family-friendly.
- Use appropriate clothing for the profession and a respectful professional
  posture.
- Avoid dramatic appearance changes or unrelated visual changes. Do not make
  the person look unrelated to the reference photo.

Career storytelling:
- Do not communicate the profession with only a single prop.
- Express the profession through appropriate clothing, setting, lighting,
  posture, and supporting details that all belong to the world of {job}.
- The career should be recognizable at first glance without relying on text.
- Keep the background supportive and clean, so the person and profession remain
  easy to understand.
- Use a balanced composition: the person in the foreground, with meaningful
  career-themed background visible around them.

If the job is actor, actress, performer, movie star, stage actor, 俳優, 女優, or similar:
- Do not make a clapperboard the main idea. If a clapperboard appears, make it
  small and natural, never the focus.
- Create a professional actor publicity portrait with a movie festival, red
  carpet, premiere screening, stage greeting, theater, or film set atmosphere.
- Use formal clothing or a refined stage outfit, neat hair, professional
  portrait lighting, spotlights, cameras, and a calm confident expression.
- Keep the tone polished, respectful, and family-friendly.

If the job is doctor, nurse, surgeon, dentist, veterinarian, 医者, 看護師, or medical worker:
- Create a bright, respectful healthcare portrait.
- Use a clean white coat or appropriate medical uniform, stethoscope, neat
  grooming, warm trustworthy expression, and gentle professional posture.
- Include a bright hospital, clinic, consultation room, soft daylight, and
  subtle medical equipment.

If the job is astronaut, space pilot, space engineer, 宇宙飛行士, or space-related:
- Create an inspiring space-career portrait.
- Use an astronaut suit or mission-ready space uniform, spacecraft, moon surface,
  Earth, space station, mission lights, and a hopeful atmosphere.
- Keep the person calm, confident, and professional.

If the job is pastry chef, patissier, baker, パティシエ, or similar:
- Use a clean pastry chef uniform, refined patisserie setting, beautiful cakes
  or desserts, warm lighting, and a skilled craftsperson atmosphere.

If the job is soccer player, footballer, サッカー選手, or athlete:
- Use a professional uniform, stadium setting, bright lights, confident sports
  posture, and a positive team-sport atmosphere.

For any other profession:
- Choose appropriate career-specific clothing, setting, lighting, posture, and
  supporting details that make the profession clear and positive.

Visual style:
- Premium keepsake, polished professional portrait, career-themed portrait,
  family-friendly, respectful, joyful, bright lighting, clean composition,
  print-worthy finish.
- Horizontal 3:2 landscape composition, not a square close-up.
- Use refined blue, gold, orange, green, and red accents. Avoid overly pink or
  childish styling.
- Natural photorealism, clear details, balanced colors, elegant depth of field,
  and a clean professional finish.

Avoid:
- No text, captions, logos, watermarks, UI elements, or readable signs.
- No emphasis on external appearance changes or physical transformation.
- No background-only spectacle with an ordinary or unclear profession.
- No random unrelated props.
- No clapperboard-only actor image.
- No scary, cynical, disrespectful, or adult-themed content.
"""

        with open(upload_path, "rb") as image_file:
            result = client.images.edit(
                model="gpt-image-1",
                image=image_file,
                prompt=prompt,
                size="1536x1024",
                n=1,
            )

        image_base64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)
        image_bytes = make_landscape_image(image_bytes)

        timestamp = int(time.time())
        output_filename = f"{child_name}_{timestamp}.png"

        output_path = os.path.join("static", "outputs", output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(image_bytes)

        image_url = f"/static/outputs/{output_filename}"

    except Exception as e:
        error = str(e)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "image_url": image_url,
            "error": error
        }
    )
