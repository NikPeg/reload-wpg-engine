#!/usr/bin/env python3
"""
Script to restart the bot safely
"""

import os
import signal
import subprocess
import time

def kill_bot_processes():
    """Kill all running bot processes"""
    try:
        # Find and kill Python processes running the bot
        result = subprocess.run(['pgrep', '-f', 'wpg_engine.adapters.telegram.bot'], 
                              capture_output=True, text=True)
        
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} bot processes to kill: {pids}")
            
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"Killed process {pid}")
                except ProcessLookupError:
                    print(f"Process {pid} already terminated")
                except Exception as e:
                    print(f"Error killing process {pid}: {e}")
            
            # Wait a bit for processes to terminate
            time.sleep(2)
        else:
            print("No bot processes found")
            
    except FileNotFoundError:
        print("pgrep not found, trying alternative method...")
        # Alternative method using ps
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            
            for line in lines:
                if 'wpg_engine.adapters.telegram.bot' in line and 'python' in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            print(f"Killed process {pid}")
                        except Exception as e:
                            print(f"Error killing process {pid}: {e}")
        except Exception as e:
            print(f"Error with alternative method: {e}")

def start_bot():
    """Start the bot"""
    print("Starting bot...")
    try:
        subprocess.run(['python', '-m', 'wpg_engine.adapters.telegram.bot'])
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error starting bot: {e}")

if __name__ == "__main__":
    print("🔄 Restarting Telegram bot...")
    
    # Kill existing processes
    kill_bot_processes()
    
    # Wait a bit more
    time.sleep(1)
    
    # Start new bot
    start_bot()