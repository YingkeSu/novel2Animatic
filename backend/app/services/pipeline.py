"""Pipeline service - orchestrates the 5-step novel-to-video pipeline."""

import asyncio
import json
import shutil
from pathlib import Path
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.project import Project
from app.models.scene import Scene
from app.models.task import Task
from app.models.asset import Asset
from app.services.stepfun_client import StepFunClient
from app.services.style_engine import get_writing_prompt, get_scene_split_prompt, get_visual_suffix, get_audio_params

STORAGE_DIR = Path(__file__).parent.parent.parent / "storage"


async def cleanup_pipeline_outputs(db: AsyncSession, user_id: int, project_id: int):
    """Remove partial pipeline outputs for a project."""
    await db.execute(delete(Asset).where(Asset.project_id == project_id))
    await db.execute(delete(Scene).where(Scene.project_id == project_id))
    shutil.rmtree(STORAGE_DIR / str(user_id) / str(project_id), ignore_errors=True)


async def generate_reference_asset(db: AsyncSession, client: StepFunClient, project: Project, scenes: list, project_dir: Path):
    """Generate a project-level reference image and persist it as an asset."""
    project_dir.mkdir(parents=True, exist_ok=True)
    reference_path = project_dir / "reference.png"

    selected_scene = next((scene for scene in scenes if getattr(scene, "character", None)), scenes[0] if scenes else None)
    character = getattr(selected_scene, "character", None) if selected_scene else None
    scene_prompt = ""
    if selected_scene is not None:
        scene_prompt = (
            getattr(selected_scene, "edit_prompt", None)
            or getattr(selected_scene, "text", None)
            or getattr(selected_scene, "narration", None)
            or ""
        )
    if not scene_prompt:
        scene_prompt = project.source_text

    prompt_parts = ["为整个项目生成一张统一风格的参考图。"]
    if character:
        prompt_parts.append(f"角色：{character}。")
    if scene_prompt:
        prompt_parts.append(f"场景提示：{scene_prompt}。")
    visual_suffix = get_visual_suffix(project.style_visual)
    if visual_suffix:
        prompt_parts.append(visual_suffix)

    image_data = await asyncio.to_thread(
        client.image_generate,
        prompt="".join(prompt_parts),
        extra_body={"cfg_scale": 1.0, "steps": 8, "seed": 41},
        size="1024x1024",
    )
    reference_path.write_bytes(image_data)

    asset = Asset(
        project_id=project.id,
        scene_id=None,
        type="reference",
        file_path=str(reference_path),
        file_size=len(image_data),
    )
    db.add(asset)
    await db.flush()
    return asset


async def run_pipeline_task(task_id: int):
    """Execute the full pipeline for a task."""
    async with async_session() as db:
        result = await db.execute(
            select(Task).where(Task.id == task_id).options(selectinload(Task.project))
        )
        task = result.scalar_one()
        project = task.project
        project_id = project.id
        user_id = project.user_id

        try:
            client = StepFunClient()

            # Step 1: Split scenes
            task.step = "split_scenes"
            task.progress = 10
            await db.commit()

            scenes_data = await asyncio.to_thread(split_scenes_sync, client, project.source_text, project.style_writing)

            # Save scenes to DB
            for i, sd in enumerate(scenes_data):
                scene = Scene(
                    project_id=project.id,
                    seq=i + 1,
                    title=sd.get("title", f"Scene {i+1}"),
                    text=sd.get("text", ""),
                    shot_type=sd.get("shot_type", "中景"),
                    narration=sd.get("narration", ""),
                    edit_prompt=sd.get("edit_prompt", ""),
                    instruction=sd.get("instruction", ""),
                    character=sd.get("character"),
                )
                db.add(scene)
            await db.commit()

            # Step 2: Generate character reference images
            task.step = "generate_refs"
            task.progress = 25
            await db.commit()

            project_dir = STORAGE_DIR / str(project.user_id) / str(project.id)
            project_dir.mkdir(parents=True, exist_ok=True)

            scenes_result = await db.execute(
                select(Scene).where(Scene.project_id == project.id).order_by(Scene.seq)
            )
            scenes = scenes_result.scalars().all()
            await generate_reference_asset(db, client, project, scenes, project_dir)

            # Step 3: Generate scene images
            task.step = "generate_images"
            task.progress = 40
            await db.commit()

            visual_suffix = get_visual_suffix(project.style_visual)
            for scene in scenes:
                img_data = await asyncio.to_thread(
                    client.image_generate,
                    prompt=scene.edit_prompt + visual_suffix,
                    extra_body={"cfg_scale": 1.0, "steps": 8, "seed": 42 + scene.seq},
                    size="1024x1024",
                )
                img_path = project_dir / f"scene_{scene.seq}.png"
                img_path.write_bytes(img_data)
                db.add(Asset(project_id=project.id, scene_id=scene.id, type="image", file_path=str(img_path), file_size=len(img_data)))
            await db.commit()

            # Step 4: Generate TTS audio
            task.step = "generate_audio"
            task.progress = 65
            await db.commit()

            audio_params = get_audio_params(project.style_audio)
            for scene in scenes:
                audio_data = await asyncio.to_thread(
                    client.tts,
                    text=scene.narration,
                    voice=audio_params["voice"],
                    extra_body={
                        "volume": audio_params["volume"],
                        "speed": audio_params["speed"],
                        "instruction": audio_params["instruction"],
                    },
                )
                audio_path = project_dir / f"scene_{scene.seq}.mp3"
                audio_path.write_bytes(audio_data)
                db.add(Asset(project_id=project.id, scene_id=scene.id, type="audio", file_path=str(audio_path), file_size=len(audio_data)))
            await db.commit()

            # Step 5: Assemble video
            task.step = "assemble_video"
            task.progress = 90
            await db.commit()

            video_path = project_dir / "final.mp4"
            await assemble_video(project_dir, scenes, video_path)
            if video_path.exists():
                db.add(Asset(project_id=project.id, type="video", file_path=str(video_path), file_size=video_path.stat().st_size))

            task.status = "done"
            task.step = "complete"
            task.progress = 100
            project.status = "done"
            await db.commit()

        except Exception as e:
            await db.rollback()
            await cleanup_pipeline_outputs(db, user_id, project_id)
            task.status = "failed"
            task.error_msg = str(e)[:500]
            project.status = "failed"
            await db.commit()


