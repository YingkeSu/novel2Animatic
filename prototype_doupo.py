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

OUTPUT_DIR = Path("prototype_output_doupo")

CHARACTER_PROFILES = {
    "萧炎": {
        "prompt": "young Chinese man, age 18, handsome face, sharp eyes, black hair in ponytail, wearing black robe with flame patterns, confident smirk, lean muscular build, martial arts style"
    },
    "纳兰嫣然": {
        "prompt": "beautiful young Chinese woman, age 20, long flowing black hair, elegant white dress with blue accents, cold proud expression, graceful posture, fairy-like appearance"
    }
}

DOUPO_STORY = """
三年前，云岚宗少宗主纳兰嫣然当众退婚，萧炎立下三年之约。

今日，萧炎终于站在了云岚宗的山门前。

"萧炎，你终于来了。"纳兰嫣然站在高台之上，白衣飘飘，目光冰冷。

萧炎抬起头，嘴角勾起一抹笑意："三年之约，我萧炎从未忘记。"

"当年你不过是个废物，今日又凭什么挑战我？"纳兰嫣然冷声道。

萧炎缓缓拔出背后的玄重尺，黑色的斗气在周身涌动："今日，我便让你知道，什么叫莫欺少年穷！"

话音刚落，萧炎脚下猛然一蹬，整个人如离弦之箭般冲向纳兰嫣然。

纳兰嫣然眼神一凝，玉手轻挥，一道冰蓝色的斗气迎面而来。

萧炎身形一闪，避过攻击，手中玄重尺带着炽热的火焰狠狠劈下。

"焰分噬浪尺！"

轰然一声巨响，两股力量在半空中碰撞，激起漫天尘土。

当尘埃落定，萧炎傲然而立，纳兰嫣然的长剑已被震飞。

"三年前你给我的羞辱，今日我加倍奉还！"萧炎的声音在云岚宗上空回荡。
"""


