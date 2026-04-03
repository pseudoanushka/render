from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import base64
import os
from dotenv import load_dotenv
from groq import Groq
from PIL import Image
import io

load_dotenv()

app = FastAPI()

# Groq Client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class ExtractionResponse(BaseModel):
    success: bool
    data: dict
    message: str


# ---------- VALIDATION ----------
def validate_file(ext: str):
    allowed = ["jpg", "jpeg", "png", "webp"]
    if ext.lower() not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG, WEBP images supported (PDF not supported by Groq vision)"
        )


# ---------- IMAGE PROCESSING ----------
def compress_image(file_bytes: bytes) -> bytes:
    try:
        image = Image.open(io.BytesIO(file_bytes))

        image = image.convert("RGB")  # ensure compatibility
        image.thumbnail((1024, 1024))  # resize (VERY IMPORTANT)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=80)

        return buffer.getvalue()

    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")


def encode_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


# ---------- GROQ VISION ----------
async def call_groq_vision(base64_content: str, prompt: str):
    try:
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                # 🔥 FORCE JPEG (stable)
                                "url": f"data:image/jpeg;base64,{base64_content}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.2,
            max_completion_tokens=1500,
            top_p=1
        )

        return {
            "success": True,
            "content": completion.choices[0].message.content
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ---------- RESPONSE PARSER ----------
def parse_llm_response(text: str):
    import json
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except:
        return {"raw": text}


# ---------- API ----------
@app.post("/extract", response_model=ExtractionResponse)
async def extract(file: UploadFile = File(...)):
    try:
        # Read file
        content = await file.read()

        if not content:
            raise HTTPException(status_code=400, detail="Empty file")

        # Validate extension
        ext = file.filename.split(".")[-1]
        validate_file(ext)

        # 🔥 Compress image (fix for invalid image error)
        content = compress_image(content)

        # Encode
        base64_content = encode_to_base64(content)

        # Prompt
        prompt = """
        You are a medical data extraction system.

        Extract:
        - test_name
        - value
        - unit
        - reference_range
        - date

        Return STRICT JSON only.
        No explanation.
        """

        # Call Groq
        result = await call_groq_vision(base64_content, prompt)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        parsed = parse_llm_response(result["content"])

        return ExtractionResponse(
            success=True,
            data=parsed,
            message="Extraction successful"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))