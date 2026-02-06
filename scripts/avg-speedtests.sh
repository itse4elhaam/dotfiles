#!/usr/bin/env bash

# lighthouse-perf-parallel.sh - Aggressive parallel Lighthouse testing
# Usage: ./lighthouse-perf-parallel.sh <url> [runs] [max-parallel] [options]
# Options: --fast       Skip throttling for quicker runs
#          --cleanup    Auto-delete raw reports after (no prompt)
#          --no-cleanup Keep raw reports (no prompt)

set -euo pipefail

# Configuration
URL="${1:-}"
RUNS="${2:-5}"
MAX_PARALLEL="${3:-}"
REPORT_DIR="./lighthouse-reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Parse flags from remaining args
FAST_MODE=false
CLEANUP_MODE="ask"  # ask | yes | no
for arg in "${@:4}"; do
    case "$arg" in
        --fast) FAST_MODE=true ;;
        --cleanup) CLEANUP_MODE="yes" ;;
        --no-cleanup) CLEANUP_MODE="no" ;;
    esac
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

detect_max_parallel() {
    local cpu_cores available_mem_gb max_by_cpu max_by_mem

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        cpu_cores=$(nproc 2>/dev/null || echo 4)
        available_mem_gb=$(free -g 2>/dev/null | awk '/^Mem:/{print $7}' || echo 8)
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        cpu_cores=$(sysctl -n hw.ncpu 2>/dev/null || echo 4)
        available_mem_gb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 8589934592) / 1024 / 1024 / 1024 ))
    else
        cpu_cores=4
        available_mem_gb=8
    fi

    # Aggressive: use all cores, ~1GB per instance
    max_by_cpu=$cpu_cores
    max_by_mem=$((available_mem_gb > 1 ? available_mem_gb : 2))

    local optimal=$((max_by_cpu < max_by_mem ? max_by_cpu : max_by_mem))
    optimal=$((optimal < 2 ? 2 : (optimal > 16 ? 16 : optimal)))

    echo "$optimal"
}

# Validation
if [ -z "$URL" ]; then
    echo -e "${RED}Error: URL required${NC}"
    echo "Usage: $0 <url> [runs] [max-parallel] [--fast] [--cleanup|--no-cleanup]"
    echo "Example: $0 https://example.com 10"
    echo "Example: $0 https://example.com 10 4 --fast --cleanup"
    exit 1
fi

# Set parallelism
if [ -z "$MAX_PARALLEL" ]; then
    MAX_PARALLEL=$(detect_max_parallel)
fi

if [ "$MAX_PARALLEL" -lt 1 ]; then
    MAX_PARALLEL=1
fi

mkdir -p "$REPORT_DIR"
TEMP_DIR="$REPORT_DIR/temp_$TIMESTAMP"
mkdir -p "$TEMP_DIR"

PROGRESS_FILE="$TEMP_DIR/progress.txt"
FAIL_FILE="$TEMP_DIR/failures.txt"
touch "$PROGRESS_FILE" "$FAIL_FILE"

CHROME_FLAGS="--headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --disable-extensions --disable-background-networking --disable-default-apps --disable-sync --disable-translate --metrics-recording-only --no-first-run --safebrowsing-disable-auto-update"

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Parallel Lighthouse Performance Test${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "URL:              ${GREEN}$URL${NC}"
echo -e "Total Runs:       ${GREEN}$RUNS${NC}"
echo -e "Parallel Jobs:    ${GREEN}$MAX_PARALLEL${NC}"
echo -e "CPU Cores:        ${CYAN}$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 'N/A')${NC}"
echo -e "Mode:             ${CYAN}$( $FAST_MODE && echo "FAST (no throttling)" || echo "Standard" )${NC}"
echo -e "Timestamp:        ${GREEN}$TIMESTAMP${NC}"
echo ""

# Pre-warm: resolve DNS + cache Chrome binary with a throwaway run
echo -e "${YELLOW}Pre-warming Chrome & DNS...${NC}"
lighthouse "$URL" \
    --output=json \
    --output-path=/dev/null \
    --only-categories=performance \
    --chrome-flags="$CHROME_FLAGS" \
    --max-wait-for-load=5000 \
    --quiet \
    2>/dev/null || true
echo -e "${GREEN}✓${NC} Warm-up done"
echo ""

run_lighthouse() {
    local run_number=$1
    local output_file="$TEMP_DIR/report_$run_number.json"
    local log_file="$TEMP_DIR/run_$run_number.log"

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
            --chrome-flags="$CHROME_FLAGS" \
            --max-wait-for-load=15000 \
            $extra_flags \
            --quiet \
            2>&1 | grep -v "^$" || true

        if [ -f "$output_file" ] && [ -s "$output_file" ]; then
            echo "$run_number" >> "$PROGRESS_FILE"
        else
            echo "$run_number" >> "$FAIL_FILE"
        fi
    } > "$log_file" 2>&1
}

