#!/usr/bin/env bash

# avg-speedtests.sh - Scientific accuracy Lighthouse testing
# Usage: ./avg-speedtests.sh <url> [runs] [options]
# Options: --fast         Skip throttling for quicker runs
#          --cleanup      Auto-delete raw reports after (no prompt)
#          --no-cleanup   Keep raw reports (no prompt)

set -euo pipefail

# Parse flags and positional args (flags can appear anywhere)
FAST_MODE=false
CLEANUP_MODE="ask"  # ask | yes | no
POSITIONAL=()
for arg in "$@"; do
    case "$arg" in
        --fast) FAST_MODE=true ;;
        --cleanup) CLEANUP_MODE="yes" ;;
        --no-cleanup) CLEANUP_MODE="no" ;;
        *) POSITIONAL+=("$arg") ;;
    esac
done

# Configuration
URL="${POSITIONAL[0]:-}"
RUNS="${POSITIONAL[1]:-5}"
REPORT_DIR="./lighthouse-reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Validation
if [ -z "$URL" ]; then
    echo -e "${RED}Error: URL required${NC}"
    echo "Usage: $0 <url> [runs] [--fast] [--cleanup|--no-cleanup]"
    echo "Example: $0 https://example.com 10"
    echo "Example: $0 https://example.com 10 --fast --cleanup"
    exit 1
fi

mkdir -p "$REPORT_DIR"
TEMP_DIR="$REPORT_DIR/temp_$TIMESTAMP"
mkdir -p "$TEMP_DIR"

