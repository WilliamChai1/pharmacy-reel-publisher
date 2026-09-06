import os
import json
import subprocess
from google import genai
from google.genai import types

WHATSAPP_PHONE = "+601110990693"
WHATSAPP_GROUP = "https://chat.whatsapp.com/D1d7scuEzrQ15rwFndmSHr"

def get_video_duration(path):
    cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {path}"
    return float(subprocess.check_output(cmd, shell=True).decode().strip())

def process_video():
    input_video = "input.mp4"
    if not os.path.exists(input_video):
        raise FileNotFoundError("input.mp4 not found!")

    total_dur = get_video_duration(input_video)
    # Cut 3.0 seconds off the end to remove NotebookLM outro bumper
    cut_duration = max(1.0, total_dur - 3.0)
    trimmed_body = "trimmed_body.mp4"

    # Overlay avatar at bottom right over watermark (9:16 ratio)
    if os.path.exists("avatar.png"):
        cmd_trim = (
            f'ffmpeg -y -ss 0 -to {cut_duration} -i {input_video} -i avatar.png '
            f'-filter_complex "[1:v]scale=130:130[logo];[0:v][logo]overlay=W-w-25:H-h-160" '
            f'-c:v libx264 -preset fast -crf 20 -c:a aac {trimmed_body}'
        )
    else:
        cmd_trim = (
            f'ffmpeg -y -ss 0 -to {cut_duration} -i {input_video} '
            f'-c:v libx264 -preset fast -crf 20 -c:a aac {trimmed_body}'
        )
    subprocess.run(cmd_trim, shell=True, check=True)

    # Stitch Intro + Trimmed Body + Outro
    segments = []
    if os.path.exists("intro.mp4"):
        segments.append("intro.mp4")
    segments.append(trimmed_body)
    if os.path.exists("outro.mp4"):
        segments.append("outro.mp4")

    with open("concat_list.txt", "w") as f:
        for s in segments:
            f.write(f"file '{s}'\n")

    stitched_temp = "stitched_temp.mp4"
    cmd_concat = f'ffmpeg -y -f concat -safe 0 -i concat_list.txt -c:v libx264 -preset fast -crf 20 -c:a aac {stitched_temp}'
    subprocess.run(cmd_concat, shell=True, check=True)

    # Add soft BGM ducked underneath
    final_output = "clean_pharmacy_reel.mp4"
    if os.path.exists("bgm.mp3"):
        cmd_bgm = (
            f'ffmpeg -y -i {stitched_temp} -stream_loop -1 -i bgm.mp3 '
            f'-filter_complex "[1:a]volume=0.12[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]" '
            f'-map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k {final_output}'
        )
        subprocess.run(cmd_bgm, shell=True, check=True)
    else:
        os.rename(stitched_temp, final_output)

    print("Video rendering finished successfully.")

def generate_caption(topic):
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    prompt = f"""
    You are a trusted, friendly community pharmacist in Kuching, Sarawak.
    Write a high-converting, caring Facebook caption for a 60-90 second educational cartoon reel.
    
    Topic: {topic}
    Target Audience: Middle-aged parents and elderly caregivers in Kuching.
    
    Required Structure:
    1. A punchy hook addressing family/child healthcare challenges.
    2. 2-3 concise bullet points with actionable pharmacist advice.
    3. Call to Action: LIKE this video and FOLLOW our Facebook page for more practical health guides.
    4. WhatsApp Community Link: Invite them to join our VIP Parents WhatsApp Community: {WHATSAPP_GROUP}
    5. In-Person Counter Invitation: Bring their child to our pharmacy counter this week for a free weight-to-dose check, safe measuring advice, and an official 'Brave Medicine Hero' sticker badge!
    6. Direct Pharmacist WhatsApp: For personal inquiries, WhatsApp {WHATSAPP_PHONE}
    7. 5 relevant hashtags: #KuchingHealth #CommunityPharmacist #Sarawak #KidsHealth #MedicationSafety
    
    Tone: Professional, warm, localized, and encouraging.
    """

    try:
        res = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )
        caption_text = res.text
    except Exception as e:
        print(f"Gemini 3.5 Flash fallback triggered: {e}")
        res = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
        caption_text = res.text

    # Write output to caption.txt for GitHub release/artifact
    with open("caption.txt", "w", encoding="utf-8") as f:
        f.write(caption_text)
    print("Caption generated successfully.")

if __name__ == "__main__":
    topic = os.environ.get("VIDEO_TOPIC", "Liquid medicine safety and why kitchen spoons fail")
    process_video()
    generate_caption(topic)
