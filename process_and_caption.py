import os
import sys
import subprocess
from google import genai

WHATSAPP_PHONE = "+601110990693"
WHATSAPP_GROUP = "https://chat.whatsapp.com/D1d7scuEzrQ15rwFndmSHr"

def get_video_duration(path):
    cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {path}"
    return float(subprocess.check_output(cmd, shell=True).decode().strip())

def process_video(lang="en"):
    input_video = "input.mp4"
    if not os.path.exists(input_video):
        print("ERROR: input.mp4 not found!")
        sys.exit(1)

    total_dur = get_video_duration(input_video)
    # Cut 3.0s off NotebookLM outro
    cut_duration = max(1.0, total_dur - 3.0)
    trimmed_body = "trimmed_body.mp4"

    # 1. Subtle blue retention progress bar at top (8px)
    progress_bar = f"drawbox=y=0:x=0:w='iw*(t/{cut_duration})':h=8:color=0x0284C7@1:t=fill"

    # 2. Perfect Watermark Placement:
    # "Gemini Notebook" sits at the bottom right.
    # We place your avatar scaled to 220px at: x=W-w-30, y=H-h-25
    if os.path.exists("avatar.png"):
        filter_str = (
            f"[1:v]scale=220:-1[logo];"
            f"[0:v][logo]overlay=W-w-30:H-h-25,{progress_bar}"
        )
        cmd_trim = (
            f'ffmpeg -y -ss 0 -to {cut_duration} -i {input_video} -i avatar.png '
            f'-filter_complex "{filter_str}" '
            f'-r 30 -c:v libx264 -preset fast -crf 20 '
            f'-c:a aac -b:a 192k -ar 44100 -ac 2 -async 1 {trimmed_body}'
        )
    else:
        cmd_trim = (
            f'ffmpeg -y -ss 0 -to {cut_duration} -i {input_video} '
            f'-vf "{progress_bar}" '
            f'-r 30 -c:v libx264 -preset fast -crf 20 '
            f'-c:a aac -b:a 192k -ar 44100 -ac 2 -async 1 {trimmed_body}'
        )

    print("Step 1: Trimming body, positioning avatar over watermark, syncing audio...")
    subprocess.run(cmd_trim, shell=True, check=True)

    # 3. Standardize Intro and Outro (Standardizes 1080x1920, 30fps, 44.1kHz audio)
    intro_file = f"intro_{lang}.mp4"
    outro_file = f"outro_{lang}.mp4"

    segments_to_concat = []

    def standardize_clip(src, dest):
        # Normalizes resolution, framerate, and audio track so concat never loses sync
        cmd = (
            f'ffmpeg -y -i {src} -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 '
            f'-filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1[v];'
            f'[0:a][1:a]amix=inputs=2:duration=first[a]" '
            f'-map "[v]" -map "[a]" -r 30 -c:v libx264 -preset fast -crf 20 -c:a aac -b:a 192k -ar 44100 {dest}'
        )
        subprocess.run(cmd, shell=True, check=True)

    if os.path.exists(intro_file):
        print("Standardizing intro...")
        standardize_clip(intro_file, "norm_intro.mp4")
        segments_to_concat.append("norm_intro.mp4")

    # Standardize body to ensure matching stream properties
    print("Standardizing trimmed body...")
    standardize_clip(trimmed_body, "norm_body.mp4")
    segments_to_concat.append("norm_body.mp4")

    if os.path.exists(outro_file):
        print("Standardizing outro...")
        standardize_clip(outro_file, "norm_outro.mp4")
        segments_to_concat.append("norm_outro.mp4")

    # 4. Concat normalized segments
    with open("concat_list.txt", "w") as f:
        for s in segments_to_concat:
            f.write(f"file '{s}'\n")

    stitched_temp = "stitched_temp.mp4"
    cmd_concat = f'ffmpeg -y -f concat -safe 0 -i concat_list.txt -c:v copy -c:a copy {stitched_temp}'
    subprocess.run(cmd_concat, shell=True, check=True)

    # 5. Mix Background Music (BGM) ducked at 12%
    final_output = "clean_pharmacy_reel.mp4"
    if os.path.exists("bgm.mp3"):
        cmd_bgm = (
            f'ffmpeg -y -i {stitched_temp} -stream_loop -1 -i bgm.mp3 '
            f'-filter_complex "[1:a]volume=0.10[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]" '
            f'-map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k -ar 44100 {final_output}'
        )
        subprocess.run(cmd_bgm, shell=True, check=True)
    else:
        os.rename(stitched_temp, final_output)

    print(f"Video finalized successfully: {final_output}")

def generate_caption(topic, lang="en"):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("GEMINI_API_KEY is empty. Writing fallback.")
        caption_text = f"Health Tip: {topic}\n\nJoin our community: {WHATSAPP_GROUP}\nConsult us on WhatsApp: {WHATSAPP_PHONE}"
        with open("caption.txt", "w", encoding="utf-8") as f:
            f.write(caption_text)
        return

    client = genai.Client(api_key=api_key)

    if lang == "zh":
        prompt = f"""
        你是一位在古晋（Kuching, Sarawak）深受大众信任、亲切专业的社区药剂师。
        请为这一部 60 至 90 秒的儿童/家庭健康教育短视频写一篇高吸引力、高转化率的 Facebook 贴文文案。
        
        短片主题：{topic}
        目标受众：古晋的爸爸妈妈、爷爷奶奶与家庭照顾者。
        语言要求：地道自然的大马中文（简体中文），用词温暖亲切。

        文案架构要求：
        1. 醒目的痛点开头：引起父母或长辈日常给孩子/家人服药时的共鸣。
        2. 2-3 个核心重点（用列点呈现药剂师的专业安全建议）。
        3. 互动号召：点赞本视频、关注我们的 Facebook 专页，获取更多实用的家庭健康知识。
        4. WhatsApp 社区邀请：点击下方链接加入我们的【古晋家庭健康 VIP WhatsApp 社区】：{WHATSAPP_GROUP}
        5. 实体门市福利：邀请家长带孩子来我们的药剂行柜台进行免费的【儿童体重与药量安全核对】，还可让勇敢的孩子免费领取专属的【Brave Medicine Hero 勇敢小英雄贴纸徽章】！
        6. 私信咨询：如有用药疑问，随时 WhatsApp 药剂师：{WHATSAPP_PHONE}
        7. 加上 5-6 个热门标签（如：#古晋健康 #社区药剂师 #砂拉越 #儿童用药安全 #育儿指南）
        """
    else:
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

    caption_text = ""
    # Primary: gemini-3.5-flash-lite
    try:
        print("Calling Primary Model: gemini-3.5-flash-lite...")
        res = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
        caption_text = res.text
        print("Primary model succeeded.")
    except Exception as e1:
        print(f"Primary model failed: {e1}. Switching to secondary: gemini-3.5-flash...")
        try:
            res = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
            )
            caption_text = res.text
            print("Secondary model succeeded.")
        except Exception as e2:
            print(f"Secondary model failed: {e2}")
            caption_text = f"Health Tip: {topic}\n\nJoin our community: {WHATSAPP_GROUP}\nContact pharmacist: {WHATSAPP_PHONE}"

    with open("caption.txt", "w", encoding="utf-8") as f:
        f.write(caption_text)
    print("caption.txt successfully written.")

if __name__ == "__main__":
    topic = os.environ.get("VIDEO_TOPIC", "Liquid medicine safety")
    lang = os.environ.get("VIDEO_LANG", "en")
    process_video(lang)
    generate_caption(topic, lang)
