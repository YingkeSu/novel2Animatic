#!/usr/bin/env python3

import os
import json
import base64
import httpx
from typing import Optional
from pathlib import Path
from openai import OpenAI

STEPFUN_API_KEY = "IOz7U4ygRrjd83fXPwuiNsQLvnbgJkmcankAKfVEKh43ODRT1oJctdJ3M6OkMEOE"
STEPFUN_BASE_URL = "https://api.stepfun.com/step_plan/v1"

IMAGE_MODEL = "step-image-edit-2"
TTS_MODEL = "stepaudio-2.5-tts"
TTS_VOICE = "cixingnansheng"

OUTPUT_DIR = Path("prototype_output")

CHARACTER_PROFILE = {
    "name": "武松",
    "prompt": "tall muscular Chinese warrior, age 28, square jaw, thick eyebrows, determined eyes, traditional topknot hairstyle with black hair, dark blue Hanfu robe with crossed collar, brown leather belt, broad shoulders, powerful build, 1.85m tall, ink wash painting style"
}

WATER_MARGIN_STORY = """
武松在路上行了几日，来到阳谷县地面。当日晌午十分，走得肚中饥渴，望见前面有一个酒店。
武松入到里面坐下，叫道："主人家，快把酒来吃。"只见店主人把三只碗、一双箸、一碟热菜，放在武松面前。
武松拿起碗，一饮而尽，叫道："这酒好生有气力！主人家，有饱肚的买些吃酒。"
店家道："只有熟牛肉。"武松道："好的切二三斤来吃酒。"

武松吃了许多酒，趁着酒兴便走。店家赶出来叫道："客官哪里去？前面景阳冈上有只吊睛白额大虫，晚了出来伤人。"
武松道："我是清河县人氏，这条景阳冈上少也走过了一二十几时不曾见说有大虫。"

武松乘着酒兴，只管走上冈子来。走不到半里多路，见一个败落的山神庙。
行到庙前，看到庙门上贴着一张印信榜文。武松读了，方知端的有虎。

欲待转身再回酒店里来，又怕被店家耻笑。武松正走，看看酒涌上来，便把毡笠儿背在脊梁上。
一步步上那冈子来，回头看这日色时，渐渐地坠下去了。

武松走了一阵，酒力发作，焦热起来。一只手提着哨棒，一只手把胸膛前袒开。
武松自言自说道："那得什么大虫！人自怕了，不敢上山。"

说时迟，那时快。武松见大虫扑来，只一闪，闪在大虫背后。
那大虫背后看人最难，便把前爪搭在地下，把腰胯一掀，掀将起来。
武松只一躲，躲在一边。大虫见掀他不着，吼一声，却似半天里起个霹雳，震得那山冈也动。
把铁棒也似虎尾倒竖起来，只一剪，武松却又闪在一边。

原来那大虫拿人，只是一扑、一掀、一剪。三般捉不着时，气性先自没了一半。
那大虫又剪不着，再吼了一声，一兜兜将回来。

武松见大虫复翻身回来，双手轮起哨棒，尽平生气力，只一棒，正打着那棵树上。
把那条哨棒折做两截，只拿得一半在手里。

那大虫咆哮，性发起来，翻身又只一扑，扑将来。武松又只一跳，却退了十步远。
那大虫恰好把两只前爪搭在武松面前。武松将半截棒丢在一边，两只手就势把大虫顶花皮疙瘩揪住，一按按将下来。
武松把只脚望大虫面门上、眼睛里只顾乱踢。
那大虫咆哮起来，把身底下扒起两堆黄泥，做了一个土坑。
武松把大虫嘴直按下黄泥坑里去。那大虫吃武松奈何得没了些气力。
武松把左手紧紧地揪住顶花皮，偷出右手来，提起铁锤般大小拳头，尽平生之力，只顾打。
打到五七十拳，那大虫眼里、口里、鼻子里、耳朵里都迸出鲜血来。
"""