def split_scenes_sync(client: StepFunClient, text: str, style: str) -> list:
    """Use LLM to split text into scenes (synchronous)."""
    default_scene = [{"title": "Scene 1", "text": text, "shot_type": "中景", "narration": text, "edit_prompt": text, "instruction": "语气自然", "character": None}]

    def normalize_string(value, default):
        return value if isinstance(value, str) and value else default

    def normalize_scene(scene, index):
        character = scene.get("character")
        return {
            "title": normalize_string(scene.get("title"), f"Scene {index}"),
            "text": normalize_string(scene.get("text"), text),
            "shot_type": normalize_string(scene.get("shot_type"), "中景"),
            "narration": normalize_string(scene.get("narration"), text),
            "edit_prompt": normalize_string(scene.get("edit_prompt"), text),
            "instruction": normalize_string(scene.get("instruction"), "语气自然"),
            "character": character if isinstance(character, str) and character else None,
        }

    style_prompt = get_scene_split_prompt(style) or get_writing_prompt(style)
    system_msg = style_prompt if style_prompt else "你是一位专业的编剧。"

    messages = [
        {"role": "system", "content": system_msg + """
请将以下文段拆分为 N 个场景，每个场景输出 JSON 格式：
{"scenes": [{"title": "场景标题", "text": "场景原文", "shot_type": "景别", "narration": "旁白文字", "edit_prompt": "图像生成提示词", "instruction": "TTS语气指令", "character": "角色名(可选)"}]}
只输出 JSON，不要其他文字。"""},
        {"role": "user", "content": text},
    ]

    response = client.llm_chat(messages)
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
        else:
            json_str = response.strip()
        data = json.loads(json_str)
        if not isinstance(data, dict):
            return default_scene

        scenes = data.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            return default_scene

        normalized_scenes = [
            normalize_scene(scene, index)
            for index, scene in enumerate(scenes, start=1)
            if isinstance(scene, dict)
        ]
        return normalized_scenes or default_scene
    except (json.JSONDecodeError, IndexError):
        return default_scene


async def assemble_video(project_dir: Path, scenes: list, video_path: Path):
    """Use ffmpeg to assemble images + audio into video."""
    segments = []
    for scene in scenes:
        img = project_dir / f"scene_{scene.seq}.png"
        audio = project_dir / f"scene_{scene.seq}.mp3"
        segment = project_dir / f"segment_{scene.seq}.mp4"

        if img.exists() and audio.exists():
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(audio),
                "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p", "-shortest",
                "-vf", "scale=1024:1024:force_original_aspect_ratio=decrease,pad=1024:1024:(ow-iw)/2:(oh-ih)/2",
                str(segment),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            returncode = await proc.wait()
            if returncode != 0:
                raise RuntimeError(f"ffmpeg failed to generate segment {scene.seq} with exit code {returncode}")
            segments.append(segment)

    if not segments:
        return

    concat_file = project_dir / "concat.txt"
    with open(concat_file, "w") as f:
        for seg in segments:
            f.write(f"file '{seg.name}'\n")

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy", str(video_path),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    returncode = await proc.wait()
    if returncode != 0:
        raise RuntimeError(f"ffmpeg failed to concatenate video with exit code {returncode}")
