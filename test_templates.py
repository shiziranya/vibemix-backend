#!/usr/bin/env python3
"""
Test card generation with card_gen service templates.
"""
import sys
sys.path.insert(0, '/opt/vibemix/vibemix-backend')

from app import create_app
from app.services.card_gen_client import card_gen_client

def test_templates():
    """Test getting templates from card_gen service."""
    app = create_app()
    with app.app_context():
        print("Testing card_gen service connection...")
        print()
        
        templates = card_gen_client.get_available_templates()
        
        if not templates:
            print("❌ Failed to get templates from card_gen service")
            print("   Make sure card_gen service is running at: http://localhost:8001")
            return False
        
        print(f"✅ Successfully connected to card_gen service")
        print(f"   Found {len(templates)} templates:")
        print()
        
        for i, template in enumerate(templates, 1):
            print(f"   {i:2d}. {template}")
        
        print()
        print(f"   Default template: {templates[0]}")
        
        return True

if __name__ == "__main__":
    success = test_templates()
    sys.exit(0 if success else 1)
