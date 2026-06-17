#!/bin/bash

OUTPUT_DIR="prototype_output_doupo_v2"
VIDEO_DIR="prototype_output_doupo_v2/video"
mkdir -p "$VIDEO_DIR"

echo "Creating video segments..."

for i in $(seq 1 14); do
    IMAGE="$OUTPUT_DIR/scene_${i}.png"
    AUDIO="$OUTPUT_DIR/scene_${i}.mp3"
    SEGMENT="$VIDEO_DIR/segment_${i}.mp4"
    
    if [ -f "$IMAGE" ] && [ -f "$AUDIO" ]; then
        DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$AUDIO")
        echo "  Scene $i: ${DURATION}s"
        
        ffmpeg -y -loop 1 -i "$IMAGE" -i "$AUDIO" \
            -c:v libx264 -tune stillimage -c:a aac -b:a 192k \
            -pix_fmt yuv420p -shortest \
            -vf "scale=1024:1024:force_original_aspect_ratio=decrease,pad=1024:1024:(ow-iw)/2:(oh-ih)/2" \
            "$SEGMENT" 2>/dev/null
    fi
done

CONCAT_FILE="$VIDEO_DIR/concat.txt"
> "$CONCAT_FILE"
for i in $(seq 1 14); do
    echo "file 'segment_${i}.mp4'" >> "$CONCAT_FILE"
done

FINAL_VIDEO="$VIDEO_DIR/斗破苍穹_三年之约_v2.mp4"
ffmpeg -y -f concat -safe 0 -i "$CONCAT_FILE" -c copy "$FINAL_VIDEO" 2>/dev/null

echo ""
echo "Final: $FINAL_VIDEO"
ls -lh "$FINAL_VIDEO"
