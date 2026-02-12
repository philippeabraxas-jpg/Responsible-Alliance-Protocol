import os
import psutil
import time
import json
from core.tbp_signature_service import TBPFullAuditSystem

def check_memory_leak():
    process = psutil.Process(os.getpid())
    config = {
        "hsm": {"hsm_type": "software"},
        "storage_path": "memory_test_audit.json",
        "tsa": {"enabled": False}
    }
    
    system = TBPFullAuditSystem(config)
    
    print(f"Starting memory check (1000 iterations)...")
    initial_mem = process.memory_info().rss / 1024 / 1024
    print(f"Initial Memory: {initial_mem:.2f} MB")
    
    for i in range(1000):
        # Bypass HSM rate limit for the purpose of the memory test
        system.hsm_signer._rate_limit_counter = 0
        
        system.log_decision(
            decision={"action": "test", "val": i},
            agent_id="test-agent",
            context={"iter": i}
        )
        if i % 200 == 0:
            current_mem = process.memory_info().rss / 1024 / 1024
            print(f"Iteration {i}: {current_mem:.2f} MB")
            
    final_mem = process.memory_info().rss / 1024 / 1024
    print(f"Final Memory: {final_mem:.2f} MB")
    print(f"Diff: {final_mem - initial_mem:.2f} MB")
    
    if final_mem - initial_mem < 5.0:
        print("✓ PASS - No significant memory leak detected.")
    else:
        print("⚠️ WARNING - Memory growth detected. Investigate caching or file handles.")

    # Cleanup
    if os.path.exists("memory_test_audit.json"):
        os.remove("memory_test_audit.json")

if __name__ == "__main__":
    check_memory_leak()
