#!/bin/bash
# ??????

set -e

echo "?? Crypto Pump & Dump Detection System - Quick Start"
echo "===================================================="

# ??????
if [ ! -d "venv" ]; then
    echo "?? Creating virtual environment..."
    python3 -m venv venv
fi

# ??????
echo "? Activating virtual environment..."
source venv/bin/activate

# ????
if [ ! -f "venv/installed" ]; then
    echo "?? Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    touch venv/installed
else
    echo "? Dependencies already installed"
fi

# ?? .env ??
if [ ! -f ".env" ]; then
    echo "??  Creating .env from template..."
    cp .env.example .env
    echo "??  Please edit .env file and set POSTGRES_PASSWORD"
    echo "   nano .env"
    exit 1
fi

# ?? Redis
echo "?? Checking Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "??  Redis is not running. Starting Redis..."
    redis-server --daemonize yes
    sleep 1
    if redis-cli ping > /dev/null 2>&1; then
        echo "? Redis started"
    else
        echo "? Failed to start Redis. Please start it manually."
        exit 1
    fi
else
    echo "? Redis is running"
fi

# ?? PostgreSQL
echo "?? Checking PostgreSQL..."
if ! psql -U postgres -c "SELECT 1" > /dev/null 2>&1; then
    echo "? PostgreSQL is not accessible. Please check:"
    echo "   1. Is PostgreSQL running?"
    echo "   2. Can you connect with: psql -U postgres"
    exit 1
else
    echo "? PostgreSQL is running"
fi

# ?????????
if ! psql -U postgres -lqt | cut -d \| -f 1 | grep -qw crypto_pump_dump; then
    echo "?? Creating database..."
    psql -U postgres -c "CREATE DATABASE crypto_pump_dump;"
fi

# ???????
echo "?? Initializing database tables..."
python scripts/setup_database.py

# ????????
read -p "?? Run system tests? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python scripts/test_system.py
fi

# ????
echo ""
echo "===================================================="
echo "?? Starting Crypto Detection System..."
echo "===================================================="
echo ""
echo "?? Tips:"
echo "   ? Press Ctrl+C to stop"
echo "   ? View logs: tail -f logs/crypto_monitor_*.log"
echo "   ? Monitor: bash scripts/monitor_system.sh"
echo ""

python main.py