def generate_reference_image(client: OpenAI) -> Optional[str]:
    print("[Reference] Generating character reference image...")
    
    prompt = f"portrait of {CHARACTER_PROFILE['prompt']}, front view, detailed, looking at viewer"
    
    try:
        response = client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            response_format="b64_json",
            extra_body={
                "cfg_scale": 1.0,
                "steps": 8,
                "seed": 42
            },
            size="1024x1024",
            n=1,
        )
        
        if response.data and len(response.data) > 0:
            b64_data = response.data[0].b64_json
            ref_file = OUTPUT_DIR / "reference_wusong.png"
            with open(ref_file, "wb") as f:
                f.write(base64.b64decode(b64_data))
            print(f"[Reference] Saved: {ref_file}")
            return str(ref_file)
        else:
            print("[Reference] No data returned")
            return None
            
    except Exception as e:
        print(f"[Reference] Error: {e}")
        return None


def split_story_into_scenes(story: str) -> list[dict]:
    scenes = [
        {
            "id": 1,
            "title": "行路饥渴",
            "text": "武松在路上行了几日，来到阳谷县地面。",
            "edit_prompt": "让这个角色走在古代道路上，背着包袱，面带疲惫，走向一个小镇，水墨画风格",
            "narration": "（沉稳）武松在路上行了几日，来到阳谷县地面。",
            "instruction": "语气沉稳，叙述背景"
        },
        {
            "id": 2,
            "title": "望见酒店",
            "text": "当日晌午十分，走得肚中饥渴，望见前面有一个酒店。",
            "edit_prompt": "让这个角色看向远处的酒馆，露出饥饿的表情，阳光明媚，水墨画风格",
            "narration": "（微饥）当日晌午十分，走得肚中饥渴，望见前面有一个酒店。",
            "instruction": "语气略带疲惫和饥饿感"
        },
        {
            "id": 3,
            "title": "入店就坐",
            "text": "武松入到里面坐下，叫道：主人家，快把酒来吃。",
            "edit_prompt": "让这个角色坐在酒馆里的木桌旁，大声喊叫，桌上放着酒坛和碗，温暖的室内光线，水墨画风格",
            "narration": "（豪迈）武松入到里面坐下，大喝一声：主人家，快把酒来吃！",
            "instruction": "语气豪迈，声音洪亮"
        },
        {
            "id": 4,
            "title": "一饮而尽",
            "text": "武松拿起碗，一饮而尽，叫道：这酒好生有气力！",
            "edit_prompt": "让这个角色端起大碗一饮而尽，酒水飞溅，豪迈的饮酒姿势，酒馆背景，水墨画风格",
            "narration": "（痛快）武松拿起碗，一饮而尽，叫道：这酒好生有气力！",
            "instruction": "语气痛快淋漓，豪气冲天"
        },
        {
            "id": 5,
            "title": "店家警告",
            "text": "店家赶出来叫道：客官哪里去？前面景阳冈上有只吊睛白额大虫，晚了出来伤人。",
            "edit_prompt": "一个店家跑出来警告这个角色，指向远处的山，店家表情恐惧，阴沉的氛围，水墨画风格",
            "narration": "（急切）客官哪里去！前面景阳冈上有只吊睛白额大虫，晚了出来伤人！",
            "instruction": "语气急切紧张，充满担忧"
        },
        {
            "id": 6,
            "title": "武松不信",
            "text": "武松道：我是清河县人氏，这条景阳冈上少也走过了一二十几时不曾见说有大虫。",
            "edit_prompt": "让这个角色露出不屑的表情，双臂交叉，自信的微笑，酒馆门口，水墨画风格",
            "narration": "（不屑）哼，我是清河县人氏，这条景阳冈上少也走过了一二十几时，不曾见说有大虫！",
            "instruction": "语气不屑一顾，充满自信"
        },
        {
            "id": 7,
            "title": "乘兴上冈",
            "text": "武松乘着酒兴，只管走上冈子来。",
            "edit_prompt": "让这个角色微醺地走上山路，手里拿着酒葫芦，摇摇晃晃，松树，古代山路，水墨画风格",
            "narration": "（微醺）武松乘着酒兴，只管走上冈子来。",
            "instruction": "语气微醺慵懒，带点醉意"
        },
        {
            "id": 8,
            "title": "山神庙",
            "text": "走不到半里多路，见一个败落的山神庙。",
            "edit_prompt": "一座破败的古代山神庙，长满藤蔓，雾气弥漫，废弃的神龛，水墨画风格",
            "narration": "走不到半里多路，见一个败落的山神庙。",
            "instruction": "语气平静，略带神秘感"
        },
        {
            "id": 9,
            "title": "日色渐坠",
            "text": "一步步上那冈子来，回头看这日色时，渐渐地坠下去了。",
            "edit_prompt": "让这个角色在山路上回头看夕阳，金色的光线，长长的影子，壮丽的日落，水墨画风格",
            "narration": "一步步上那冈子来，回头看这日色时，渐渐地坠下去了。",
            "instruction": "语气舒缓，营造氛围"
        },
        {
            "id": 10,
            "title": "酒力发作",
            "text": "武松走了一阵，酒力发作，焦热起来。一只手提着哨棒，一只手把胸膛前袒开。",
            "edit_prompt": "让这个角色感到酒力发作，解开衣襟，手持木棍，出汗，山林，水墨画风格",
            "narration": "（燥热）武松走了一阵，酒力发作，焦热起来。一只手提着哨棒，一只手把胸膛前袒开。",
            "instruction": "语气燥热，带点醉意和烦躁"
        },
        {
            "id": 11,
            "title": "猛虎扑来",
            "text": "说时迟，那时快。武松见大虫扑来，只一闪，闪在大虫背后。",
            "edit_prompt": "一只巨大的猛虎扑向这个角色，角色闪身躲避，戏剧性的动作姿势，月光下的林间空地，激烈的战斗瞬间，水墨画风格",
            "narration": "（紧张急促）说时迟，那时快！武松见大虫扑来，只一闪，闪在大虫背后！",
            "instruction": "语速极快，紧张刺激，像评书艺人讲述打斗场面"
        },
        {
            "id": 12,
            "title": "虎扑一掀",
            "text": "那大虫背后看人最难，便把前爪搭在地下，把腰胯一掀，掀将起来。武松只一躲，躲在一边。",
            "edit_prompt": "老虎用爪子向这个角色挥击，角色灵巧躲避，动态战斗场景，月光下的森林，水墨画风格",
            "narration": "（急促）那大虫背后看人最难，便把前爪搭在地下，把腰胯一掀，掀将起来！武松只一躲，躲在一边！",
            "instruction": "语速快，紧张激烈"
        },
        {
            "id": 13,
            "title": "虎啸震山",
            "text": "大虫见掀他不着，吼一声，却似半天里起个霹雳，震得那山冈也动。",
            "edit_prompt": "老虎咆哮，可见冲击波，树木摇晃，山峦震动，震撼的咆哮场景，水墨画风格",
            "narration": "（震撼）大虫见掀他不着，吼一声，却似半天里起个霹雳，震得那山冈也动！",
            "instruction": "声音震撼有力，表现老虎的威猛"
        },
        {
            "id": 14,
            "title": "哨棒折断",
            "text": "武松见大虫复翻身回来，双手轮起哨棒，尽平生气力，只一棒，正打着那棵树上。把那条哨棒折做两截。",
            "edit_prompt": "让这个角色挥棍打向老虎但打中了树，木棍断裂成两截，木屑飞溅，戏剧性的动作瞬间，水墨画风格",
            "narration": "（焦急）武松见大虫复翻身回来，双手轮起哨棒，尽平生气力，只一棒，正打着那棵树上！把那条哨棒折做两截！",
            "instruction": "语气焦急，武器断裂的紧张感"
        },
        {
            "id": 15,
            "title": "赤手空拳",
            "text": "武松将半截棒丢在一边，两只手就势把大虫顶花皮疙瘩揪住，一按按将下来。",
            "edit_prompt": "让这个角色赤手空拳抓住老虎的头按在地上，原始的力量，激烈的近身搏斗，水墨画风格",
            "narration": "（勇猛）武松将半截棒丢在一边，两只手就势把大虫顶花皮疙瘩揪住，一按按将下来！",
            "instruction": "语气勇猛无畏，展现英雄气概"
        },
        {
            "id": 16,
            "title": "拳打猛虎",
            "text": "武松把只脚望大虫面门上、眼睛里只顾乱踢。提起铁锤般大小拳头，尽平生之力，只顾打。",
            "edit_prompt": "让这个角色用拳头猛烈击打老虎，血迹飞溅，史诗般的地面搏斗，月光下的森林，英雄时刻，水墨画风格",
            "narration": "（激昂）武松把只脚望大虫面门上、眼睛里只顾乱踢！提起铁锤般大小拳头，尽平生之力，只顾打！",
            "instruction": "语气激昂高亢，充满力量感"
        },
        {
            "id": 17,
            "title": "虎毙命",
            "text": "打到五七十拳，那大虫眼里、口里、鼻子里、耳朵里都迸出鲜血来。",
            "edit_prompt": "一只老虎倒地不起，这个角色胜利地站在旁边，地面上有血迹，月光下的空地，英雄凯旋场景，水墨画风格",
            "narration": "（胜利）打到五七十拳，那大虫眼里、口里、鼻子里、耳朵里都迸出鲜血来！",
            "instruction": "语气胜利凯旋，英雄气概"
        }
    ]
    return scenes


