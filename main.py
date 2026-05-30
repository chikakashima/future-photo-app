import os
import uuid
import base64
import time
import io
import mimetypes
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
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini")


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


def get_safe_photo_features(image_bytes: bytes, filename) -> str:
    mime_type = mimetypes.guess_type(filename or "")[0] or "image/png"
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    image_url = f"data:{mime_type};base64,{image_base64}"

    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You describe only safe, non-identifying visual "
                        "atmosphere from an uploaded image. Do not identify the "
                        "person. Do not estimate age. Do not predict the future. "
                        "Do not judge attractiveness. Keep the description "
                        "wholesome, respectful, and concise."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract safe visual atmosphere notes for a "
                                "profession-inspired keepsake portrait. Include "
                                "only: face shape, eye shape, eye size, eyebrow "
                                "style, nose impression, smile impression, "
                                "hairstyle, hair color, general skin tone, and "
                                "overall visual style. "
                                "Avoid identity, face matching, future prediction, "
                                "age estimation, attractiveness evaluation, or "
                                "body-related comments. Return short English "
                                "phrases separated by commas, for example: "
                                "round face, soft almond eyes, medium eyebrows, "
                                "warm smile, straight black hair, fair skin tone, "
                                "gentle and cheerful atmosphere."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                    ],
                },
            ],
            max_tokens=120,
        )

        features = response.choices[0].message.content or ""
        features = " ".join(features.split())
        return features or (
            "soft facial impression, warm smile, neat hairstyle, natural hair "
            "color, general natural skin tone, gentle and positive atmosphere"
        )

    except Exception:
        return (
            "soft facial impression, warm smile, neat hairstyle, natural hair "
            "color, general natural skin tone, gentle and positive atmosphere"
        )


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
    person_type: str = Form(...),
    mood: str = Form(...),
    child_image: UploadFile = File(...)
):
    image_url = None
    error = None

    try:
        original_name = child_image.filename
        child_name = os.path.splitext(original_name or f"photo_{uuid.uuid4()}")[0]

        uploaded_image_bytes = await child_image.read()
        photo_features = get_safe_photo_features(uploaded_image_bytes, original_name)

        person_type_prompts = {
            "女の子向け": (
                "Use a feminine-presenting person for the career-experience "
                "portrait, while keeping the result wholesome, respectful, and "
                "family-friendly."
            ),
            "男の子向け": (
                "Use a masculine-presenting person for the career-experience "
                "portrait, while keeping the result wholesome, respectful, and "
                "family-friendly."
            ),
            "性別指定なし": (
                "Use a neutral presentation without emphasizing gender. Keep the "
                "career image balanced, wholesome, respectful, and family-friendly."
            ),
        }

        mood_prompts = {
            "明るくかわいい": "Use a bright, cheerful, gentle, and friendly mood.",
            "かっこいい": "Use a cool, confident, polished, and energetic mood.",
            "上品": "Use an elegant, refined, calm, and premium mood.",
            "元気いっぱい": "Use a lively, energetic, joyful, and positive mood.",
            "落ち着いた雰囲気": "Use a calm, composed, warm, and peaceful mood.",
        }

        person_type_prompt = person_type_prompts.get(
            person_type,
            person_type_prompts["性別指定なし"]
        )
        mood_prompt = mood_prompts.get(
            mood,
            "Use a warm, respectful, family-friendly mood."
        )

        prompt = f"""
Create a wholesome premium keepsake image for a career theme.

Create a profession-inspired portrait for the career theme: {job}. This is an
imaginative career scene and family-friendly keepsake image, not a factual
prediction. Do not base the image on any uploaded face or personal identity.

Safe visual style notes from the uploaded photo:
- {photo_features}

Use these notes only as gentle visual-style inspiration for facial atmosphere,
hairstyle, expression, and overall mood. Do not copy a face, identify a person,
or imply a timeline.

Person type:
- {person_type_prompt}

Mood:
- {mood_prompt}

Most important:
- Create a respectful, positive, career-themed portrait that a family could
  print, frame, and give as a special present.
- Create a horizontal landscape image, like a premium event photo card or movie
  poster, with enough space to show the career-themed background.
- The person should be the clear main subject, shown in a medium upper-body
  composition with a warm smile and confident expression.
- Keep the full head visible with comfortable space above the hair. Do not crop
  the top of the head, face, shoulders, or important career details.
- Keep the result natural, wholesome, and suitable as a generic career-experience
  keepsake image.
- Use bright lighting, clean composition, neat styling, and a print-worthy
  premium keepsake finish.

Person presentation:
- Use polished professional portrait lighting and neat styling.
- Keep the facial expression warm, calm, confident, and family-friendly.
- Use appropriate clothing for the profession and a respectful professional
  posture.
- Avoid implying that the image is based on a real person's face or identity.
- Treat the result as a safe career-themed costume portrait or
  profession-inspired portrait.

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
- No scary, cynical, disrespectful, or inappropriate content.
"""

        result = client.images.generate(
            model="gpt-image-1",
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
