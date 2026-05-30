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
Create a premium keepsake portrait inspired by the uploaded child photo.

Use the uploaded child photo as the visual reference for the person's overall
identity, warmth, and natural charm. Show this person as a grown-up adult
joyfully working as a {job}.

Art direction:
- Make the image feel like a beautiful gift for the child and their family.
- Bright, hopeful, respectful, positive, and family-friendly.
- Premium commemorative photo style, suitable for printing or presenting.
- Natural high-quality portrait photography with a gentle touch of fantasy.
- Theme-park, toy-box, and dreamy pastel world atmosphere.
- Sparkling highlights, soft rainbow accents, floating light particles,
  cheerful decorations, and a sense of wonder.
- Create a gorgeous professional background that matches the {job}, making
  the career feel exciting, aspirational, and full of possibility.
- The person should look confident, kind, and proud while working.
- Polished composition, premium lighting, clean details, vivid but soft colors.

Avoid:
- Scary, dark, cynical, disrespectful, or adult-themed elements.
- Text, logos, watermarks, or captions inside the image.
- Anything that suggests a factual prediction or guaranteed outcome.
"""

        result = client.images.edit(
            model="gpt-image-1",
            image=open(upload_path, "rb"),
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