def generate_character_references(client: OpenAI) -> dict:
    print("[Reference] Generating character reference images...")
    refs = {}
    
    for name, profile in CHARACTER_PROFILES.items():
        print(f"  Generating: {name}")
        prompt = f"portrait of {profile['prompt']}, front view, detailed, looking at viewer, Chinese ink wash painting style"
        
        try:
            response = client.images.generate(
                model=IMAGE_MODEL,
                prompt=prompt,
                response_format="b64_json",
                extra_body={
                    "cfg_scale": 1.0,
                    "steps": 8,
                    "seed": hash(name) % 2147483647
                },
                size="1024x1024",
                n=1,
            )
            
            if response.data and len(response.data) > 0:
                b64_data = response.data[0].b64_json
                ref_file = OUTPUT_DIR / f"ref_{name}.png"
                with open(ref_file, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                refs[name] = str(ref_file)
                print(f"  Saved: {ref_file}")
                
        except Exception as e:
            print(f"  Error generating {name}: {e}")
    
    return refs


def split_story_into_scenes(story: str) -> list[dict]:
    scenes = [
        {
            "id": 1,
            "title": "三年之约",
            "text": "三年前，云岚宗少宗主纳兰嫣然当众退婚，萧炎立下三年之约。",
            "edit_prompt": "一个年轻男子站在山门前，抬头仰望，表情坚毅，穿着黑色火焰纹长袍，水墨画风格",
            "character": "萧炎",
            "narration": "（回忆）三年前，云岚宗少宗主纳兰嫣然当众退婚，萧炎立下三年之约。",
            "instruction": "语气低沉，带有回忆的沉重感"
        },
        {
            "id": 2,
            "title": "云岚宗山门",
            "text": "今日，萧炎终于站在了云岚宗的山门前。",
            "edit_prompt": "让这个角色站在宏伟的古代山门前，气势磅礴，云雾缭绕，水墨画风格",
            "character": "萧炎",
            "narration": "（坚定）今日，萧炎终于站在了云岚宗的山门前。",
            "instruction": "语气坚定有力"
        },
        {
            "id": 3,
            "title": "纳兰嫣然现身",
            "text": "萧炎，你终于来了。纳兰嫣然站在高台之上，白衣飘飘，目光冰冷。",
            "edit_prompt": "一个美丽的白衣女子站在高台上，长发飘飘，表情冰冷高傲，仙气飘飘，水墨画风格",
            "character": "纳兰嫣然",
            "narration": "（冰冷）萧炎，你终于来了。",
            "instruction": "语气冰冷高傲，带有轻蔑"
        },
        {
            "id": 4,
            "title": "萧炎回应",
            "text": "萧炎抬起头，嘴角勾起一抹笑意：三年之约，我萧炎从未忘记。",
            "edit_prompt": "让这个角色抬头微笑，自信的表情，水墨画风格",
            "character": "萧炎",
            "narration": "（自信）三年之约，我萧炎从未忘记。",
            "instruction": "语气自信，带有挑衅"
        },
        {
            "id": 5,
            "title": "纳兰嫣然嘲讽",
            "text": "当年你不过是个废物，今日又凭什么挑战我？纳兰嫣然冷声道。",
            "edit_prompt": "让这个女子露出嘲讽的笑容，眼神轻蔑，水墨画风格",
            "character": "纳兰嫣然",
            "narration": "（嘲讽）当年你不过是个废物，今日又凭什么挑战我？",
            "instruction": "语气嘲讽轻蔑"
        },
        {
            "id": 6,
            "title": "拔出玄重尺",
            "text": "萧炎缓缓拔出背后的玄重尺，黑色的斗气在周身涌动。",
            "edit_prompt": "让这个角色拔出一把巨大的黑色尺子，周围有黑色气息涌动，气势强大，水墨画风格",
            "character": "萧炎",
            "narration": "（霸气）萧炎缓缓拔出背后的玄重尺，黑色的斗气在周身涌动。",
            "instruction": "语气霸气，充满力量感"
        },
        {
            "id": 7,
            "title": "莫欺少年穷",
            "text": "今日，我便让你知道，什么叫莫欺少年穷！",
            "edit_prompt": "让这个角色高喊，表情激昂，手中握着黑色大尺，水墨画风格",
            "character": "萧炎",
            "narration": "（激昂）今日，我便让你知道，什么叫莫欺少年穷！",
            "instruction": "语气激昂高亢，热血沸腾"
        },
        {
            "id": 8,
            "title": "冲锋",
            "text": "话音刚落，萧炎脚下猛然一蹬，整个人如离弦之箭般冲向纳兰嫣然。",
            "edit_prompt": "让这个角色向前冲刺，动作迅猛，残影效果，水墨画风格",
            "character": "萧炎",
            "narration": "（急促）话音刚落，萧炎脚下猛然一蹬，整个人如离弦之箭般冲向纳兰嫣然！",
            "instruction": "语速极快，紧张刺激"
        },
        {
            "id": 9,
            "title": "冰蓝斗气",
            "text": "纳兰嫣然眼神一凝，玉手轻挥，一道冰蓝色的斗气迎面而来。",
            "edit_prompt": "让这个女子挥手释放冰蓝色的能量，表情冷峻，水墨画风格",
            "character": "纳兰嫣然",
            "narration": "（冷峻）纳兰嫣然眼神一凝，玉手轻挥，一道冰蓝色的斗气迎面而来。",
            "instruction": "语气冷峻有力"
        },
        {
            "id": 10,
            "title": "闪避",
            "text": "萧炎身形一闪，避过攻击，手中玄重尺带着炽热的火焰狠狠劈下。",
            "edit_prompt": "让这个角色闪避攻击，同时挥动燃烧着火焰的黑色大尺，水墨画风格",
            "character": "萧炎",
            "narration": "（迅猛）萧炎身形一闪，避过攻击，手中玄重尺带着炽热的火焰狠狠劈下！",
            "instruction": "语气迅猛有力"
        },
        {
            "id": 11,
            "title": "焰分噬浪尺",
            "text": "焰分噬浪尺！",
            "edit_prompt": "让这个角色施展招式，巨大的火焰从尺中爆发，水墨画风格",
            "character": "萧炎",
            "narration": "（爆发）焰分噬浪尺！",
            "instruction": "声音爆发力极强"
        },
        {
            "id": 12,
            "title": "力量碰撞",
            "text": "轰然一声巨响，两股力量在半空中碰撞，激起漫天尘土。",
            "edit_prompt": "两股能量在空中碰撞爆炸，火与冰交织，尘土飞扬，水墨画风格",
            "character": None,
            "narration": "（震撼）轰然一声巨响，两股力量在半空中碰撞，激起漫天尘土！",
            "instruction": "声音震撼有力"
        },
        {
            "id": 13,
            "title": "尘埃落定",
            "text": "当尘埃落定，萧炎傲然而立，纳兰嫣然的长剑已被震飞。",
            "edit_prompt": "让这个角色傲然站立，对面女子的剑被震飞，胜利的姿态，水墨画风格",
            "character": "萧炎",
            "narration": "（胜利）当尘埃落定，萧炎傲然而立，纳兰嫣然的长剑已被震飞。",
            "instruction": "语气胜利凯旋"
        },
        {
            "id": 14,
            "title": "加倍奉还",
            "text": "三年前你给我的羞辱，今日我加倍奉还！",
            "edit_prompt": "让这个角色高声宣告，气势凌人，水墨画风格",
            "character": "萧炎",
            "narration": "（霸气）三年前你给我的羞辱，今日我加倍奉还！",
            "instruction": "语气霸气，充满复仇的快感"
        }
    ]
    return scenes


def generate_scene_image(scene: dict, client: OpenAI, refs: dict) -> Optional[str]:
    print(f"  [Image] Scene {scene['id']}: {scene['title']}")
    
    image_file = OUTPUT_DIR / f"scene_{scene['id']}.png"
    character = scene.get("character")
    
    try:
        if character and character in refs:
            with open(refs[character], "rb") as f:
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
        else:
            response = client.images.generate(
                model=IMAGE_MODEL,
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
        <p class="subtitle">三年之约 | 网文名场面票选第一 | AI 手书</p>
        {scenes_html}
        <div class="footer">
            <p>图片: StepFun step-image-edit-2 | 音频: stepaudio-2.5-tts | API: Step Plan</p>
            <p>角色一致性策略：参考图 + 图片编辑</p>
        </div>
    </div>
</body>
</html>'''
    
    html_file = OUTPUT_DIR / "storybook.html"
    html_file.write_text(html, encoding="utf-8")
    return str(html_file)


def run_pipeline():
    print("=" * 60)
    print("PROTOTYPE: 斗破苍穹 - 三年之约")
    print("=" * 60)
    print()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    print("[API 配置]")
    print(f"  Base URL: {STEPFUN_BASE_URL}")
    print(f"  Image Model: {IMAGE_MODEL}")
    print(f"  TTS Model: {TTS_MODEL}")
    print(f"  角色: {', '.join(CHARACTER_PROFILES.keys())}")
    print()
    
    client = OpenAI(
        api_key=STEPFUN_API_KEY,
        base_url=STEPFUN_BASE_URL
    )
    
    refs = generate_character_references(client)
    print()
    
    print("[2/4] Splitting story into scenes...")
    scenes = split_story_into_scenes(DOUPO_STORY)
    print(f"  Found {len(scenes)} scenes")
    print()
    
    print("[3/4] Generating scene images with character consistency...")
    for scene in scenes:
        image_file = generate_scene_image(scene, client, refs)
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
