#!/bin/bash
# Monitoring script for Smart Money Signal System

LOG_FILE="/tmp/signal-system-monitor.log"
SIGNAL_LOG="/tmp/signal-system.log"
SCRAPER_LOG="/tmp/market-scraper.log"

echo "$(date): Monitor started" >> "$LOG_FILE"

while true; do
    # Check signal system health
    HEALTH=$(curl -s http://localhost:4341/health 2>/dev/null)

    if [ -z "$HEALTH" ]; then
        echo "$(date): ERROR - Signal system not responding" >> "$LOG_FILE"
    fi

    # Check for errors in logs
    SIGNAL_ERRORS=$(grep -i "error\|exception\|failed" "$SIGNAL_LOG" 2>/dev/null | tail -5)
    if [ -n "$SIGNAL_ERRORS" ]; then
        echo "$(date): Signal system errors detected:" >> "$LOG_FILE"
        echo "$SIGNAL_ERRORS" >> "$LOG_FILE"
    fi

    SCRAPER_ERRORS=$(grep -i "error\|exception\|failed" "$SCRAPER_LOG" 2>/dev/null | tail -5)
    if [ -n "$SCRAPER_ERRORS" ]; then
        echo "$(date): Market scraper errors detected:" >> "$LOG_FILE"
        echo "$SCRAPER_ERRORS" >> "$LOG_FILE"
    fi

    # Log stats every 5 minutes
    MINUTE=$(date +%M)
    if [ "$MINUTE" = "00" ] || [ "$MINUTE" = "05" ] || [ "$MINUTE" = "10" ] || [ "$MINUTE" = "15" ] || [ "$MINUTE" = "20" ] || [ "$MINUTE" = "25" ] || [ "$MINUTE" = "30" ] || [ "$MINUTE" = "35" ] || [ "$MINUTE" = "40" ] || [ "$MINUTE" = "45" ] || [ "$MINUTE" = "50" ] || [ "$MINUTE" = "55" ]; then
        MSG_COUNT=$(echo "$HEALTH" | grep -o '"message_count":[0-9]*' | grep -o '[0-9]*')
        TRACKED=$(echo "$HEALTH" | grep -o '"tracked_traders":[0-9]*' | head -1 | grep -o '[0-9]*')
        SIGNALS=$(echo "$HEALTH" | grep -o '"signals_generated":[0-9]*' | grep -o '[0-9]*')
        echo "$(date): Stats - messages: $MSG_COUNT, traders: $TRACKED, signals: $SIGNALS" >> "$LOG_FILE"
    fi

    sleep 60
done
