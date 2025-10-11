#!/usr/bin/env python3
"""
Startup script that runs both the web server and Celery services
"""
import subprocess
import sys
import os
import signal
import time
from multiprocessing import Process

def run_web_server():
    """Run the web server"""
    try:
        subprocess.run([sys.executable, "startup.py"], check=True)
    except KeyboardInterrupt:
        print("Web server stopped")
    except Exception as e:
        print(f"Web server error: {e}")

def run_celery_worker():
    """Run Celery worker"""
    try:
        subprocess.run([
            sys.executable, "-m", "celery", "-A", "app.celery_app", 
            "worker", "--loglevel=info"
        ], check=True)
    except KeyboardInterrupt:
        print("Celery worker stopped")
    except Exception as e:
        print(f"Celery worker error: {e}")

def run_celery_beat():
    """Run Celery beat scheduler"""
    try:
        subprocess.run([
            sys.executable, "-m", "celery", "-A", "app.celery_app", 
            "beat", "--loglevel=info"
        ], check=True)
    except KeyboardInterrupt:
        print("Celery beat stopped")
    except Exception as e:
        print(f"Celery beat error: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("Received shutdown signal, stopping all processes...")
    sys.exit(0)

def main():
    """Main function to start all services"""
    print("Starting Logikal Middleware with Celery services...")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start all processes
    processes = []
    
    try:
        # Start Celery worker
        print("Starting Celery worker...")
        worker_process = Process(target=run_celery_worker)
        worker_process.start()
        processes.append(worker_process)
        
        # Start Celery beat
        print("Starting Celery beat scheduler...")
        beat_process = Process(target=run_celery_beat)
        beat_process.start()
        processes.append(beat_process)
        
        # Give Celery services time to start
        time.sleep(5)
        
        # Start web server (this will block)
        print("Starting web server...")
        run_web_server()
        
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"Error starting services: {e}")
    finally:
        # Clean up processes
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()

if __name__ == "__main__":
    main()
