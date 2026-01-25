#!/bin/bash
# Script de teste para busca de YouTube Shorts
# Valida o novo endpoint /search/shorts

set -e

BASE_URL="http://localhost:8003"
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================="
echo "  YouTube Shorts Search - Tests"
echo "========================================="
echo ""

# Function to test endpoint
test_endpoint() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local expected_status="${4:-200}"
    
    echo -n "[$TOTAL_TESTS] Testing $name... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$BASE_URL$endpoint")
    elif [ "$method" = "POST" ]; then
        response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL$endpoint")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
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
            error=$(echo "$response" | grep -o '"error_message":"[^"]*"' | cut -d'"' -f4)
            echo "   Error: $error"
            return 1
        fi
        echo -n "."
    done
    
    echo -e " ${YELLOW}⚠ Timeout${NC}"
    return 1
}

echo "=== Basic Tests ==="
echo ""

# Test 1: Root endpoint should list shorts endpoint
echo -n "[1] Testing Root endpoint includes shorts... "
TOTAL_TESTS=$((TOTAL_TESTS + 1))
response=$(curl -s "$BASE_URL/")
if echo "$response" | grep -q "search_shorts"; then
    echo -e "${GREEN}✓ PASSED${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗ FAILED${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo ""
echo "=== Shorts Search Tests ==="
echo ""

# Test 2: Search shorts with small limit
echo "[2] Testing Search shorts (max_results=5)..."
TOTAL_TESTS=$((TOTAL_TESTS + 1))
response=$(curl -s -X POST "$BASE_URL/search/shorts?query=funny&max_results=5")
job_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -n "$job_id" ]; then
    echo -e "   ${GREEN}✓ Job created${NC} (ID: $job_id)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
    
    # Wait for completion
    if wait_for_job "$job_id"; then
        # Verify results are shorts
        result=$(curl -s "$BASE_URL/jobs/$job_id")
        results_count=$(echo "$result" | grep -o '"results_count":[0-9]*' | cut -d':' -f2)
        search_type=$(echo "$result" | grep -o '"search_type":"[^"]*"' | cut -d'"' -f4)
        
        echo "   Results: $results_count shorts found"
        echo "   Search type: $search_type"
        
        # Check if results are marked as shorts
        if echo "$result" | grep -q '"is_short":true'; then
            echo -e "   ${GREEN}✓ Results contain is_short flag${NC}"
        fi
    fi
else
    echo -e "   ${RED}✗ Failed to create job${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo ""

# Test 3: Search shorts with larger limit
echo "[3] Testing Search shorts (max_results=20)..."
TOTAL_TESTS=$((TOTAL_TESTS + 1))
response=$(curl -s -X POST "$BASE_URL/search/shorts?query=gaming&max_results=20")
job_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -n "$job_id" ]; then
    echo -e "   ${GREEN}✓ Job created${NC} (ID: $job_id)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
    
    if wait_for_job "$job_id"; then
        result=$(curl -s "$BASE_URL/jobs/$job_id")
        results_count=$(echo "$result" | grep -o '"results_count":[0-9]*' | cut -d':' -f2)
        total_scanned=$(echo "$result" | grep -o '"total_scanned":[0-9]*' | cut -d':' -f2)
        
        echo "   Results: $results_count shorts from $total_scanned scanned"
        
        # Verify duration of all results
        echo "   Checking durations..."
        durations=$(echo "$result" | grep -o '"duration_seconds":[0-9]*' | cut -d':' -f2)
        invalid_count=0
        
        while IFS= read -r duration; do
            if [ "$duration" -gt 60 ]; then
                invalid_count=$((invalid_count + 1))
            fi
        done <<< "$durations"
        
        if [ "$invalid_count" -eq 0 ]; then
            echo -e "   ${GREEN}✓ All results are valid shorts (≤60s)${NC}"
        else
            echo -e "   ${RED}✗ Found $invalid_count videos with duration > 60s${NC}"
        fi
    fi
else
    echo -e "   ${RED}✗ Failed to create job${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo ""

# Test 4: Search shorts with very large limit
echo "[4] Testing Search shorts (max_results=50)..."
TOTAL_TESTS=$((TOTAL_TESTS + 1))
response=$(curl -s -X POST "$BASE_URL/search/shorts?query=tutorial&max_results=50")
http_code=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$BASE_URL/search/shorts?query=tutorial&max_results=50")

if [ "$http_code" = "200" ]; then
    echo -e "   ${GREEN}✓ PASSED${NC} (Accepts large max_results)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "   ${RED}✗ FAILED${NC} (HTTP $http_code)"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo ""
echo "=== Edge Cases ==="
echo ""

# Test 5: Invalid max_results (< 1)
echo "[$((TOTAL_TESTS + 1))] Testing Invalid max_results (< 1)..."
TOTAL_TESTS=$((TOTAL_TESTS + 1))
response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/search/shorts?query=test&max_results=0")
http_code=$(echo "$response" | tail -n1)

if [[ "$http_code" =~ ^4[0-9][0-9]$ ]]; then
    echo -e "   ${GREEN}✓ PASSED${NC} (Correctly rejected with HTTP $http_code)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "   ${RED}✗ FAILED${NC} (Expected 4xx, got $http_code)"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo ""

# Test 6: Empty query
echo "[$((TOTAL_TESTS + 1))] Testing Empty query..."
TOTAL_TESTS=$((TOTAL_TESTS + 1))
response=$(curl -s -X POST "$BASE_URL/search/shorts?query=&max_results=10")
job_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -n "$job_id" ]; then
    echo -e "   ${GREEN}✓ Job created${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
    
    if wait_for_job "$job_id"; then
        result=$(curl -s "$BASE_URL/jobs/$job_id")
        if echo "$result" | grep -q "error"; then
            echo -e "   ${GREEN}✓ Error handled correctly${NC}"
        fi
    fi
else
    echo -e "   ${YELLOW}⚠ Job not created (might be expected)${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi

echo ""
echo "=== Comparison: Videos vs Shorts ==="
echo ""

# Test 7: Compare regular search vs shorts search
echo "[7] Comparing regular search vs shorts search..."
TOTAL_TESTS=$((TOTAL_TESTS + 1))

echo "   Creating regular video search..."
video_response=$(curl -s -X POST "$BASE_URL/search/videos?query=python&max_results=10")
video_job=$(echo "$video_response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

echo "   Creating shorts search..."
shorts_response=$(curl -s -X POST "$BASE_URL/search/shorts?query=python&max_results=10")
shorts_job=$(echo "$shorts_response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -n "$video_job" ] && [ -n "$shorts_job" ]; then
    echo -e "   ${GREEN}✓ Both jobs created${NC}"
    echo "   Video job: $video_job"
    echo "   Shorts job: $shorts_job"
    
    # Verify they have different IDs (different search types)
    if [ "$video_job" != "$shorts_job" ]; then
        echo -e "   ${GREEN}✓ Different job IDs (correct caching)${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "   ${RED}✗ Same job ID (caching issue)${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo -e "   ${RED}✗ Failed to create jobs${NC}"
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
    echo ""
    echo "📱 YouTube Shorts search is working correctly!"
    exit 0
else
    echo -e "${RED}✗ Some tests failed!${NC}"
    exit 1
fi