def generate_scene_image(scene: dict, client: OpenAI, ref_image_path: str) -> Optional[str]:
    print(f"  [Image] Scene {scene['id']}: {scene['title']}")
    
    image_file = OUTPUT_DIR / f"scene_{scene['id']}.png"
    
    try:
        with open(ref_image_path, "rb") as f:
            ref_image = f.read()
        
        response = client.images.edit(
            model=IMAGE_MODEL,
            image=ref_image,
            prompt=scene["edit_prompt"],
            response_format="b64_json",
            extra_body={
                "cfg_scale": 1.0,
                "steps": 8,
                "seed": 42 + scene["id"]
            },
            size="1024x1024",
            n=1,
        )
        
        if response.data and len(response.data) > 0:
            b64_data = response.data[0].b64_json
            with open(image_file, "wb") as f:
                f.write(base64.b64decode(b64_data))
            print(f"  [Image] Saved: {image_file}")
            return str(image_file)
        else:
            print(f"  [Image] No data returned")
            return None
            
    except Exception as e:
        print(f"  [Image] Error: {e}")
        return None


def generate_audio(scene: dict, client: OpenAI) -> Optional[str]:
    print(f"  [Audio] Scene {scene['id']}: {scene['title']}")
    
    audio_file = OUTPUT_DIR / f"scene_{scene['id']}.mp3"
    
    try:
        response = client.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=scene["narration"],
            extra_body={
                "volume": 1.2,
                "speed": 1.1,
                "instruction": scene.get("instruction", "语气自然，适中语速")
            }
        )
        
        response.stream_to_file(str(audio_file))
        print(f"  [Audio] Saved: {audio_file}")
        return str(audio_file)
        
    except Exception as e:
        print(f"  [Audio] Error: {e}")
        return None


