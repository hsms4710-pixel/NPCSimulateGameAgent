#!/usr/bin/env python3
"""
NPC Behavior Simulator - Unified Entry Point
=============================================

This is the main entry file for the MRAG (Memory-RAG) enhanced NPC simulation system.

Features:
- DeepSeek LLM-powered intelligent NPC behavior generation
- Four-level decision system (L1-L4: Daily/Fast/Strategic/Deep Reasoning)
- Three-layer memory architecture (Hot/Warm/Cold memory + RAG retrieval)
- Multi-NPC message bus and spatial positioning system
- GUI visualization interface
- Frontend-backend separated Web interface

Usage:
    python run.py              # Start GUI simulator (Tkinter)
    python run.py --web        # Start Web interface (frontend-backend separated)
    python run.py --api        # Start API server only
    python run.py --check      # Check system dependencies
    python run.py --test       # Run test suite
    python run.py --help       # Show help info

Author: SimModel Team
Version: 2.0.0
"""

import sys
import os
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Ensure project directory is in Python path
PROJECT_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_DIR))


def setup_logging(verbose: bool = False):
    """Configure logging system"""
    log_level = logging.DEBUG if verbose else logging.INFO
    log_file = PROJECT_DIR / 'npc_simulator.log'

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Lower third-party library log levels
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('sentence_transformers').setLevel(logging.WARNING)

    return logging.getLogger(__name__)


def check_python_version():
    """Check Python version"""
    if sys.version_info < (3, 8):
        print(f"[X] Requires Python 3.8 or higher")
        print(f"    Current version: {sys.version}")
        return False
    print(f"[OK] Python version: {sys.version.split()[0]}")
    return True


def check_dependencies():
    """Check system dependencies"""
    print("\nChecking system dependencies...")
    print("=" * 50)

    # Required dependencies
    required = {
        'tkinter': 'GUI interface',
        'requests': 'HTTP requests',
        'json': 'JSON processing',
        'threading': 'Multi-threading',
        'datetime': 'Date and time',
        'typing': 'Type annotations',
        'dataclasses': 'Data classes',
        'enum': 'Enum types'
    }

    # Optional dependencies (provide enhanced features)
    optional = {
        'numpy': 'Numerical computing',
        'jieba': 'Chinese word segmentation',
        'sentence_transformers': 'Semantic embedding',
        'faiss': 'Vector search'
    }

    missing_required = []
    missing_optional = []

    # Check required dependencies
    print("\n[Required Dependencies]")
    for module, desc in required.items():
        try:
            __import__(module)
            print(f"  [OK] {module}: {desc}")
        except ImportError:
            print(f"  [X] {module}: {desc} (missing)")
            missing_required.append(module)

    # Check optional dependencies
    print("\n[Optional Dependencies]")
    for module, desc in optional.items():
        try:
            __import__(module)
            print(f"  [OK] {module}: {desc}")
        except ImportError:
            print(f"  [!] {module}: {desc} (not installed, using fallback)")
            missing_optional.append(module)

    # Check project modules
    print("\n[Project Modules]")
    project_modules = [
        'constants',
        'deepseek_client',
        'world_clock',
        'world_lore',
        'npc_persistence',
        'npc_system',
        'gui_interface',
        'npc_optimization'
    ]

    for module in project_modules:
        try:
            __import__(module)
            print(f"  [OK] {module}")
        except Exception as e:
            print(f"  [X] {module}: {str(e)[:50]}")
            missing_required.append(module)

    print("\n" + "=" * 50)

    if missing_required:
        print(f"[X] Missing required dependencies: {', '.join(missing_required)}")
        print("    Please run: pip install -r requirements.txt")
        return False

    if missing_optional:
        print(f"[!] Optional dependencies not installed (won't affect basic features):")
        print(f"    Run to install: pip install {' '.join(missing_optional)}")

    print("[OK] Dependency check passed!")
    return True


def run_tests():
    """Run test suite"""
    print("\nRunning test suite...")
    print("=" * 50)

    try:
        # Try to import and run tests
        import test_suite
        return test_suite.main()
    except ImportError:
        print("[X] Test module not found")
        return 1
    except Exception as e:
        print(f"[X] Test run failed: {e}")
        return 1


def run_gui():
    """Start GUI interface"""
    logger = setup_logging()

    print("\nNPC Behavior Simulator")
    print("=" * 50)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Starting GUI interface...")
    print("\nTip: If API Key is not configured, the system will automatically show config dialog")
    print()

    try:
        from gui_interface import main as gui_main
        logger.info("Starting NPC Simulator GUI")
        gui_main()
        return 0

    except ImportError as e:
        logger.error(f"Import error: {e}")
        print(f"[X] Import error: {e}")
        print("    Please ensure all project files are in the correct location")
        return 1

    except KeyboardInterrupt:
        logger.info("User interrupted program")
        print("\nProgram stopped")
        return 0

    except Exception as e:
        logger.exception(f"Program run error: {e}")
        print(f"[X] Program run error: {e}")
        print("    Please check log file 'npc_simulator.log' for details")
        return 1


