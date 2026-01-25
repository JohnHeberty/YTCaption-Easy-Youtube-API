#!/bin/bash
# Script de teste completo para o serviço youtube-search
# Testa todos os endpoints e valida operacionalidade

set -e

BASE_URL="http://localhost:8003"
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "  YouTube Search Service - Full Test"
echo "========================================="
echo ""

# Function to test endpoint
test_endpoint() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="${5:-200}"
    
    echo -n "[$TOTAL_TESTS] Testing $name... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$BASE_URL$endpoint")
    elif [ "$method" = "POST" ]; then
        if [ -n "$data" ]; then
            response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL$endpoint$data")
        else
            response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL$endpoint")
        fi
    elif [ "$method" = "DELETE" ]; then
        response=$(curl -s -w "\n%{http_code}" -X DELETE "$BASE_URL$endpoint")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    # Check for expected status or any 2xx status
    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]] || [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASSED${NC} (HTTP $http_code)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC} (HTTP $http_code)"
        echo "   Expected: $expected_status, Got: $http_code"
        echo "   Response: $body" | head -n 3
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Function to wait for job completion
wait_for_job() {
    local job_id="$1"
    local max_wait=60
    local waited=0
    
    echo -n "   Waiting for job completion"
    while [ $waited -lt $max_wait ]; do
        sleep 3
        waited=$((waited + 3))
        
        response=$(curl -s "$BASE_URL/jobs/$job_id")
        status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        
        if [ "$status" = "completed" ]; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        elif [ "$status" = "failed" ]; then
            echo -e " ${RED}✗ Failed${NC}"
            return 1
        fi
        echo -n "."
    done
    
    echo -e " ${YELLOW}⚠ Timeout${NC}"
    return 1
}

echo "=== Basic Endpoints ==="
echo ""

# Test 1: Root endpoint
test_endpoint "Root endpoint" "GET" "/"

# Test 2: Health check
test_endpoint "Health check" "GET" "/health"

# Test 3: Admin stats
test_endpoint "Admin stats" "GET" "/admin/stats"

# Test 4: Admin queue
test_endpoint "Admin queue" "GET" "/admin/queue"

# Test 5: List jobs
test_endpoint "List jobs" "GET" "/jobs?limit=10"

echo ""
echo "=== Search Endpoints with Unlimited max_results ==="
echo ""

# Test 6: Search videos with small limit
test_endpoint "Search videos (max_results=5)" "POST" "/search/videos?query=python%20tutorial&max_results=5"

# Test 7: Search videos with large limit (previously would fail)
test_endpoint "Search videos (max_results=100)" "POST" "/search/videos?query=javascript&max_results=100"

# Test 8: Search videos with very large limit
test_endpoint "Search videos (max_results=500)" "POST" "/search/videos?query=programming&max_results=500"

# Test 9: Video info
video_info_response=$(curl -s -X POST "$BASE_URL/search/video-info?video_id=dQw4w9WgXcQ")
video_info_job_id=$(echo "$video_info_response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
if [ -n "$video_info_job_id" ]; then
    echo -e "[$((TOTAL_TESTS + 1))] Testing Video info... ${GREEN}✓ PASSED${NC} (Job ID: $video_info_job_id)"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "[$((TOTAL_TESTS + 1))] Testing Video info... ${RED}✗ FAILED${NC}"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test 10: Channel info
test_endpoint "Channel info" "POST" "/search/channel-info?channel_id=UCX6OQ3DkcsbYNE6H8uQQuVA&include_videos=false"

# Test 11: Related videos with large limit
related_response=$(curl -s -X POST "$BASE_URL/search/related-videos?video_id=dQw4w9WgXcQ&max_results=200")
related_job_id=$(echo "$related_response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
if [ -n "$related_job_id" ]; then
    echo -e "[$((TOTAL_TESTS + 1))] Testing Related videos (max_results=200)... ${GREEN}✓ PASSED${NC} (Job ID: $related_job_id)"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "[$((TOTAL_TESTS + 1))] Testing Related videos... ${RED}✗ FAILED${NC}"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo ""
echo "=== Job Management Endpoints ==="
echo ""

# Test 12: Get job status
if [ -n "$video_info_job_id" ]; then
    test_endpoint "Get job status" "GET" "/jobs/$video_info_job_id"
    
    # Test 13: Wait for job (with short timeout for testing)
    echo "[$((TOTAL_TESTS + 1))] Testing Wait for job completion..."
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if wait_for_job "$video_info_job_id"; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    
    # Test 14: Download results
    test_endpoint "Download results" "GET" "/jobs/$video_info_job_id/download"
fi

echo ""
echo "=== Edge Cases ==="
echo ""

# Test 15: Invalid max_results (< 1)
echo "[$((TOTAL_TESTS + 1))] Testing Invalid max_results (< 1)..."
TOTAL_TESTS=$((TOTAL_TESTS + 1))
response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/search/videos?query=test&max_results=0")
http_code=$(echo "$response" | tail -n1)
if [[ "$http_code" =~ ^4[0-9][0-9]$ ]]; then
    echo -e "   ${GREEN}✓ PASSED${NC} (Correctly rejected with HTTP $http_code)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "   ${RED}✗ FAILED${NC} (Expected 4xx, got $http_code)"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test 16: Get non-existent job
echo "[$((TOTAL_TESTS + 1))] Testing Get non-existent job..."
TOTAL_TESTS=$((TOTAL_TESTS + 1))
response=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/jobs/nonexistent-job-id")
http_code=$(echo "$response" | tail -n1)
if [ "$http_code" = "404" ]; then
    echo -e "   ${GREEN}✓ PASSED${NC} (Correctly returned 404)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "   ${RED}✗ FAILED${NC} (Expected 404, got $http_code)"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo ""
echo "========================================="
echo "          TEST SUMMARY"
echo "========================================="
echo "Total Tests:  $TOTAL_TESTS"
echo -e "Passed:       ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed:       ${RED}$FAILED_TESTS${NC}"
echo "Success Rate: $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%"
echo "========================================="

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed!${NC}"
    exit 1
fi
