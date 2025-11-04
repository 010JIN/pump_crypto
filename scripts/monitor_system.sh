#!/bin/bash
# System monitoring script
# Shows system status and recent alerts

echo "========================================"
echo "???  Crypto Detection System Monitor"
echo "========================================"

# Check if system is running
if pgrep -f "main.py" > /dev/null; then
    echo "? System Status: RUNNING"
    PID=$(pgrep -f "main.py")
    echo "   PID: $PID"
else
    echo "? System Status: STOPPED"
fi

echo ""
echo "?? System Statistics:"
echo "----------------------------------------"

# Database stats
if command -v psql &> /dev/null; then
    echo "PostgreSQL:"
    psql -U postgres crypto_pump_dump -t -c "
        SELECT '  Events detected: ' || COUNT(*) FROM detection_events;
        SELECT '  Active events: ' || COUNT(*) FROM detection_events WHERE status='ACTIVE';
        SELECT '  Factors calculated: ' || COUNT(*) FROM factor_values;
    " 2>/dev/null || echo "  Database not accessible"
fi

# Redis stats
if command -v redis-cli &> /dev/null; then
    echo ""
    echo "Redis:"
    REDIS_KEYS=$(redis-cli DBSIZE 2>/dev/null | awk '{print $2}')
    echo "  Total keys: $REDIS_KEYS"
    WATCHLIST=$(redis-cli ZCARD watchlist 2>/dev/null)
    echo "  Monitored symbols: $WATCHLIST"
fi

# Recent logs
echo ""
echo "?? Recent Activity (last 10 lines):"
echo "----------------------------------------"
if [ -f logs/crypto_monitor_*.log ]; then
    tail -n 10 logs/crypto_monitor_*.log 2>/dev/null | tail -n 10
else
    echo "No logs found"
fi

# System resources
echo ""
echo "?? System Resources:"
echo "----------------------------------------"
if command -v free &> /dev/null; then
    free -h | grep Mem | awk '{print "  Memory: " $3 " / " $2 " used"}'
fi

if command -v df &> /dev/null; then
    df -h . | tail -n 1 | awk '{print "  Disk: " $3 " / " $2 " used (" $5 ")"}'
fi

echo ""
echo "========================================"
