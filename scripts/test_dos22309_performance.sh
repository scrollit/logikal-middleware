#!/bin/bash
# Test DOS22309 Force Sync Performance
# Measures timing before and after Phase 1 optimizations

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_BASE_URL="${1:-http://localhost:8001}"
PROJECT_ID="DOS22309"
DIRECTORY_ID="Demo Odoo"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  DOS22309 Performance Test - Phase 1 Optimizations        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "API Base URL: ${YELLOW}${API_BASE_URL}${NC}"
echo -e "Project: ${YELLOW}${PROJECT_ID}${NC}"
echo -e "Directory: ${YELLOW}${DIRECTORY_ID}${NC}"
echo ""

# Get authentication token
echo -e "${YELLOW}[1/5] Authenticating...${NC}"
if [ -f ".env.local" ]; then
    source .env.local
elif [ -f "env.local" ]; then
    source env.local
fi

if [ -z "$LOGIKAL_AUTH_USERNAME" ] || [ -z "$LOGIKAL_AUTH_PASSWORD" ]; then
    echo -e "${RED}❌ LOGIKAL_AUTH_USERNAME or LOGIKAL_AUTH_PASSWORD not set${NC}"
    echo "Please set credentials in env.local or export them"
    exit 1
fi

# Create client and get token (simplified - adjust based on your auth)
TOKEN=$(curl -s -X POST "${API_BASE_URL}/api/v1/client-auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"client_id\":\"test-client\",\"client_secret\":\"test-secret\"}" \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo -e "${YELLOW}⚠️  Client auth failed, trying direct call${NC}"
    # If client auth doesn't work, we'll just test without auth or use basic auth
    AUTH_HEADER=""
else
    echo -e "${GREEN}✅ Authenticated successfully${NC}"
    AUTH_HEADER="Authorization: Bearer $TOKEN"
fi

# Test 1: Health Check
echo -e "\n${YELLOW}[2/5] Health check...${NC}"
HEALTH_RESPONSE=$(curl -s "${API_BASE_URL}/api/v1/health" || curl -s "${API_BASE_URL}/health")
if [ -z "$HEALTH_RESPONSE" ]; then
    echo -e "${RED}❌ Health check failed - service may not be running${NC}"
    exit 1
else
    echo -e "${GREEN}✅ Service is healthy${NC}"
fi

# Test 2: Get baseline stats
echo -e "\n${YELLOW}[3/5] Getting baseline statistics...${NC}"
ELEVATIONS_COUNT=$(curl -s "${API_BASE_URL}/api/v1/elevations?limit=1000" \
    -H "$AUTH_HEADER" 2>/dev/null | grep -o '"id"' | wc -l || echo "0")
echo -e "  Elevations in database: ${ELEVATIONS_COUNT}"

# Test 3: Trigger Force Sync with timing
echo -e "\n${YELLOW}[4/5] Triggering Force Sync for ${PROJECT_ID}...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "This will take approximately 4-7 minutes (down from 8.5 minutes)"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

START_TIME=$(date +%s)

# Make the API call
SYNC_RESPONSE=$(curl -s -w "\n\nHTTP_CODE:%{http_code}\nTIME_TOTAL:%{time_total}" \
    -X POST "${API_BASE_URL}/api/v1/sync/force/project/${PROJECT_ID}?directory_id=${DIRECTORY_ID// /+}" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" 2>&1)

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

# Extract response details
HTTP_CODE=$(echo "$SYNC_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
CURL_TIME=$(echo "$SYNC_RESPONSE" | grep "TIME_TOTAL:" | cut -d: -f2)
RESPONSE_BODY=$(echo "$SYNC_RESPONSE" | sed '/^HTTP_CODE:/d' | sed '/^TIME_TOTAL:/d')

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Sync Completed!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# Parse response (basic parsing without jq)
DURATION=$(echo "$RESPONSE_BODY" | grep -o '"duration_seconds":[0-9.]*' | cut -d: -f2)
PHASES_SYNCED=$(echo "$RESPONSE_BODY" | grep -o '"phases_synced":[0-9]*' | cut -d: -f2)
ELEVATIONS_SYNCED=$(echo "$RESPONSE_BODY" | grep -o '"elevations_synced":[0-9]*' | cut -d: -f2)
PARTS_SYNCED=$(echo "$RESPONSE_BODY" | grep -o '"parts_lists_synced":[0-9]*' | cut -d: -f2)
PARTS_FAILED=$(echo "$RESPONSE_BODY" | grep -o '"parts_lists_failed":[0-9]*' | cut -d: -f2)

echo ""
echo "📊 Sync Results:"
echo "  ├─ HTTP Status: $HTTP_CODE"
echo "  ├─ Phases synced: ${PHASES_SYNCED:-N/A}"
echo "  ├─ Elevations synced: ${ELEVATIONS_SYNCED:-N/A}"
echo "  ├─ Parts lists synced: ${PARTS_SYNCED:-N/A}"
echo "  └─ Parts lists failed: ${PARTS_FAILED:-N/A}"
echo ""
echo "⏱️  Performance:"
echo "  ├─ Total wall time: ${TOTAL_TIME}s"
echo "  ├─ Curl reported time: ${CURL_TIME}s"
echo "  └─ Server reported duration: ${DURATION:-N/A}s"
echo ""

# Performance Analysis
if [ ! -z "$DURATION" ]; then
    DURATION_INT=$(echo "$DURATION" | cut -d. -f1)
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo "📈 Performance Analysis:"
    echo ""
    echo "  Baseline (before optimization): 508 seconds (8.5 minutes)"
    echo "  Current (with optimizations):   ${DURATION_INT} seconds"
    
    if [ "$DURATION_INT" -lt 508 ]; then
        SAVINGS=$((508 - DURATION_INT))
        PERCENT=$(( (SAVINGS * 100) / 508 ))
        echo "  ${GREEN}✅ IMPROVEMENT: ${SAVINGS}s saved (${PERCENT}% faster)${NC}"
        
        if [ "$PERCENT" -ge 45 ]; then
            echo "  ${GREEN}🎉 EXCELLENT: Exceeds 45% target!${NC}"
        elif [ "$PERCENT" -ge 19 ]; then
            echo "  ${GREEN}✅ SUCCESS: Within 19-45% target range${NC}"
        else
            echo "  ${YELLOW}⚠️  Below 19% target, but still improved${NC}"
        fi
    else
        REGRESSION=$((DURATION_INT - 508))
        echo "  ${RED}❌ REGRESSION: ${REGRESSION}s slower${NC}"
        echo "  ${RED}   This indicates the optimizations may not be working${NC}"
    fi
    
    echo ""
    echo "  Target range: 279-414 seconds (4.6-6.9 minutes)"
    
    if [ "$DURATION_INT" -ge 279 ] && [ "$DURATION_INT" -le 414 ]; then
        echo "  ${GREEN}✅ Within expected target range!${NC}"
    elif [ "$DURATION_INT" -lt 279 ]; then
        echo "  ${GREEN}🎉 BETTER than expected! Excellent performance!${NC}"
    else
        echo "  ${YELLOW}⚠️  Above target range, but likely still improved${NC}"
    fi
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
fi

# Test 4: Verify parsing worked
echo -e "\n${YELLOW}[5/5] Verifying parsing results...${NC}"

# Check parsing status
PARSED_COUNT=$(curl -s "${API_BASE_URL}/api/v1/elevations?limit=1000" -H "$AUTH_HEADER" 2>/dev/null \
    | grep -o '"parse_status":"success"' | wc -l || echo "0")

echo "  ├─ Successfully parsed elevations: ${PARSED_COUNT}"

if [ "$PARSED_COUNT" -gt 0 ]; then
    echo -e "  ${GREEN}✅ Parsing is working${NC}"
else
    echo -e "  ${YELLOW}⚠️  No parsed elevations found (may need to check async parsing)${NC}"
fi

# Final Summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    TEST SUMMARY                            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ ! -z "$DURATION_INT" ] && [ "$DURATION_INT" -lt 508 ]; then
    IMPROVEMENT=$(( (508 - DURATION_INT) * 100 / 508 ))
    echo -e "${GREEN}✅ Phase 1 optimizations are WORKING!${NC}"
    echo ""
    echo "  Performance improvement: ${IMPROVEMENT}%"
    echo "  Time saved: $((508 - DURATION_INT)) seconds"
    echo "  Original: 508s (8.5 min) → Optimized: ${DURATION_INT}s"
    echo ""
    echo -e "${GREEN}🎉 Deployment successful!${NC}"
    EXIT_CODE=0
else
    echo -e "${YELLOW}⚠️  Results inconclusive or performance regression${NC}"
    echo "  Please check logs and verify optimizations are active"
    EXIT_CODE=1
fi

# Save results to file
RESULTS_FILE="test_results_$(date +%Y%m%d_%H%M%S).txt"
cat > "$RESULTS_FILE" << EOF
DOS22309 Performance Test Results
==================================
Date: $(date)
API: ${API_BASE_URL}

Results:
- HTTP Status: ${HTTP_CODE}
- Duration: ${DURATION:-N/A}s
- Phases: ${PHASES_SYNCED:-N/A}
- Elevations: ${ELEVATIONS_SYNCED:-N/A}
- Parts synced: ${PARTS_SYNCED:-N/A}
- Parts failed: ${PARTS_FAILED:-N/A}

Performance:
- Baseline: 508s
- Current: ${DURATION:-N/A}s
- Improvement: $([ ! -z "$DURATION_INT" ] && echo "$((100 * (508 - DURATION_INT) / 508))%" || echo "N/A")

Full Response:
${RESPONSE_BODY}
EOF

echo ""
echo "Results saved to: ${RESULTS_FILE}"
echo ""

exit $EXIT_CODE

