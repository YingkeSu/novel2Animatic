#!/usr/bin/env python3

import os
import json
import base64
from typing import Optional
from pathlib import Path
from openai import OpenAI

STEPFUN_API_KEY = "IOz7U4ygRrjd83fXPwuiNsQLvnbgJkmcankAKfVEKh43ODRT1oJctdJ3M6OkMEOE"
STEPFUN_BASE_URL = "https://api.stepfun.com/step_plan/v1"

IMAGE_MODEL = "step-image-edit-2"
TTS_MODEL = "stepaudio-2.5-tts"
TTS_VOICE = "cixingnansheng"

OUTPUT_DIR = Path("prototype_output_doupo_v2")

CHARACTER_PROFILES = {
    "萧炎": {
        "anchor": "黑袍火焰纹马尾辫",
        "prompt": "young Chinese man age 18 handsome face sharp eyes black hair ponytail black robe flame patterns confident smirk lean muscular build"
    },
    "纳兰嫣然": {
        "anchor": "白衣长发仙气飘飘",
        "prompt": "beautiful young Chinese woman age 20 long flowing black hair elegant white dress blue accents cold proud expression graceful posture"
    }
}

SCENES = [
    {
        "id": 1,
        "title": "三年前·退婚",
        "text": "三年前，纳兰嫣然当众退婚，萧炎立下三年之约。",
        "edit_prompt": "一个年轻男子被一个白衣女子当众退婚，男子表情屈辱坚毅，女子表情冰冷高傲，众人围观，水墨画风格",
        "character": None,
        "shot_type": "中景",
        "narration": "（低沉）三年前，纳兰嫣然当众退婚，萧炎立下三年之约。",
        "instruction": "语气低沉压抑，带有屈辱感"
    },
    {
        "id": 2,
        "title": "今日·山门前",
        "text": "今日，萧炎终于站在了云岚宗的山门前。",
        "edit_prompt": "让这个角色站在宏伟的古代山门前，抬头仰望，气势磅礴，云雾缭绕，水墨画风格",
        "character": "萧炎",
        "shot_type": "远景",
        "narration": "（坚定）今日，萧炎终于站在了云岚宗的山门前。",
        "instruction": "语气坚定有力"
    },
    {
        "id": 3,
        "title": "高台之上",
        "text": "纳兰嫣然站在高台之上，白衣飘飘，目光冰冷。",
        "edit_prompt": "让这个女子站在高台上，白衣飘飘，俯视下方，目光冰冷高傲，仙气飘飘，水墨画风格",
        "character": "纳兰嫣然",
        "shot_type": "仰拍",
        "narration": "纳兰嫣然站在高台之上，白衣飘飘，目光冰冷。",
        "instruction": "语气冰冷高傲"
    },
    {
        "id": 4,
        "title": "三年之约",
        "text": "萧炎，你终于来了。三年之约，我萧炎从未忘记。",
        "edit_prompt": "让这个角色抬头直视前方，嘴角微笑，眼神坚定自信，水墨画风格",
        "character": "萧炎",
        "shot_type": "特写",
        "narration": "（自信）三年之约，我萧炎从未忘记。",
        "instruction": "语气自信，带有挑衅"
    },
    {
        "id": 5,
        "title": "废物嘲讽",
        "text": "当年你不过是个废物，今日又凭什么挑战我？",
        "edit_prompt": "让这个女子露出嘲讽的笑容，眼神轻蔑，俯视姿态，水墨画风格",
        "character": "纳兰嫣然",
        "shot_type": "近景",
        "narration": "（嘲讽）当年你不过是个废物，今日又凭什么挑战我？",
        "instruction": "语气嘲讽轻蔑"
    },
    {
        "id": 6,
        "title": "拔尺·斗气涌动",
        "text": "萧炎缓缓拔出背后的玄重尺，黑色的斗气在周身涌动。",
        "edit_prompt": "让这个角色拔出一把巨大的黑色尺子，周围有黑色气息涌动，气势强大，水墨画风格",
        "character": "萧炎",
        "shot_type": "中景",
        "narration": "（霸气）萧炎缓缓拔出背后的玄重尺，黑色的斗气在周身涌动。",
        "instruction": "语气霸气，充满力量感"
    },
    {
        "id": 7,
        "title": "莫欺少年穷",
        "text": "今日，我便让你知道，什么叫莫欺少年穷！",
        "edit_prompt": "让这个角色高喊，表情激昂热血，手中握着燃烧火焰的黑色大尺，水墨画风格",
        "character": "萧炎",
        "shot_type": "近景",
        "narration": "（激昂）今日，我便让你知道，什么叫莫欺少年穷！",
        "instruction": "语气激昂高亢，热血沸腾"
    },
    {
        "id": 8,
        "title": "冲锋",
        "text": "萧炎脚下猛然一蹬，如离弦之箭般冲出。",
        "edit_prompt": "让这个角色向前冲刺，动作迅猛，残影效果，地面碎裂，水墨画风格",
        "character": "萧炎",
        "shot_type": "全景",
        "narration": "（急促）萧炎脚下猛然一蹬，如离弦之箭般冲出！",
        "instruction": "语速极快，紧张刺激"
    },
    {
        "id": 9,
        "title": "冰蓝斗气",
        "text": "纳兰嫣然玉手轻挥，一道冰蓝色的斗气迎面而来。",
        "edit_prompt": "让这个女子挥手释放冰蓝色的能量光芒，表情冷峻，水墨画风格",
        "character": "纳兰嫣然",
        "shot_type": "中景",
        "narration": "（冷峻）纳兰嫣然玉手轻挥，一道冰蓝色的斗气迎面而来。",
        "instruction": "语气冷峻有力"
    },
    {
        "id": 10,
        "title": "闪避反击",
        "text": "萧炎身形一闪，避过攻击，玄重尺带着炽热火焰劈下。",
        "edit_prompt": "让这个角色闪避攻击同时挥动燃烧火焰的黑色大尺，动作迅猛，水墨画风格",
        "character": "萧炎",
        "shot_type": "近景",
        "narration": "（迅猛）萧炎身形一闪，避过攻击，玄重尺带着炽热火焰劈下！",
        "instruction": "语气迅猛有力"
    },
    {
        "id": 11,
        "title": "焰分噬浪尺",
        "text": "焰分噬浪尺！",
        "edit_prompt": "让这个角色施展招式，巨大的火焰从尺中爆发，火浪翻涌，水墨画风格",
        "character": "萧炎",
        "shot_type": "特写",
        "narration": "（爆发）焰分噬浪尺！",
        "instruction": "声音爆发力极强"
    },
    {
        "id": 12,
        "title": "力量碰撞",
        "text": "轰然巨响，两股力量碰撞，激起漫天尘土。",
        "edit_prompt": "火与冰两股能量在空中碰撞爆炸，尘土飞扬，冲击波扩散，水墨画风格",
        "character": None,
        "shot_type": "全景",
        "narration": "（震撼）轰然巨响，两股力量碰撞，激起漫天尘土！",
        "instruction": "声音震撼有力"
    },
    {
        "id": 13,
        "title": "尘埃落定",
        "text": "尘埃落定，萧炎傲然而立，纳兰嫣然的长剑已被震飞。",
        "edit_prompt": "让这个角色傲然站立，烟尘散去，胜利姿态，对面女子的剑被震飞，水墨画风格",
        "character": "萧炎",
        "shot_type": "中景",
        "narration": "（胜利）尘埃落定，萧炎傲然而立，纳兰嫣然的长剑已被震飞。",
        "instruction": "语气胜利凯旋"
    },
    {
        "id": 14,
        "title": "加倍奉还",
        "text": "三年前你给我的羞辱，今日我加倍奉还！",
        "edit_prompt": "让这个角色高声宣告，气势凌人，背景是倒地的女子，水墨画风格",
        "character": "萧炎",
        "shot_type": "近景",
        "narration": "（霸气）三年前你给我的羞辱，今日我加倍奉还！",
        "instruction": "语气霸气，充满复仇的快感"
    }
]


