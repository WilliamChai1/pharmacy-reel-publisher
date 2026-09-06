import os
import json
import time
import asyncio
import requests
import edge_tts
from google import genai
from google.genai import types

# Modern MoviePy v2 imports (No moviepy.editor)
from moviepy import (
    ImageClip, 
    AudioFileClip, 
    CompositeAudioClip, 
    concatenate_videoclips
)
import moviepy.video.fx as vfx

# --- 1. GEMINI SCRIPT & PROMPT GENERATOR ---
def generate_storyboard(topic: str) -> list:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing!")
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Create a lively, educational 3D animated video storyboard for children (aged 5-8) and their parents.
    Topic: {topic}
    
    Requirements:
    - Duration: Around 60 to 90 seconds (concise, high-retention).
    - Tone: Friendly, entertaining, and educational.
    - Style: 3D Pixar animation style, vibrant colors, expressive characters, cinematic soft lighting.
    - Script Structure:
      1. Hook parents and kids on a common struggle.
      2. Explain the body's superhero defense system simply for kids.
      3. Give parents the clear, practical safety tip.
      4. Call to Action: Explicitly ask viewers to LIKE this video and FOLLOW our Facebook page for more parenting health tips. Mention visiting our counter for a free weight-to-dose check and their Brave Medicine Hero sticker, and tell them to check the post caption to join our WhatsApp community.
    - Format: Output STRICTLY a JSON array of 5 to 7 scene objects. No markdown wraps, no extra text.
    
    JSON Schema:
    [
      {{
        "scene_id": 1,
        "narration": "Voiceover line spoken in clear, friendly English.",
        "image_prompt": "Detailed 3D Pixar animation prompt describing character, action, expression, lighting, cozy pharmacy or home setting, 9:16 portrait vertical ratio."
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
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

# --- 3. BACKGROUND MUSIC DOWNLOADER ---
def download_bgm(bgm_path="bgm.mp3"):
    # Download a royalty-free playful acoustic track
    bgm_url = "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3?filename=baby-mandala-111166.mp3"
    if not os.path.exists(bgm_path):
        print("Downloading royalty-free background music...")
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(bgm_url, headers=headers)
        with open(bgm_path, "wb") as f:
            f.write(r.content)

# --- 4. PIPELINE COMPILER ---
def build_video():
    topic = os.environ.get("VIDEO_TOPIC", "Why kitchen spoons are dangerous for kids medicine and how to take syrup easily")
    print(f"Generating storyboard for: {topic}")
    
    scenes = generate_storyboard(topic)
    print(f"Generated {len(scenes)} scenes successfully.")
    
    download_bgm("bgm.mp3")
    
    clips = []
    
    for idx, sc in enumerate(scenes):
        print(f"Rendering scene {idx + 1}/{len(scenes)}...")
        audio_path = f"voice_{idx}.mp3"
        image_path = f"frame_{idx}.jpg"
        
        # Audio generation
        asyncio.run(create_voice(sc["narration"], audio_path))
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # 3D Pixar visual generation
        prompt_full = f"{sc['image_prompt']}, 3D Pixar animation, Disney render style, octane 3D render, highly detailed, 9:16 portrait vertical ratio"
        encoded_prompt = requests.utils.quote(prompt_full)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&nologo=true&seed={idx + 101}"
        
        # Download image with retry
        for attempt in range(3):
            try:
                res = requests.get(image_url, timeout=30)
                if res.status_code == 200:
                    with open(image_path, "wb") as f:
                        f.write(res.content)
                    break
            except Exception as e:
                print(f"Image fetch retry {attempt+1}... ({e})")
                time.sleep(2)
        
        time.sleep(1)
        
        # Modern MoviePy v2 Clip construction
        img_clip = ImageClip(image_path).with_duration(duration)
        
        # Gentle dynamic zoom effect
        zoom_clip = img_clip.with_effects([vfx.Resize(lambda t: 1 + 0.04 * (t / duration))])
        
        # Attach audio to clip
        clip_with_voice = zoom_clip.with_audio(audio_clip)
        clips.append(clip_with_voice)
        
    print("Concatenating scenes...")
    concatenated = concatenate_videoclips(clips, method="compose")
    total_duration = concatenated.duration
    
    # Mix soft background music (loops and scaled to 8% volume so voice is dominant)
    try:
        bgm = AudioFileClip("bgm.mp3").with_volume_scaled(0.08)
        # Loop music if video is longer than the music track
        if bgm.duration < total_duration:
            num_loops = int(total_duration // bgm.duration) + 1
            bgm = concatenate_videoclips([bgm] * num_loops)
        bgm = bgm.subclipped(0, total_duration)
        
        final_audio = CompositeAudioClip([concatenated.audio, bgm])
        final_video = concatenated.with_audio(final_audio)
    except Exception as e:
        print(f"BGM mixing skipped due to error: {e}. Exporting with voiceover only.")
        final_video = concatenated

    print("Encoding final 9:16 MP4...")
    final_video.write_videofile(
        "pharmacy_education_reel.mp4", 
        fps=24, 
        codec="libx264", 
        audio_codec="aac"
    )
    print("Video rendered successfully: pharmacy_education_reel.mp4")

if __name__ == "__main__":
    build_video()
