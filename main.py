import os
import uuid
import base64
import time
from dotenv import load_dotenv
from openai import OpenAI

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

load_dotenv()

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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
Create a premium AI gift portrait inspired by the uploaded child photo.

Use the uploaded child photo as a respectful visual reference for the person's
overall identity, warmth, and natural charm. Show this person as a grown-up
adult thriving in the profession: {job}. This is an imaginative keepsake image,
not a factual prediction.

Most important:
- The person must be the hero of the image, large in frame, bust-up or upper
  body centered, with strong presence and direct emotional impact.
- Make the person look naturally beautified but still believable and connected
  to the reference photo; do not transform them into an unrelated person.
- Create a premium, print-worthy portrait with the quality of an advertising
  visual, movie poster, magazine cover, or professional publicity photo.
- The image should feel like something a parent could frame and give as a
  special present.

Person refinement:
- Elevate facial features, hair, skin, expression, posture, clothing, and body
  proportions with tasteful high-end portrait retouching.
- Use flattering face and body proportions, clean skin, refined hair styling,
  expressive eyes, confident posture, elegant wardrobe, and a bright charismatic
  smile.
- The person should feel successful, aspirational, polished, joyful, and
  inspiring.
- Avoid an ordinary snapshot look. Avoid plain clothing, weak posture, dull
  expression, or a generic face.

Career storytelling:
- Do not communicate the profession with only a single prop.
- Express the profession through a complete visual system: wardrobe, hairstyle,
  posture, facial expression, lighting, environment, colors, and supporting
  details must all belong to the world of {job}.
- The career should be instantly recognizable at first glance.
- Keep the background secondary. It should enhance the person and career, not
  distract from them.

If the job is actor, actress, performer, movie star, stage actor, 俳優, 女優, or similar:
- Do not make a clapperboard the main idea. If a clapperboard appears, make it
  small and natural, never the focus.
- Create the feeling of a lead actor's cinematic movie poster, red carpet photo,
  film festival appearance, premiere screening, stage greeting, or high-end
  publicity portrait.
- Use a luxury suit, elegant dress, refined stage outfit, polished hair, tasteful
  makeup or grooming, and a star-like pose.
- Add cinematic spotlights, press flash, cameras, theater lights, red carpet,
  audience glow, movie-premiere atmosphere, and sophisticated celebrity polish.
- The person should look like a successful young star: charismatic, stylish,
  confident, glamorous, and emotionally engaging.

If the job is doctor, nurse, surgeon, dentist, veterinarian, 医者, 看護師, or medical worker:
- Create a bright premium healthcare advertising portrait.
- Use a clean white coat or appropriate medical uniform, stethoscope, refined
  grooming, warm trustworthy expression, and gentle confident posture.
- Include a bright hospital, clinic, consultation room, soft daylight, and
  subtle medical equipment.

If the job is astronaut, space pilot, space engineer, 宇宙飛行士, or space-related:
- Create an epic cinematic space-career poster.
- Use an impressive astronaut suit or mission-ready space uniform, heroic pose,
  spacecraft, moon surface, Earth, space station, mission lights, and vast scale.
- The person should look brave, polished, and inspiring.

If the job is pastry chef, patissier, baker, パティシエ, or similar:
- Use an elegant pastry chef uniform, refined patisserie setting, beautiful
  cakes or desserts, warm premium lighting, and a skilled craftsperson mood.

If the job is soccer player, footballer, サッカー選手, or athlete:
- Use a professional uniform, stadium lights, athletic confident posture,
  energetic body language, victory atmosphere, and premium sports poster style.

For any other profession:
- Choose sophisticated career-specific clothing, environment, lighting, pose,
  and supporting details that make the profession clear and aspirational.

Visual style:
- Premium gift portrait, cinematic poster quality, magazine cover quality,
  professional career portrait, luxury theme park event magic, premium keepsake.
- Use refined blue, gold, orange, green, and red accents. Avoid overly pink or
  cheap childish styling.
- Natural photorealism, high-end lighting, sharp focus, polished composition,
  beautiful color grading, elegant depth of field, print-ready finish.

Avoid:
- No text, captions, logos, watermarks, UI elements, or readable signs.
- No background-only spectacle with an ordinary-looking person.
- No plain clothes unless the profession specifically requires them.
- No random unrelated props.
- No clapperboard-only actor image.
- No scary, cynical, disrespectful, or adult-themed content.
"""

        with open(upload_path, "rb") as image_file:
            result = client.images.edit(
                model="gpt-image-1",
                image=image_file,
                prompt=prompt,
                size="1024x1024",
                n=1,
            )

        image_base64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

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