export -f run_lighthouse
export URL TEMP_DIR PROGRESS_FILE FAIL_FILE CHROME_FLAGS FAST_MODE

# Progress monitor function (aggressive: 200ms poll, failure tracking)
monitor_progress() {
    local total=$1
    local start_time
    start_time=$(date +%s)

    while true; do
        local completed failed done_total
        completed=$(wc -l < "$PROGRESS_FILE" 2>/dev/null || echo 0)
        failed=$(wc -l < "$FAIL_FILE" 2>/dev/null || echo 0)
        done_total=$((completed + failed))

        local current_time elapsed
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))

        if [ "$done_total" -ge "$total" ]; then
            break
        fi

        local percent=$((done_total * 100 / total))
        local bar_length=40
        local filled=$((percent * bar_length / 100))
        local empty=$((bar_length - filled))

        local eta="calculating..."
        if [ "$done_total" -gt 0 ]; then
            local avg_time=$((elapsed / done_total))
            local remaining=$((total - done_total))
            local eta_seconds=$((avg_time * remaining))
            eta=$(printf "%02d:%02d" $((eta_seconds / 60)) $((eta_seconds % 60)))
        fi

        local fail_str=""
        if [ "$failed" -gt 0 ]; then
            fail_str=" | ${RED}✗${failed}${NC}"
        fi

        printf "\r${YELLOW}Progress: ${NC}["
        printf "%${filled}s" | tr ' ' '█'
        printf "%${empty}s" | tr ' ' '░'
        printf "] ${GREEN}%3d%%${NC} (${GREEN}✓%d${NC}${fail_str}/${CYAN}%d${NC}) | %02d:%02d | ETA: %s  " \
            "$percent" "$completed" "$total" \
            $((elapsed / 60)) $((elapsed % 60)) "$eta"

        sleep 0.2
    done

    echo ""
}

echo -e "${YELLOW}Running $RUNS Lighthouse audits ($MAX_PARALLEL parallel jobs)...${NC}"
if [ "$FAST_MODE" = "true" ]; then
    echo -e "${CYAN}  ⚡ Fast mode: throttling disabled${NC}"
fi
echo ""

monitor_progress "$RUNS" &
MONITOR_PID=$!

START_TIME=$(date +%s)

# Early abort wrapper: kills parallel jobs if >50% fail
run_with_abort() {
    local total=$1
    shift

    "$@" &
    local job_pid=$!

    while kill -0 "$job_pid" 2>/dev/null; do
        local failed
        failed=$(wc -l < "$FAIL_FILE" 2>/dev/null || echo 0)
        local threshold=$(( (total + 1) / 2 ))
        if [ "$failed" -ge "$threshold" ] && [ "$failed" -gt 1 ]; then
            echo ""
            echo -e "${RED}✗ Aborting: $failed/$total runs failed (>50%)${NC}"
            kill "$job_pid" 2>/dev/null || true
            wait "$job_pid" 2>/dev/null || true
            return 1
        fi
        sleep 0.3
    done
    wait "$job_pid"
}

ABORT_FAILED=0
if command -v parallel &> /dev/null; then
    run_with_abort "$RUNS" parallel -j "$MAX_PARALLEL" --will-cite run_lighthouse -- $(seq 1 "$RUNS") || ABORT_FAILED=1
else
    run_with_abort "$RUNS" bash -c 'seq 1 "'"$RUNS"'" | xargs -P "'"$MAX_PARALLEL"'" -I {} bash -c '"'"'run_lighthouse "$@"'"'"' _ {}' || ABORT_FAILED=1
fi

kill $MONITOR_PID 2>/dev/null || true
wait $MONITOR_PID 2>/dev/null || true

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

if [ "$ABORT_FAILED" -eq 1 ]; then
    echo -e "${RED}✗ Aborted after ${TOTAL_TIME}s due to excessive failures${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

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
