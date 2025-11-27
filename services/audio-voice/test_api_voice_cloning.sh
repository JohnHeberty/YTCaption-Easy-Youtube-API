#!/bin/bash
# Test high-fidelity voice cloning via API with RVC

echo "================================================================================"
echo "🎤 HIGH-FIDELITY VOICE CLONING TEST WITH RVC - API VERSION"
echo "================================================================================"
echo ""

# Configuration
API_URL="http://localhost:8005"
TEST_AUDIO="tests/Teste.ogg"
OUTPUT_DIR="temp/test_outputs"

# Check if test audio exists
if [ ! -f "$TEST_AUDIO" ]; then
    echo "❌ Test audio not found: $TEST_AUDIO"
    exit 1
fi

echo "✅ Test audio found: $TEST_AUDIO"
ls -lh "$TEST_AUDIO"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check API health
echo "🔍 Checking API health..."
HEALTH=$(curl -s "$API_URL/health" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "✅ API is healthy"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
else
    echo "❌ API is not responding at $API_URL"
    echo "   Make sure the service is running:"
    echo "   docker compose up -d"
    exit 1
fi
echo ""

# Step 1: Upload reference audio and create voice profile
echo "================================================================================"
echo "📤 STEP 1: Creating voice profile from Teste.ogg"
echo "================================================================================"
echo ""

CLONE_RESPONSE=$(curl -s -X POST "$API_URL/voices/clone" \
  -F "audio_file=@$TEST_AUDIO" \
  -F "voice_name=Teste_Voice_HighFidelity" \
  -F "language=pt-BR" \
  -F "description=High-fidelity test voice with RVC enhancement")

echo "Response:"
echo "$CLONE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$CLONE_RESPONSE"
echo ""

# Extract voice_profile_id
VOICE_ID=$(echo "$CLONE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('voice_profile_id', ''))" 2>/dev/null)

if [ -z "$VOICE_ID" ]; then
    echo "❌ Failed to create voice profile"
    exit 1
fi

echo "✅ Voice profile created: $VOICE_ID"
echo ""

# Step 2: Generate dubbing with different quality settings
echo "================================================================================"
echo "🎙️  STEP 2: Testing voice dubbing with HIGH QUALITY settings"
echo "================================================================================"
echo ""

# Test texts
declare -a TEXTS=(
    "Olá, este é um teste de clonagem de voz com alta fidelidade usando XTTS e RVC."
    "A tecnologia de síntese de voz avançou muito nos últimos anos."
    "Agora podemos criar vozes sintéticas que soam extremamente naturais e expressivas."
)

# Quality profiles to test
declare -a QUALITIES=("quality")

TEST_NUM=0

for TEXT in "${TEXTS[@]}"; do
    TEST_NUM=$((TEST_NUM + 1))
    
    echo "────────────────────────────────────────────────────────────────────────────────"
    echo "📝 TEST $TEST_NUM/${#TEXTS[@]}"
    echo "────────────────────────────────────────────────────────────────────────────────"
    echo "Text: $TEXT"
    echo ""
    
    for QUALITY in "${QUALITIES[@]}"; do
        echo "🎚️  Quality Profile: $QUALITY"
        echo "   Generating audio..."
        
        START_TIME=$(date +%s.%N)
        
        # Generate with RVC enabled
        OUTPUT_FILE="$OUTPUT_DIR/test_${TEST_NUM}_${QUALITY}_rvc.json"
        
        # Create job
        JOB_RESPONSE=$(curl -s -X POST "$API_URL/jobs" \
          -H "Content-Type: application/x-www-form-urlencoded" \
          -d "text=$TEXT" \
          -d "source_language=pt-BR" \
          -d "mode=dubbing_with_clone" \
          -d "quality_profile=$QUALITY" \
          -d "voice_id=$VOICE_ID" \
          -d "tts_engine=xtts" \
          -d "enable_rvc=true" \
          -d "rvc_pitch=0" \
          -d "rvc_index_rate=0.75" \
          -d "rvc_filter_radius=3" \
          -d "rvc_rms_mix_rate=0.25" \
          -d "rvc_protect=0.33")
        
        echo "$JOB_RESPONSE" > "$OUTPUT_FILE"
        
        # Get job ID
        JOB_ID=$(echo "$JOB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_id', ''))" 2>/dev/null)
        
        if [ -z "$JOB_ID" ]; then
            echo "   ❌ Failed to create job"
            cat "$OUTPUT_FILE"
            echo ""
            continue
        fi
        
        echo "   Job created: $JOB_ID"
        echo "   Waiting for completion..."
        
        # Poll job status
        MAX_WAIT=60
        WAIT=0
        while [ $WAIT -lt $MAX_WAIT ]; do
            sleep 2
            WAIT=$((WAIT + 2))
            
            STATUS_RESPONSE=$(curl -s "$API_URL/jobs/$JOB_ID")
            STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)
            
            if [ "$STATUS" == "completed" ]; then
                # Download audio
                AUDIO_OUTPUT="$OUTPUT_DIR/test_${TEST_NUM}_${QUALITY}_rvc.wav"
                curl -s "$API_URL/jobs/$JOB_ID/download" -o "$AUDIO_OUTPUT"
                
                END_TIME=$(date +%s.%N)
                GEN_TIME=$(echo "$END_TIME - $START_TIME" | bc)
                
                if [ -f "$AUDIO_OUTPUT" ]; then
                    FILE_SIZE=$(stat -f%z "$AUDIO_OUTPUT" 2>/dev/null || stat -c%s "$AUDIO_OUTPUT" 2>/dev/null)
                    FILE_SIZE_KB=$(echo "scale=2; $FILE_SIZE / 1024" | bc)
                    
                    # Get audio duration
                    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$AUDIO_OUTPUT" 2>/dev/null)
                    
                    if [ ! -z "$DURATION" ]; then
                        RTF=$(echo "scale=3; $GEN_TIME / $DURATION" | bc)
                        
                        echo "   ✅ Success!"
                        echo "   Duration: ${DURATION}s"
                        echo "   Generation Time: ${GEN_TIME}s"
                        echo "   RTF: ${RTF}x"
                        echo "   Output Size: ${FILE_SIZE_KB} KB"
                        echo "   Saved: $AUDIO_OUTPUT"
                    else
                        echo "   ✅ Audio generated"
                        echo "   Generation Time: ${GEN_TIME}s"
                        echo "   Output Size: ${FILE_SIZE_KB} KB"
                        echo "   Saved: $AUDIO_OUTPUT"
                    fi
                fi
                break
            elif [ "$STATUS" == "failed" ]; then
                ERROR=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error_message', 'Unknown error'))" 2>/dev/null)
                echo "   ❌ Job failed: $ERROR"
                break
            fi
            
            echo -n "."
        done
        
        if [ $WAIT -ge $MAX_WAIT ]; then
            echo ""
            echo "   ⚠️  Timeout waiting for job completion"
        fi
        
        echo ""
    done
done

# Summary
echo "================================================================================"
echo "📊 RESULTS SUMMARY"
echo "================================================================================"
echo ""

TOTAL_FILES=$(find "$OUTPUT_DIR" -name "test_*.wav" -type f 2>/dev/null | wc -l)

echo "✅ Generated Files: $TOTAL_FILES"
echo ""

if [ $TOTAL_FILES -gt 0 ]; then
    echo "📁 Output Directory: $OUTPUT_DIR"
    echo ""
    echo "Generated Files:"
    find "$OUTPUT_DIR" -name "test_*.wav" -type f -exec ls -lh {} \;
    echo ""
    echo "🎧 To play the audio files:"
    echo "   ffplay $OUTPUT_DIR/test_1_quality_rvc.wav"
fi

echo ""
echo "================================================================================"
echo "✅ TEST COMPLETE!"
echo "================================================================================"
