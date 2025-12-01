#!/bin/bash
# Quick Test Script for WebUI Fixes
# Run this to verify all fixes are working

echo "🔍 Testing WebUI Fixes..."
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check if files were updated
echo "📁 Test 1: Checking file versions..."
if grep -q "v=2.1" /home/YTCaption-Easy-Youtube-API/services/audio-voice/app/webui/index.html; then
    echo -e "${GREEN}✅ Cache buster updated to v2.1${NC}"
else
    echo -e "${RED}❌ Cache buster not found${NC}"
fi

# Test 2: Check if window.app is exposed
echo ""
echo "📦 Test 2: Checking window.app exposure..."
if grep -q "window.app = app;" /home/YTCaption-Easy-Youtube-API/services/audio-voice/app/webui/assets/js/app.js; then
    echo -e "${GREEN}✅ window.app exposed${NC}"
else
    echo -e "${RED}❌ window.app not exposed${NC}"
fi

# Test 3: Check if functions exist
echo ""
echo "🔧 Test 3: Checking function definitions..."
functions=(
    "filterJobsInRealTime"
    "clearJobSearch"
    "filterJobsByStatus"
    "toggleAutoRefresh"
    "duplicateProfileFromEdit"
)

for func in "${functions[@]}"; do
    if grep -q "${func}(" /home/YTCaption-Easy-Youtube-API/services/audio-voice/app/webui/assets/js/app.js; then
        echo -e "${GREEN}✅ $func defined${NC}"
    else
        echo -e "${RED}❌ $func not found${NC}"
    fi
done

# Test 4: Check Docker status
echo ""
echo "🐳 Test 4: Checking Docker containers..."
if docker ps | grep -q "audio-voice-api.*Up"; then
    echo -e "${GREEN}✅ Docker container is running${NC}"
else
    echo -e "${RED}❌ Docker container not running${NC}"
fi

# Test 5: Test RVC stats endpoint
echo ""
echo "🌐 Test 5: Testing RVC Stats endpoint..."
response=$(curl -s http://localhost:8005/rvc-models/stats)
if echo "$response" | grep -q "total_models"; then
    echo -e "${GREEN}✅ RVC Stats endpoint working${NC}"
    echo "   Response: $response"
else
    echo -e "${YELLOW}⚠️  RVC Stats returned: $response${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${YELLOW}📋 NEXT STEPS:${NC}"
echo ""
echo "1. Open browser and press: ${GREEN}Ctrl + Shift + R${NC} (hard reload)"
echo "2. Open Console (F12) and run: ${GREEN}debugApp()${NC}"
echo "3. Navigate to 'Jobs & Downloads' and test filters"
echo "4. Open 'Quality Profiles', edit one, and test 'Duplicate' button"
echo ""
echo "If still seeing errors, clear browser cache completely:"
echo "  Chrome: Settings > Privacy > Clear browsing data > Cached images"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
