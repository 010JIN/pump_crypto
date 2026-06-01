#!/usr/bin/env python3
"""
System test script
Tests all major components
"""

import sys
sys.path.append('.')

import asyncio
from datetime import datetime
import numpy as np
from loguru import logger

logger.add("logs/test.log")


async def test_database():
    """Test database connections"""
    print("\n1??  Testing Database Connections...")
    try:
        from src.storage import init_databases
        pg, redis = init_databases()
        
        # Test PostgreSQL
        with pg.session_scope() as session:
            result = session.execute("SELECT 1")
            assert result.fetchone()[0] == 1
        
        # Test Redis
        redis.client.set("test", "value")
        assert redis.client.get("test") == "value"
        redis.client.delete("test")
        
        print("   ? Database connections OK")
        return True
    except Exception as e:
        print(f"   ? Database test failed: {e}")
        return False


def test_factors():
    """Test factor calculations"""
    print("\n2??  Testing Factor Calculations...")
    try:
        from src.factors import PriceFactors, VolumeFactors, LiquidityFactors
        
        # Test price factors
        prices = [100 + i * 0.5 + np.random.normal(0, 0.2) for i in range(60)]
        config = {'velocity_windows': [1, 5, 15], 'volatility_window': 15, 'rsi_period': 14}
        
        price_factors = PriceFactors.calculate_all(prices, config)
        assert 'price_velocity_5m' in price_factors
        assert 'rsi' in price_factors
        
        # Test volume factors
        volumes = [1000 + np.random.normal(0, 100) for _ in range(60)]
        volume_data = {
            'current_volume': 1500,
            'historical_volumes': volumes,
            'taker_buy_volume': 1000,
            'trade_volumes': [10, 15, 8, 50]
        }
        volume_config = {'ratio_window': 60}
        
        volume_factors = VolumeFactors.calculate_all(volume_data, volume_config)
        assert 'volume_spike_score' in volume_factors
        
        print(f"   ? Factor calculations OK ({len(price_factors) + len(volume_factors)} factors)")
        return True
    except Exception as e:
        print(f"   ? Factor test failed: {e}")
        return False


def test_detectors():
    """Test PUMP/DUMP detectors"""
    print("\n3??  Testing Detection Engine...")
    try:
        import yaml
        from src.detectors import PumpDetector, DumpDetector
        
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Test PUMP detector
        pump_detector = PumpDetector(config['detection'])
        pump_factors = {
            'price_velocity_5m': 15.0,
            'volume_spike_score': 0.85,
            'buy_sell_ratio': 3.5,
            'bid_ask_imbalance': 0.7,
            'trade_intensity': 5.0
        }
        
        pump_result = pump_detector.detect(pump_factors)
        assert pump_result['is_pump'] == True
        assert pump_result['confidence'] > 0.6
        
        # Test DUMP detector
        dump_detector = DumpDetector(config['detection'])
        dump_factors = {
            'price_velocity_5m': -12.0,
            'volume_spike_score': 0.80,
            'buy_sell_ratio': 0.3,
            'bid_ask_imbalance': -0.65,
            'price_continuity': 0.45
        }
        
        dump_result = dump_detector.detect(dump_factors)
        assert dump_result['is_dump'] == True
        assert dump_result['confidence'] > 0.6
        
        print(f"   ? Detection engine OK")
        print(f"      PUMP confidence: {pump_result['confidence']:.2%}")
        print(f"      DUMP confidence: {dump_result['confidence']:.2%}")
        return True
    except Exception as e:
        print(f"   ? Detector test failed: {e}")
        return False


def test_alerts():
    """Test alert system"""
    print("\n4??  Testing Alert System...")
    try:
        from src.alerts import ConsoleAlert
        
        config = {'enabled': True, 'color_output': False}
        alert = ConsoleAlert(config)
        
        test_event = {
            'symbol': 'TESTUSDT',
            'event_type': 'PUMP',
            'confidence': 0.85,
            'risk_level': 'HIGH',
            'start_price': 100.0,
            'start_time': datetime.now(),
            'trigger_factors': [
                {'name': 'price_velocity_5m', 'value': 15.0, 'score': 0.9}
            ]
        }
        
        # This should print to console
        alert.send_alert(test_event)
        
        print("   ? Alert system OK")
        return True
    except Exception as e:
        print(f"   ? Alert test failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("\n" + "=" * 50)
    print("?? Running System Tests")
    print("=" * 50)
    
    results = []
    
    # Run tests
    results.append(await test_database())
    results.append(test_factors())
    results.append(test_detectors())
    results.append(test_alerts())
    
    # Summary
    print("\n" + "=" * 50)
    print("?? Test Summary")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n? All tests passed!")
        return 0
    else:
        print(f"\n? {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