CHROME_FLAGS="--headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --disable-extensions --disable-background-networking --disable-default-apps --disable-sync --disable-translate --metrics-recording-only --no-first-run --safebrowsing-disable-auto-update"

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Scientific Lighthouse Performance Test${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "URL:              ${GREEN}$URL${NC}"
echo -e "Total Runs:       ${GREEN}$RUNS${NC}"
echo -e "Mode:             ${CYAN}$( $FAST_MODE && echo "FAST (no throttling)" || echo "Standard" ) | Sequential${NC}"
echo -e "Timestamp:        ${GREEN}$TIMESTAMP${NC}"
echo ""

# Always do a warmup run to stabilize DNS, TLS, and Chrome startup
echo -e "${YELLOW}Warm-up run (discarded)...${NC}"
lighthouse "$URL" \
    --output=json \
    --output-path=/dev/null \
    --only-categories=performance \
    --chrome-flags="$CHROME_FLAGS" \
    --quiet || true

sleep 5
echo ""

run_lighthouse() {
    local run_number=$1
    local output_file="$TEMP_DIR/report_$run_number.json"
    local log_file="$TEMP_DIR/run_$run_number.log"
    
    # Fresh Chrome profile per run - prevents cross-run cache pollution
    local chrome_profile="$TEMP_DIR/chrome_profile_$run_number"
    mkdir -p "$chrome_profile"

    local extra_flags=""
    if [ "$FAST_MODE" = "true" ]; then
        extra_flags="--throttling.cpuSlowdownMultiplier=1 --throttling.rttMs=0 --throttling.throughputKbps=0"
    fi

    {
        # shellcheck disable=SC2086
        lighthouse "$URL" \
            --output=json \
            --output-path="$output_file" \
            --only-categories=performance \
            --chrome-flags="$CHROME_FLAGS --user-data-dir=$chrome_profile" \
            --max-wait-for-load=15000 \
            --disable-storage-reset \
            $extra_flags \
            --quiet \
            2>&1 | grep -v "^$" || true
    } > "$log_file" 2>&1
}

echo -e "${YELLOW}Running sequential Lighthouse audits...${NC}"
if [ "$FAST_MODE" = "true" ]; then
    echo -e "${CYAN}  ⚡ Fast mode: throttling disabled${NC}"
fi
echo ""

START_TIME=$(date +%s)

for i in $(seq 1 "$RUNS"); do
    echo -e "${CYAN}Run $i/$RUNS${NC}"
    run_lighthouse "$i"
    
    if [ "$i" -lt "$RUNS" ]; then
        echo -e "${CYAN}Cooling down...${NC}"
        sleep 8
    fi
done

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

echo -e "${GREEN}✓ All tests completed in ${TOTAL_TIME}s${NC}"
echo ""

# Check for failures
EXPECTED_REPORTS=$RUNS
ACTUAL_REPORTS=$(find "$TEMP_DIR" -name "report_*.json" -type f | wc -l)

if [ "$ACTUAL_REPORTS" -lt "$EXPECTED_REPORTS" ]; then
    echo -e "${RED}Warning: Only $ACTUAL_REPORTS/$EXPECTED_REPORTS reports generated${NC}"
    echo -e "${YELLOW}Check logs in: $TEMP_DIR/*.log${NC}"
    echo ""
fi

# Process results with jq
echo -e "${YELLOW}Processing results...${NC}"

# Create summary JSON with corrected jq syntax
jq -s '
# Define all statistical functions FIRST
def average: add / length;
def minimum: min;
def maximum: max;
def median_calc: 
  sort as $sorted |
  length as $len |
  if ($len % 2) == 0 then
    (($sorted[($len / 2 | floor) - 1] + $sorted[$len / 2 | floor]) / 2)
  else
    $sorted[($len / 2) | floor]
  end;

def stddev_calc:
  . as $arr |
  ($arr | average) as $mean |
  ($arr | map(. - $mean | . * .) | average | sqrt);

# Extract performance metrics from all runs (null-safe)
def extract_metrics:
  {
    performance_score: ((.categories.performance.score // 0) * 100),
    fcp: (.audits."first-contentful-paint".numericValue // 0),
    lcp: (.audits."largest-contentful-paint".numericValue // 0),
    si: (.audits."speed-index".numericValue // 0),
    tbt: (.audits."total-blocking-time".numericValue // 0),
    tti: (.audits.interactive.numericValue // 0),
    cls: (.audits."cumulative-layout-shift".numericValue // 0)
  };

# Filter out failed runs (no performance score) then process
[.[] | select(.categories.performance.score != null)] |
if length == 0 then error("No valid Lighthouse reports found") else . end |
map(extract_metrics) as $metrics |

{
  summary: {
    url: .[0].requestedUrl,
    runs: length,
    timestamp: .[0].fetchTime,
    device: .[0].configSettings.formFactor,
    lighthouse_version: .[0].lighthouseVersion
  },
  statistics: {
    performance_score: {
      avg: ($metrics | map(.performance_score) | average | round),
      min: ($metrics | map(.performance_score) | minimum | round),
      max: ($metrics | map(.performance_score) | maximum | round),
      median: ($metrics | map(.performance_score) | median_calc | round),
      stddev: ($metrics | map(.performance_score) | stddev_calc | round)
    },
    fcp_ms: {
      avg: ($metrics | map(.fcp) | average | round),
      min: ($metrics | map(.fcp) | minimum | round),
      max: ($metrics | map(.fcp) | maximum | round),
      median: ($metrics | map(.fcp) | median_calc | round)
    },
    lcp_ms: {
      avg: ($metrics | map(.lcp) | average | round),
      min: ($metrics | map(.lcp) | minimum | round),
      max: ($metrics | map(.lcp) | maximum | round),
      median: ($metrics | map(.lcp) | median_calc | round)
    },
    si_ms: {
      avg: ($metrics | map(.si) | average | round),
      min: ($metrics | map(.si) | minimum | round),
      max: ($metrics | map(.si) | maximum | round),
      median: ($metrics | map(.si) | median_calc | round)
    },
    tbt_ms: {
      avg: ($metrics | map(.tbt) | average | round),
      min: ($metrics | map(.tbt) | minimum | round),
      max: ($metrics | map(.tbt) | maximum | round),
      median: ($metrics | map(.tbt) | median_calc | round)
    },
    tti_ms: {
      avg: ($metrics | map(.tti) | average | round),
      min: ($metrics | map(.tti) | minimum | round),
      max: ($metrics | map(.tti) | maximum | round),
      median: ($metrics | map(.tti) | median_calc | round)
    },
    cls: {
      avg: ($metrics | map(.cls) | average * 1000 | round / 1000),
      min: ($metrics | map(.cls) | minimum * 1000 | round / 1000),
      max: ($metrics | map(.cls) | maximum * 1000 | round / 1000),
      median: ($metrics | map(.cls) | median_calc * 1000 | round / 1000)
    }
  },
  individual_runs: $metrics
}
' "$TEMP_DIR"/report_*.json > "$REPORT_DIR/summary_$TIMESTAMP.json"

# Generate human-readable output
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PERFORMANCE RESULTS (Statistics from $ACTUAL_REPORTS runs)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

jq -r '
def score_emoji(score):
  if score >= 90 then "🟢"
  elif score >= 50 then "🟡"
  else "🔴"
  end;

def cls_emoji(cls):
  if cls <= 0.1 then "🟢"
  elif cls <= 0.25 then "🟡"
  else "🔴"
  end;

def ms_to_s: (. / 1000 * 100 | round / 100);

"📊 CORE WEB VITALS (Median Values)",
"",
"  Performance Score:  \(score_emoji(.statistics.performance_score.median)) \(.statistics.performance_score.median)/100  (±\(.statistics.performance_score.stddev))",
"",
"  First Contentful Paint (FCP):      \(.statistics.fcp_ms.median | ms_to_s)s  (range: \(.statistics.fcp_ms.min | ms_to_s)s - \(.statistics.fcp_ms.max | ms_to_s)s)",
"  Largest Contentful Paint (LCP):    \(.statistics.lcp_ms.median | ms_to_s)s  (range: \(.statistics.lcp_ms.min | ms_to_s)s - \(.statistics.lcp_ms.max | ms_to_s)s)",
"  Cumulative Layout Shift (CLS):     \(cls_emoji(.statistics.cls.median)) \(.statistics.cls.median)  (range: \(.statistics.cls.min) - \(.statistics.cls.max))",
"",
"📈 ADDITIONAL METRICS (Median Values)",
"",
"  Speed Index (SI):                  \(.statistics.si_ms.median | ms_to_s)s  (range: \(.statistics.si_ms.min | ms_to_s)s - \(.statistics.si_ms.max | ms_to_s)s)",
"  Total Blocking Time (TBT):         \(.statistics.tbt_ms.median)ms  (range: \(.statistics.tbt_ms.min)ms - \(.statistics.tbt_ms.max)ms)",
"  Time to Interactive (TTI):         \(.statistics.tti_ms.median | ms_to_s)s  (range: \(.statistics.tti_ms.min | ms_to_s)s - \(.statistics.tti_ms.max | ms_to_s)s)",
"",
"📊 STATISTICAL SUMMARY",
"",
"  Total Runs:         \(.summary.runs)",
"  Test Duration:      '"$TOTAL_TIME"'s",
"  Avg per Run:        '"$((TOTAL_TIME / RUNS))"'s",
"  Lighthouse:         \(.summary.lighthouse_version)",
"",
"🎯 PERFORMANCE THRESHOLDS",
"",
"  FCP:  Good < 1.8s  | Needs Improvement < 3s  | Poor ≥ 3s",
"  LCP:  Good < 2.5s  | Needs Improvement < 4s  | Poor ≥ 4s",
"  CLS:  Good < 0.1   | Needs Improvement < 0.25 | Poor ≥ 0.25",
"  TBT:  Good < 200ms | Needs Improvement < 600ms | Poor ≥ 600ms",
""
' "$REPORT_DIR/summary_$TIMESTAMP.json"

# Score interpretation
MEDIAN_SCORE=$(jq -r '.statistics.performance_score.median' "$REPORT_DIR/summary_$TIMESTAMP.json")
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

if (( $(echo "$MEDIAN_SCORE >= 90" | bc -l 2>/dev/null || echo "0") )); then
    echo -e "${GREEN}✓ EXCELLENT${NC} - Performance is optimal"
elif (( $(echo "$MEDIAN_SCORE >= 50" | bc -l 2>/dev/null || echo "0") )); then
    echo -e "${YELLOW}⚠ NEEDS IMPROVEMENT${NC} - Some optimization recommended"
else
    echo -e "${RED}✗ POOR${NC} - Significant optimization needed"
fi

echo ""
echo -e "Summary JSON:  ${BLUE}$REPORT_DIR/summary_$TIMESTAMP.json${NC}"
echo -e "Raw reports:   ${BLUE}$TEMP_DIR/${NC}"
echo -e "Logs:          ${BLUE}$TEMP_DIR/*.log${NC}"
echo ""

if [ "$CLEANUP_MODE" = "yes" ]; then
    rm -rf "$TEMP_DIR"
    echo -e "${GREEN}✓${NC} Temporary files deleted (auto-cleanup)"
elif [ "$CLEANUP_MODE" = "ask" ]; then
    read -p "Delete raw reports and logs? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$TEMP_DIR"
        echo -e "${GREEN}✓${NC} Temporary files deleted"
    fi
fi

echo ""
echo -e "${GREEN}✓ Testing complete!${NC}"
