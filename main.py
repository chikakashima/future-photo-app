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
Create an inspiring future portrait based on the uploaded child photo.

The person should be shown as an adult working as a {job}.

Important:
- This is not a prediction of the child's future face.
- Create a respectful, positive, future-oriented image.
- Make it suitable as a family keepsake.
- High quality, photorealistic, professional lighting.
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