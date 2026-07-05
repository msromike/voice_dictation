"""
Test script for PTTListener - Chunk 1 validation

Tests middle mouse button detection independently.
Press middle mouse button to see "PRESSED" message.
Release to see "RELEASED" message.
Press Ctrl+C to exit.
"""

import sys
sys.path.insert(0, '.')

from vdict.keyboard import PTTListener

def main():
    print("PTTListener Test")
    print("=" * 50)
    print("Initializing mouse listener...")
    
    ptt = PTTListener("middle", debug=True)  # Enable debug mode
    
    print("Listener active!")
    print("Try pressing ANY mouse button to test detection...")
    print("(Looking for middle mouse button)")
    print("Press Ctrl+C to exit")
    print()
    
    try:
        count = 0
        while True:
            print(f"[{count}] Waiting for middle mouse press...")
            ptt.wait_for_press()
            print(f"[{count}] PRESSED - Middle mouse button down")
            
            ptt.wait_for_release()
            print(f"[{count}] RELEASED - Middle mouse button up")
            print()
            count += 1
            
    except KeyboardInterrupt:
        print("\nCtrl+C detected - stopping...")
        ptt.stop()
        print("Test complete")


if __name__ == "__main__":
    main()
