#!/usr/bin/env python3
"""
Test script for card generation integration.

Tests the full flow: backend -> card_gen service -> image generation.

Usage:
    python test_card_generation.py
"""
import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.card_gen_client import card_gen_client


def test_card_gen_service_health():
    """Test if card_gen service is accessible."""
    import requests
    
    base_url = os.environ.get("CARD_GEN_SERVICE_URL", "http://localhost:8001")
    
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        response.raise_for_status()
        data = response.json()
        print(f"✅ card_gen service is healthy: {data}")
        return True
    except Exception as e:
        print(f"❌ card_gen service health check failed: {e}")
        print(f"   Make sure card_gen service is running at {base_url}")
        print(f"   Start it with: cd card_gen && ./start.sh")
        return False


def test_card_generation():
    """Test card generation with mock data."""
    print("\n🎨 Testing card generation...")
    
    # Mock cocktail data
    test_data = {
        "cocktail_id": 1,
        "cocktail_name": "Test Mojito",
        "cocktail_name_zh": "测试莫吉托",
        "ai_poetic": "夏日微风轻拂，薄荷清香四溢，一杯莫吉托，让烦恼随风而逝。",
        "mood_caption": "周末放松时光",
        "ingredients": [
            {
                "name": "White Rum",
                "name_zh": "白朗姆酒",
                "measure": "60ml",
                "measure_raw": "60ml",
                "status": "owned",
            },
            {
                "name": "Fresh Mint",
                "name_zh": "新鲜薄荷",
                "measure": "10 leaves",
                "measure_raw": "10片",
                "status": "available",
            },
            {
                "name": "Lime",
                "name_zh": "青柠",
                "measure": "1 whole",
                "measure_raw": "1个",
                "status": "owned",
            },
            {
                "name": "Sugar",
                "name_zh": "糖",
                "measure": "2 tsp",
                "measure_raw": "2茶匙",
                "status": "owned",
            },
            {
                "name": "Soda Water",
                "name_zh": "苏打水",
                "measure": "top up",
                "measure_raw": "加满",
                "status": "available",
            },
        ],
        "user_photo_url": "https://images.unsplash.com/photo-1514362545857-3bc16c4c7d1b?w=800",
        "template_name": "amber",
        "abv_level": "medium",
        "difficulty": 2,
        "mood_tags": ["清爽", "放松"],
        "flavor_tags": ["薄荷", "柑橘", "甜"],
        "glass_type": "highball",
    }
    
    try:
        start_time = time.time()
        print(f"📡 Calling card_gen service...")
        
        image_bytes = card_gen_client.generate_card(**test_data)
        
        elapsed = time.time() - start_time
        print(f"✅ Card generated successfully in {elapsed:.2f}s")
        print(f"   Image size: {len(image_bytes)} bytes ({len(image_bytes) / 1024:.1f} KB)")
        
        # Save test output
        output_path = "test_card_output.png"
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        print(f"   Saved to: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Card generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 VibeMix Card Generation Integration Test")
    print("=" * 60)
    
    # Check environment
    card_gen_url = os.environ.get("CARD_GEN_SERVICE_URL", "http://localhost:8001")
    print(f"\n📍 card_gen service URL: {card_gen_url}")
    
    # Test 1: Health check
    print("\n1️⃣ Testing card_gen service health...")
    if not test_card_gen_service_health():
        print("\n❌ Health check failed. Please start card_gen service first.")
        return 1
    
    # Test 2: Card generation
    print("\n2️⃣ Testing card generation...")
    if not test_card_generation():
        print("\n❌ Card generation test failed.")
        return 1
    
    # All tests passed
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
