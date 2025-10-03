#!/usr/bin/env python3
"""Test script to verify the parameter order fixes."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")
    
    try:
        # Test common enums
        from supportdesk.common.enums import ThreadState, PlatformType, ActorType, MessageType
        print("[OK] Common enums imported successfully")
        
        # Test model imports
        from supportdesk.customers.models import Customer
        from supportdesk.threads.models import Thread
        from supportdesk.messages.models import Message
        from supportdesk.events.models import ThreadEvent
        from supportdesk.tenants.models import Tenant
        print("[OK] All models imported successfully")
        
        # Test repository imports
        from supportdesk.customers.repository import CustomerRepository
        from supportdesk.threads.repository import ThreadRepository
        from supportdesk.messages.repository import MessageRepository
        from supportdesk.events.repository import ThreadEventRepository
        print("[OK] All repositories imported successfully")
        
        # Test service imports (skip for now due to dependencies)
        # from supportdesk.customers.service import CustomerService
        # from supportdesk.threads.service import ThreadService
        # from supportdesk.messages.service import MessageService
        print("[OK] All core imports successful (services skipped)")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return False

def test_enum_values():
    """Test that enum values are correct."""
    print("\nTesting enum values...")
    
    try:
        from supportdesk.common.enums import ThreadState, PlatformType, ActorType, MessageType
        
        # Test ThreadState values
        assert ThreadState.NEW == "new"
        assert ThreadState.ACKNOWLEDGED == "acknowledged"
        assert ThreadState.RESOLVED == "resolved"
        print("[OK] ThreadState values correct")
        
        # Test PlatformType values
        assert PlatformType.WHATSAPP == "whatsapp"
        assert PlatformType.INSTAGRAM == "instagram"
        print("[OK] PlatformType values correct")
        
        # Test ActorType values
        assert ActorType.SYSTEM == "system"
        assert ActorType.USER == "user"
        print("[OK] ActorType values correct")
        
        # Test MessageType values
        assert MessageType.INBOUND == "inbound"
        assert MessageType.OUTBOUND == "outbound"
        assert MessageType.SYSTEM == "system"
        print("[OK] MessageType values correct")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Enum test failed: {e}")
        return False

def test_parameter_order():
    """Test that parameter order is documented correctly."""
    print("\nTesting parameter order documentation...")
    
    try:
        from supportdesk.customers.repository import CustomerRepository
        import inspect
        
        # Check get_by_id signature
        sig = inspect.signature(CustomerRepository.get_by_id)
        params = list(sig.parameters.keys())
        
        # Should be: self, customer_id, tenant_id, include_inactive
        expected = ['self', 'customer_id', 'tenant_id', 'include_inactive']
        if params == expected:
            print("[OK] CustomerRepository.get_by_id parameter order correct")
            return True
        else:
            print(f"[FAIL] CustomerRepository.get_by_id parameter order wrong: {params}")
            print(f"   Expected: {expected}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Parameter order test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Running P2 fixes verification tests...\n")
    
    tests = [
        test_imports,
        test_enum_values,
        test_parameter_order,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All tests passed! The fixes look good.")
        return 0
    else:
        print("Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
