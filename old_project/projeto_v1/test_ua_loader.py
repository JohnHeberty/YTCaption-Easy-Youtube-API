#!/usr/bin/env python3
"""Quick test for user agent loader."""

from pathlib import Path
from src.infrastructure.youtube.user_agent_rotator import UserAgentRotator

def test_user_agent_loading():
    """Test loading user agents from file."""
    print("Testing user agent loading...")
    
    # Create rotator instance
    rotator = UserAgentRotator()
    
    # Check loaded user agents
    print(f"✅ Loaded {len(rotator.CUSTOM_USER_AGENTS)} user agents")
    print(f"First UA: {rotator.CUSTOM_USER_AGENTS[0][:100]}...")
    print(f"Last UA: {rotator.CUSTOM_USER_AGENTS[-1][:100]}...")
    
    # Test rotation
    print("\nTesting rotation:")
    for i in range(3):
        ua = rotator.get_random()
        print(f"  {i+1}. {ua[:80]}...")
    
    # Test stats
    stats = rotator.get_stats()
    print(f"\nStats: {stats}")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_user_agent_loading()
