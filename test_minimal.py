#!/usr/bin/env python3
"""Minimal test to verify parameter order fixes."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_parameter_order():
    """Test that parameter order is correct by examining the source code."""
    print("Testing parameter order...")
    
    # Read the customer repository file
    repo_file = os.path.join(os.path.dirname(__file__), 'src', 'supportdesk', 'customers', 'repository.py')
    
    with open(repo_file, 'r') as f:
        content = f.read()
    
    # Look for the get_by_id method signature
    lines = content.split('\n')
    in_get_by_id = False
    
    for line in lines:
        if 'async def get_by_id(' in line:
            in_get_by_id = True
            continue
        
        if in_get_by_id:
            if 'customer_id: UUID,' in line:
                print("[OK] Found customer_id parameter first")
                return True
            elif 'tenant_id: UUID,' in line and 'customer_id' not in content[:content.find(line)]:
                print("[FAIL] tenant_id appears before customer_id")
                return False
            elif ')' in line and 'customer_id' not in line:
                break
    
    print("[FAIL] Could not find get_by_id method signature")
    return False

def test_enum_imports():
    """Test that enum imports work."""
    print("Testing enum imports...")
    
    try:
        from supportdesk.common.enums import ThreadState, PlatformType, ActorType, MessageType
        print("[OK] All enums imported successfully")
        
        # Test a few values
        assert ThreadState.NEW == "new"
        assert PlatformType.WHATSAPP == "whatsapp"
        assert ActorType.SYSTEM == "system"
        assert MessageType.INBOUND == "inbound"
        print("[OK] Enum values are correct")
        
        return True
    except Exception as e:
        print(f"[FAIL] Enum import failed: {e}")
        return False

def main():
    """Run minimal tests."""
    print("Running minimal P2 fixes verification...\n")
    
    tests = [
        test_parameter_order,
        test_enum_imports,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All tests passed! The core fixes look good.")
        return 0
    else:
        print("Some tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
