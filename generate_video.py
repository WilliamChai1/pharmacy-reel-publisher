import os
import json
import time
import asyncio
import requests
import edge_tts
from google import genai
from google.genai import types
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# --- 1. GEMINI SCRIPT & PROMPT GENERATOR ---
def generate_storyboard(topic: str) -> list:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    
    prompt = f"""
    Create a lively, educational 3D animated video storyboard for children (aged 5-8) and their parents.
    Topic: {topic}
    
    Requirements:
    - Duration: Around 90 to 120 seconds (under 3 minutes).
    - Tone: Friendly, entertaining, and educational.
    - Style: 3D Pixar animation style, vibrant colors, expressive characters, cinematic lighting.
    - Audience retention: Talk to kids about their body's superhero defense, and talk to parents about medicine safety and dosage.
    - Call to Action: Explicitly tell viewers to LIKE this video and FOLLOW the Facebook page for more parenting health tips, and invite parents to bring their kids to our counter for a free weight check, dosing advice, and a Brave Medicine Hero badge. Mention checking the caption to join our WhatsApp community.
    - Format: Output STRICTLY a JSON array of 6 to 8 scene objects. No markdown wraps, no extra text.
    
    JSON Schema:
    [
      {{
        "scene_id": 1,
        "narration": "Voiceover line spoken in clear, friendly English.",
        "image_prompt": "Detailed 3D Pixar animation prompt describing character, action, expression, lighting, cozy pharmacy or home setting, 9:16 portrait ratio."
      }}
    ]
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    return json.loads(response.text)

# --- 2. TEXT-TO-SPEECH (Edge-TTS) ---
async def create_voice(text: str, filename: str, voice: str = "en-US-AnaNeural"):
    # en-US-AnaNeural is a warm, kid-friendly voice
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

# --- 3. DYNAMIC CAMERA ZOOM ---
def dynamic_zoom(clip, duration):
    # Applies a continuous subtle push-in to simulate 3D camera tracking
    return clip.resize(lambda t: 1 + 0.05 * (t / duration)).set_position(('center', 'center'))

# --- 4. PIPELINE COMPILER ---
def build_video():
    topic = os.environ.get("VIDEO_TOPIC", "How to take liquid medicine easily and why kitchen spoons are dangerous")
    print(f"🎬 Generating script for: {topic}")
    
    scenes = generate_storyboard(topic)
    print(f"Generated {len(scenes)} scenes.")
    
    clips = []
    
    for idx, sc in enumerate(scenes):
        print(f"Processing scene {idx + 1}/{len(scenes)}...")
        audio_path = f"voice_{idx}.mp3"
        image_path = f"frame_{idx}.jpg"
        
        # Audio generation
        asyncio.run(create_voice(sc["narration"], audio_path))
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # 3D Pixar visual generation via Pollinations Flux
        prompt_full = f"{sc['image_prompt']}, 3D Pixar animation, Disney render style, octane 3D render, highly detailed, 9:16 portrait vertical ratio"
        encoded_prompt = requests.utils.quote(prompt_full)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&nologo=true&seed={idx + 42}"
        
        res = requests.get(image_url)
        with open(image_path, "wb") as f:
            f.write(res.content)
            
        time.sleep(1) # Polite cooldown
        
        # Assemble scene clip
        img_clip = ImageClip(image_path).set_duration(duration)
        animated_clip = dynamic_zoom(img_clip, duration).set_audio(audio_clip)
        clips.append(animated_clip)
        
    print("Stitching clips and rendering final 9:16 MP4...")
    final_video = concatenate_videoclips(clips, method="compose")
    final_video.write_videofile("pharmacy_education_reel.mp4", fps=24, codec="libx264", audio_codec="aac")
    print("Render complete: pharmacy_education_reel.mp4")

if __name__ == "__main__":
    build_video()