def create_storybook_html(scenes: list[dict]) -> str:
    scenes_html = ""
    for scene in scenes:
        image_html = ""
        if scene.get("image_file"):
            image_html = f'<img src="{scene["image_file"]}" alt="{scene["title"]}">'
        else:
            image_html = '<div class="placeholder">图片生成失败</div>'
        
        audio_html = ""
        if scene.get("audio_file"):
            audio_html = f'''
                <audio controls>
                    <source src="{scene["audio_file"]}" type="audio/mpeg">
                </audio>
            '''
        
        scenes_html += f'''
        <div class="scene">
            <div class="header">
                <h2>{scene["title"]}</h2>
                <span class="badge">场景 {scene["id"]}</span>
            </div>
            <div class="content">
                <div class="image">{image_html}</div>
                <div class="text">
                    <p>{scene["text"]}</p>
                    {audio_html}
                </div>
            </div>
        </div>
        '''
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>武松打虎 - 手书</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 100vh; padding: 40px 20px; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        h1 {{ text-align: center; color: #e94560; font-size: 3em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }}
        .subtitle {{ text-align: center; color: #8b8b8b; margin-bottom: 40px; }}
        .scene {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 30px; margin-bottom: 30px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        .header h2 {{ color: #e94560; font-size: 1.5em; }}
        .badge {{ background: #e94560; color: white; padding: 5px 15px; border-radius: 20px; font-size: 0.9em; }}
        .content {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        @media (max-width: 768px) {{ .content {{ grid-template-columns: 1fr; }} }}
        .image img {{ width: 100%; border-radius: 12px; }}
        .placeholder {{ background: rgba(255,255,255,0.1); height: 300px; display: flex; align-items: center; justify-content: center; border-radius: 12px; color: #666; }}
        .text p {{ color: #d4d4d4; line-height: 1.8; font-size: 1.1em; margin-bottom: 20px; }}
        audio {{ width: 100%; }}
        .footer {{ text-align: center; color: #555; margin-top: 40px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>武松打虎</h1>
        <p class="subtitle">水浒传 第二十三回 | AI 手书 | 角色一致性版</p>
        {scenes_html}
        <div class="footer">
            <p>图片: StepFun step-image-edit-2 | 音频: stepaudio-2.5-tts | API: Step Plan</p>
            <p>策略：参考图 + 图片编辑（保持角色一致性）</p>
        </div>
    </div>
</body>
</html>'''
    
    html_file = OUTPUT_DIR / "storybook.html"
    html_file.write_text(html, encoding="utf-8")
    return str(html_file)


def run_pipeline():
    print("=" * 60)
    print("PROTOTYPE: 角色一致性版 - 武松打虎")
    print("=" * 60)
    print()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    print("[API 配置]")
    print(f"  Base URL: {STEPFUN_BASE_URL}")
    print(f"  Image Model: {IMAGE_MODEL}")
    print(f"  TTS Model: {TTS_MODEL}")
    print(f"  角色: {CHARACTER_PROFILE['name']}")
    print()
    
    client = OpenAI(
        api_key=STEPFUN_API_KEY,
        base_url=STEPFUN_BASE_URL
    )
    
    ref_image = generate_reference_image(client)
    if not ref_image:
        print("Failed to generate reference image, aborting")
        return
    print()
    
    print("[2/4] Splitting story into scenes...")
    scenes = split_story_into_scenes(WATER_MARGIN_STORY)
    print(f"  Found {len(scenes)} scenes")
    print()
    
    print("[3/4] Generating scene images with character consistency...")
    for scene in scenes:
        image_file = generate_scene_image(scene, client, ref_image)
        scene["image_file"] = image_file
    print()
    
    print("[4/4] Generating audio narration...")
    for scene in scenes:
        audio_file = generate_audio(scene, client)
        scene["audio_file"] = audio_file
    print()
    
    print("[5/5] Creating HTML storybook...")
    html_file = create_storybook_html(scenes)
    print(f"  Storybook: {html_file}")
    print()
    
    scene_data_file = OUTPUT_DIR / "scene_data.json"
    with open(scene_data_file, "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)
    
    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print()
    print("Generated files:")
    for file in sorted(OUTPUT_DIR.iterdir()):
        if file.is_file():
            size = file.stat().st_size
            print(f"  {file.name} ({size:,} bytes)")
    print()
    
    success_count = sum(1 for s in scenes if s.get("image_file") and s.get("audio_file"))
    print(f"Success rate: {success_count}/{len(scenes)} scenes complete")
    
    return scenes


if __name__ == "__main__":
    run_pipeline()