def run_api_server(host: str = "0.0.0.0", port: int = 8000):
    """Start API server"""
    logger = setup_logging()

    print("\nNPC Behavior Simulator - API Server")
    print("=" * 50)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Service address: http://{host}:{port}")
    print(f"API docs: http://{host}:{port}/docs")
    print("Press Ctrl+C to stop server")
    print()

    try:
        import uvicorn
        from backend.api_server import app

        # Windows event loop configuration
        if sys.platform == "win32":
            import asyncio
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        logger.info(f"Starting API server: {host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info", ws="websockets")
        return 0

    except ImportError as e:
        logger.error(f"Import error: {e}")
        print(f"[X] Missing dependency: {e}")
        print("    Please run: pip install fastapi uvicorn[standard] websockets")
        return 1

    except KeyboardInterrupt:
        logger.info("User interrupted server")
        print("\nServer stopped")
        return 0

    except Exception as e:
        logger.exception(f"Server run error: {e}")
        print(f"[X] Server error: {e}")
        return 1


def run_web(port: int = 8000, no_browser: bool = False):
    """Start Web interface (frontend-backend separated mode)"""
    logger = setup_logging()

    print("\nNPC Behavior Simulator - Web Interface")
    print("=" * 50)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Frontend address: http://localhost:{port}")
    print(f"API address: http://localhost:{port}/api/v1")
    print(f"API docs: http://localhost:{port}/docs")
    print("Press Ctrl+C to stop server")
    print()

    try:
        import uvicorn
        from backend.api_server import app
        import webbrowser
        import threading

        # Windows event loop configuration
        if sys.platform == "win32":
            import asyncio
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # Open browser after delay if not disabled
        if not no_browser:
            def open_browser():
                import time
                time.sleep(1.5)  # Wait for server to start
                webbrowser.open(f"http://localhost:{port}")

            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()

        logger.info(f"Starting Web server: localhost:{port}")
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info", ws="websockets")
        return 0

    except ImportError as e:
        logger.error(f"Import error: {e}")
        print(f"[X] Missing dependency: {e}")
        print("    Please run: pip install fastapi uvicorn[standard] websockets")
        return 1

    except KeyboardInterrupt:
        logger.info("User interrupted server")
        print("\nServer stopped")
        return 0

    except Exception as e:
        logger.exception(f"Server run error: {e}")
        print(f"[X] Server error: {e}")
        return 1


def show_info():
    """Show system info"""
    print("\nNPC Behavior Simulator - System Info")
    print("=" * 50)
    print(f"Project directory: {PROJECT_DIR}")
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")

    # Check API config
    api_config_file = PROJECT_DIR / 'api_config.json'
    if api_config_file.exists():
        import json
        with open(api_config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        api_key = config.get('api_key', '')
        print(f"API config: Configured ({config.get('provider', 'unknown')})")
        print(f"API Key: {api_key[:10]}..." if api_key else "API Key: Not set")
        print(f"Model: {config.get('model', 'unknown')}")
    else:
        print("API config: Not configured (will prompt on startup)")

    # Check frontend/backend files
    frontend_dir = PROJECT_DIR / 'frontend'
    backend_dir = PROJECT_DIR / 'backend'
    print(f"Frontend directory: {'[OK] exists' if frontend_dir.exists() else '[X] not found'}")
    print(f"Backend directory: {'[OK] exists' if backend_dir.exists() else '[X] not found'}")

    print()


def main():
    """Main entry function"""
    parser = argparse.ArgumentParser(
        description='NPC Behavior Simulator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py              Start GUI simulator (Tkinter)
  python run.py --web        Start Web interface (frontend-backend separated)
  python run.py --api        Start API server only
  python run.py --check      Check system dependencies
  python run.py --test       Run test suite
  python run.py --info       Show system info
        """
    )

    # Startup mode options
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--web', action='store_true',
                            help='Start Web interface (frontend-backend separated)')
    mode_group.add_argument('--api', action='store_true',
                            help='Start API server only')
    mode_group.add_argument('--gui', action='store_true',
                            help='Start GUI interface (default)')

    # Server options
    parser.add_argument('--port', type=int, default=8000,
                        help='API server port (default: 8000)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='API server address (default: 0.0.0.0)')
    parser.add_argument('--no-browser', action='store_true',
                        help='Do not auto-open browser in Web mode')

    # Other options
    parser.add_argument('--check', action='store_true',
                        help='Check system dependencies')
    parser.add_argument('--test', action='store_true',
                        help='Run test suite')
    parser.add_argument('--info', action='store_true',
                        help='Show system info')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed logs')

    args = parser.parse_args()

    # Check Python version
    if not check_python_version():
        return 1

    # Handle command line arguments
    if args.info:
        show_info()
        return 0

    if args.check:
        return 0 if check_dependencies() else 1

    if args.test:
        return run_tests()

    # Startup mode selection
    if args.web:
        return run_web(port=args.port, no_browser=args.no_browser)

    if args.api:
        return run_api_server(host=args.host, port=args.port)

    # Default: start GUI
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
