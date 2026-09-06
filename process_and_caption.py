def generate_caption(topic, lang="en"):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set!")

    client = genai.Client(api_key=api_key)

    if lang == "zh":
        prompt = f"""
        你是一位在古晋（Kuching, Sarawak）深受大众信任、亲切专业的社区药剂师。
        请为这一部 60 至 90 秒的儿童/家庭健康教育动画短视频写一篇高吸引力、高转化率的 Facebook 贴文文案。
        
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

    # --- PRIMARY MODEL: gemini-3.5-flash-lite ---
    try:
        print("Calling Primary Model: gemini-3.5-flash-lite...")
        res = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
        caption_text = res.text
        print("✅ Caption generated successfully using gemini-3.5-flash-lite.")
    except Exception as err_lite:
        print(f"⚠️ Primary model (gemini-3.5-flash-lite) error: {err_lite}")
        print("Switching to Secondary Model: gemini-3.5-flash...")
        
        # --- SECONDARY FALLBACK: gemini-3.5-flash ---
        try:
            res = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
            )
            caption_text = res.text
            print("✅ Caption generated successfully using secondary model (gemini-3.5-flash).")
        except Exception as err_flash:
            print(f"❌ Both models failed: {err_flash}")
            raise err_flash

    with open("caption.txt", "w", encoding="utf-8") as f:
        f.write(caption_text)
        
def process_video(lang="en"):
    input_video = "input.mp4"
    if not os.path.exists(input_video):
        raise FileNotFoundError("input.mp4 not found!")

    total_dur = get_video_duration(input_video)
    # Cut 3.0 seconds off the end to remove NotebookLM outro bumper
    cut_duration = max(1.0, total_dur - 3.0)
    trimmed_body = "trimmed_body.mp4"

    # --- ADVANCED RETENTION FILTERS ---
    # 1. Overlay avatar at bottom right over watermark
    # 2. Dynamic progress bar at the very top (height: 8px, vibrant cyan color)
    progress_bar_filter = (
        f"drawbox=y=0:x=0:w='iw*(t/{cut_duration})':h=8:color=0x0284C7@1:t=fill"
    )

    if os.path.exists("avatar.png"):
        filter_str = (
            f"[1:v]scale=130:130[logo];"
            f"[0:v][logo]overlay=W-w-25:H-h-160,{progress_bar_filter}"
        )
        cmd_trim = (
            f'ffmpeg -y -ss 0 -to {cut_duration} -i {input_video} -i avatar.png '
            f'-filter_complex "{filter_str}" '
            f'-c:v libx264 -preset fast -crf 20 -c:a aac {trimmed_body}'
        )
    else:
        cmd_trim = (
            f'ffmpeg -y -ss 0 -to {cut_duration} -i {input_video} '
            f'-vf "{progress_bar_filter}" '
            f'-c:v libx264 -preset fast -crf 20 -c:a aac {trimmed_body}'
        )

    subprocess.run(cmd_trim, shell=True, check=True)

    # Stitch Intro + Trimmed Body + Outro
    intro_file = f"intro_{lang}.mp4"
    outro_file = f"outro_{lang}.mp4"

    segments = []
    if os.path.exists(intro_file):
        segments.append(intro_file)
    segments.append(trimmed_body)
    if os.path.exists(outro_file):
        segments.append(outro_file)

    with open("concat_list.txt", "w") as f:
        for s in segments:
            f.write(f"file '{s}'\n")

    stitched_temp = "stitched_temp.mp4"
    cmd_concat = f'ffmpeg -y -f concat -safe 0 -i concat_list.txt -c:v libx264 -preset fast -crf 20 -c:a aac {stitched_temp}'
    subprocess.run(cmd_concat, shell=True, check=True)

    # Mix soft background music ducked underneath narration
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

    print(f"Video rendering finished with retention progress bar for: {lang}")
