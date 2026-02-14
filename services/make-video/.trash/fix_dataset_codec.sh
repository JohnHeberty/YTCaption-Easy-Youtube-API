#!/bin/bash
# Fix Dataset: Convert all AV1 videos to H.264

set -e

VALIDATION_DIR="storage/validation"
OK_DIR="$VALIDATION_DIR/sample_OK"
NOT_OK_DIR="$VALIDATION_DIR/sample_NOT_OK"
H264_DIR="$VALIDATION_DIR/h264_converted"

echo "════════════════════════════════════════════════════════════"
echo "🔧 FIX DATASET: Convert AV1 → H.264"
echo "════════════════════════════════════════════════════════════"
echo ""

# Function to check codec
check_codec() {
    local file="$1"
    ffprobe -v error -select_streams v:0 \
        -show_entries stream=codec_name \
        -of default=noprint_wrappers=1:nokey=1 \
        "$file" 2>/dev/null || echo "unknown"
}

# Function to convert video
convert_video() {
    local input="$1"
    local output="$2"
    
    echo "  🔄 Converting: $(basename "$input")"
    
    if ffmpeg -i "$input" -c:v libx264 -crf 23 -c:a copy -y "$output" \
        -loglevel error -stats 2>&1 | grep -v "^frame="; then
        echo "  ✅ Success: $(basename "$output")"
        return 0
    else
        echo "  ❌ Failed: $(basename "$input")"
        return 1
    fi
}

# Stats
total_videos=0
av1_videos=0
h264_videos=0
converted_videos=0
failed_videos=0

echo "📊 Step 1: Analyzing dataset..."
echo ""

# Analyze NOT_OK videos
echo "🔍 Checking NOT_OK videos:"
for video in "$NOT_OK_DIR"/*.mp4; do
    if [ !  -f "$video" ]; then
        continue
    fi
    
    ((total_videos++))
    codec=$(check_codec "$video")
    filename=$(basename "$video")
    
    if [ "$codec" == "av1" ]; then
        echo "  ❌ AV1: $filename"
        ((av1_videos++))
    elif [ "$codec" == "h264" ]; then
        echo "  ✅ H.264: $filename"
        ((h264_videos++))
    else
        echo "  ⚠️  Unknown codec ($codec): $filename"
    fi
done

echo ""
echo "🔍 Checking OK videos:"
for video in "$OK_DIR"/*.mp4; do
    if [ ! -f "$video" ]; then
        continue
    fi
    
    ((total_videos++))
    codec=$(check_codec "$video")
    filename=$(basename "$video")
    
    if [ "$codec" == "av1" ]; then
        echo "  ❌ AV1: $filename"
        ((av1_videos++))
    elif [ "$codec" == "h264" ]; then
        echo "  ✅ H.264: $filename"
        ((h264_videos++))
    else
        echo "  ⚠️  Unknown codec ($codec): $filename"
    fi
done

echo ""
echo "────────────────────────────────────────────────────────────"
echo "📊 Analysis Summary:"
echo "   Total videos: $total_videos"
echo "   H.264 (OK): $h264_videos"
echo "   AV1 (needs conversion): $av1_videos"
echo "   Other: $((total_videos - h264_videos - av1_videos))"
echo "────────────────────────────────────────────────────────────"
echo ""

if [ "$av1_videos" -eq 0 ]; then
    echo "✅ All videos are already H.264! No conversion needed."
    exit 0
fi

echo "🔄 Step 2: Converting AV1 videos to H.264..."
echo ""

# Create H.264 directories if needed
mkdir -p "$H264_DIR/OK"
mkdir -p "$H264_DIR/NOT_OK"

# Convert NOT_OK videos
echo "🎬 Converting NOT_OK videos:"
for video in "$NOT_OK_DIR"/*.mp4; do
    if [ ! -f "$video" ]; then
        continue
    fi
    
    codec=$(check_codec "$video")
    filename=$(basename "$video")
    
    if [ "$codec" == "av1" ]; then
        output="$H264_DIR/NOT_OK/${filename%.mp4}_h264.mp4"
        
        if convert_video "$video" "$output"; then
            ((converted_videos++))
        else
            ((failed_videos++))
        fi
    fi
done

echo ""
echo "🎬 Converting OK videos:"
for video in "$OK_DIR"/*.mp4; do
    if [ ! -f "$video" ]; then
        continue
    fi
    
    codec=$(check_codec "$video")
    filename=$(basename "$video")
    
    if [ "$codec" == "av1" ]; then
        output="$H264_DIR/OK/${filename%.mp4}_h264.mp4"
        
        if convert_video "$video" "$output"; then
            ((converted_videos++))
        else
            ((failed_videos++))
        fi
    fi
done

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Conversion Complete!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📊 Results:"
echo "   Converted: $converted_videos"
echo "   Failed: $failed_videos"
echo "   Already H.264: $h264_videos"
echo ""
echo "📁 Converted videos saved to:"
echo "   $H264_DIR/OK/"
echo "   $H264_DIR/NOT_OK/"
echo ""

if [ "$failed_videos" -gt 0 ]; then
    echo "⚠️  Some videos failed to convert. Check ffmpeg errors above."
    exit 1
fi

echo "💡 Next steps:"
echo "   1. Verify converted videos: ls -lh $H264_DIR/*/
"   2. Update calibration to use H.264 directory
"   3. Re-run calibration: make calibrate-start"
echo ""