def generate_character_references(client: OpenAI) -> dict:
    print("[1/5] Generating character reference images...")
    refs = {}
    
    for name, profile in CHARACTER_PROFILES.items():
        print(f"  {name}: {profile['anchor']}")
        prompt = f"portrait of {profile['prompt']}, front view, detailed, Chinese ink wash painting style"
        
        try:
            response = client.images.generate(
                model=IMAGE_MODEL,
                prompt=prompt,
                response_format="b64_json",
                extra_body={"cfg_scale": 1.0, "steps": 8, "seed": hash(name) % 2147483647},
                size="1024x1024",
                n=1,
            )
            
            if response.data and len(response.data) > 0:
                b64_data = response.data[0].b64_json
                ref_file = OUTPUT_DIR / f"ref_{name}.png"
                with open(ref_file, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                refs[name] = str(ref_file)
                print(f"    Saved: {ref_file}")
                
        except Exception as e:
            print(f"    Error: {e}")
    
    return refs


def generate_scene_images(client: OpenAI, refs: dict) -> list:
    print(f"\n[2/5] Generating {len(SCENES)} scene images...")
    
    for scene in SCENES:
        print(f"  [{scene['shot_type']}] Scene {scene['id']}: {scene['title']}")
        
        character = scene.get("character")
        image_file = OUTPUT_DIR / f"scene_{scene['id']}.png"
        
        try:
            if character and character in refs:
                with open(refs[character], "rb") as f:
                    ref_image = f.read()
                
                response = client.images.edit(
                    model=IMAGE_MODEL,
                    image=ref_image,
                    prompt=scene["edit_prompt"],
                    response_format="b64_json",
                    extra_body={"cfg_scale": 1.0, "steps": 8, "seed": 42 + scene["id"]},
                    size="1024x1024",
                    n=1,
                )
            else:
                response = client.images.generate(
                    model=IMAGE_MODEL,
                    prompt=scene["edit_prompt"],
                    response_format="b64_json",
                    extra_body={"cfg_scale": 1.0, "steps": 8, "seed": 42 + scene["id"]},
                    size="1024x1024",
                    n=1,
                )
            
            if response.data and len(response.data) > 0:
                b64_data = response.data[0].b64_json
                with open(image_file, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                scene["image_file"] = str(image_file)
                print(f"    Saved")
            else:
                scene["image_file"] = None
                print(f"    No data")
                
        except Exception as e:
            scene["image_file"] = None
            print(f"    Error: {e}")
    
    return SCENES


def generate_audio_files(client: OpenAI) -> list:
    print(f"\n[3/5] Generating {len(SCENES)} audio files...")
    
    for scene in SCENES:
        print(f"  Scene {scene['id']}: {scene['title']}")
        audio_file = OUTPUT_DIR / f"scene_{scene['id']}.mp3"
        
        try:
            response = client.audio.speech.create(
                model=TTS_MODEL,
                voice=TTS_VOICE,
                input=scene["narration"],
                extra_body={
                    "volume": 1.2,
                    "speed": 1.1,
                    "instruction": scene.get("instruction", "语气自然")
                }
            )
            
            response.stream_to_file(str(audio_file))
            scene["audio_file"] = str(audio_file)
            print(f"    Saved")
            
        except Exception as e:
            scene["audio_file"] = None
            print(f"    Error: {e}")
    
    return SCENES


def create_storybook_html() -> str:
    print("\n[4/5] Creating HTML storybook...")
    
    scenes_html = ""
    for scene in SCENES:
        image_html = f'<img src="{scene["image_file"]}" alt="{scene["title"]}">' if scene.get("image_file") else '<div class="placeholder">图片生成失败</div>'
        
        audio_html = ""
        if scene.get("audio_file"):
            audio_html = f'<audio controls><source src="{scene["audio_file"]}" type="audio/mpeg"></audio>'
        
        scenes_html += f'''
        <div class="scene">
            <div class="header">
                <h2>{scene["title"]}</h2>
                <span class="badge">{scene["shot_type"]}</span>
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
    <title>斗破苍穹 - 三年之约</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: serif; background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%); min-height: 100vh; padding: 40px 20px; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        h1 {{ text-align: center; color: #ff6b6b; font-size: 3em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }}
        .subtitle {{ text-align: center; color: #8b8b8b; margin-bottom: 40px; }}
        .scene {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 30px; margin-bottom: 30px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        .header h2 {{ color: #ff6b6b; font-size: 1.5em; }}
        .badge {{ background: #ff6b6b; color: white; padding: 5px 15px; border-radius: 20px; font-size: 0.9em; }}
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
        <h1>斗破苍穹</h1>
        <p class="subtitle">三年之约 | 网文名场面票选第一 | AI 手书 v2</p>
        {scenes_html}
        <div class="footer">
            <p>图片: step-image-edit-2 | 音频: stepaudio-2.5-tts | API: Step Plan</p>
            <p>手书规范：景别交替 + 情绪卡点 + 角色锚定</p>
        </div>
    </div>
</body>
</html>'''
    
    html_file = OUTPUT_DIR / "storybook.html"
    html_file.write_text(html, encoding="utf-8")
    return str(html_file)


def run_pipeline():
    print("=" * 60)
    print("斗破苍穹 - 三年之约 (手书规范版)")
    print("=" * 60)
    print()
    print("手书规范:")
    print("  - 景别交替: 远景/全景/中景/近景/特写")
    print("  - 前3秒强冲突，每8秒情绪爆点")
    print("  - 角色锚定: 末尾固定描述")
    print("  - 音画同步: 配音驱动画面")
    print()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    client = OpenAI(
        api_key=STEPFUN_API_KEY,
        base_url=STEPFUN_BASE_URL
    )
    
    refs = generate_character_references(client)
    
    generate_scene_images(client, refs)
    
    generate_audio_files(client)
    
    create_storybook_html()
    
    scene_data_file = OUTPUT_DIR / "scene_data.json"
    with open(scene_data_file, "w", encoding="utf-8") as f:
        json.dump(SCENES, f, ensure_ascii=False, indent=2)
    
    print(f"\n[5/5] Pipeline complete!")
    print()
    print("Generated files:")
    for file in sorted(OUTPUT_DIR.iterdir()):
        if file.is_file():
            size = file.stat().st_size
            print(f"  {file.name} ({size:,} bytes)")
    
    success_count = sum(1 for s in SCENES if s.get("image_file") and s.get("audio_file"))
    print(f"\nSuccess: {success_count}/{len(SCENES)} scenes")
    
    return SCENES


if __name__ == "__main__":
    run_pipeline()
