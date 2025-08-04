#!/usr/bin/env python3
"""
Test runner script for the automerge project.
Provides convenient commands for running tests with coverage reporting.
"""

import argparse
import subprocess
import sys
import os


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n🔄 {description}...")
    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, text=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"❌ {description} failed with error: {e}")
        return False


def install_dependencies():
    """Install project dependencies."""
    return run_command(
        ["python", "-m", "pip", "install", "-r", "requirements.txt"],
        "Installing dependencies"
    )


def run_tests_only():
    """Run tests without coverage."""
    return run_command(
        ["python", "-m", "unittest", "discover",
            "-s", "./tests", "-p", "test_*.py", "-v"],
        "Running unit tests"
    )


def run_tests_with_coverage():
    """Run tests with coverage reporting."""
    commands = [
        (["coverage", "run", "-m", "unittest", "discover", "-s", "./tests", "-p", "test_*.py"],
         "Running tests with coverage"),
        (["coverage", "report"], "Generating coverage report"),
    ]

    for cmd, desc in commands:
        if not run_command(cmd, desc):
            return False
    return True


def generate_html_coverage():
    """Generate HTML coverage report."""
    return run_command(
        ["coverage", "html"],
        "Generating HTML coverage report"
    )


def generate_xml_coverage():
    """Generate XML coverage report."""
    return run_command(
        ["coverage", "xml"],
        "Generating XML coverage report"
    )


def run_linting():
    """Run code linting with ruff."""
    return run_command(
        ["ruff", "check", "."],
        "Running code linting"
    )


def clean_coverage():
    """Clean coverage files."""
    files_to_clean = [".coverage", "coverage.xml"]
    dirs_to_clean = ["htmlcov", ".coverage_cache"]

    print("\n🧹 Cleaning coverage files...")

    for file_path in files_to_clean:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Removed {file_path}")

    for dir_path in dirs_to_clean:
        if os.path.exists(dir_path):
            import shutil
            shutil.rmtree(dir_path)
            print(f"Removed directory {dir_path}")

    print("✅ Cleanup completed")
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test runner for automerge project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py --install --test --coverage
  python run_tests.py --quick
  python run_tests.py --full
  python run_tests.py --clean
        """
    )

    parser.add_argument("--install", action="store_true",
                        help="Install dependencies")
    parser.add_argument("--test", action="store_true",
                        help="Run unit tests only")
    parser.add_argument("--coverage", action="store_true",
                        help="Run tests with coverage")
    parser.add_argument("--html", action="store_true",
                        help="Generate HTML coverage report")
    parser.add_argument("--xml", action="store_true",
                        help="Generate XML coverage report")
    parser.add_argument("--lint", action="store_true",
                        help="Run code linting")
    parser.add_argument("--clean", action="store_true",
                        help="Clean coverage files")

    # Convenience options
    parser.add_argument("--quick", action="store_true",
                        help="Quick test run (tests only)")
    parser.add_argument("--full", action="store_true",
                        help="Full test suite (coverage + HTML + lint)")
    parser.add_argument("--full_no_web", action="store_true",
                        help="Full test suite (coverage + lint)")

    parser.add_argument("--ci", action="store_true",
                        help="CI mode (coverage + XML)")

    args = parser.parse_args()

    # Check if we're in the right directory
    if not os.path.exists("src") or not os.path.exists("tests"):
        print("❌ Error: This script must be run from the project root directory")
        print("   Make sure you're in the directory containing 'src' and 'tests' folders")
        sys.exit(1)

    success = True

    # Handle convenience options
    if args.quick:
        args.test = True
    elif args.full_no_web:
        args.install = True
        args.coverage = True
        args.lint = True
    elif args.full:
        args.install = True
        args.coverage = True
        args.html = True
        args.lint = True
    elif args.ci:
        args.coverage = True
        args.xml = True

    # If no options specified, show help
    if not any([args.install, args.test, args.coverage, args.html,
                args.xml, args.lint, args.clean]):
        parser.print_help()
        sys.exit(0)

    print("🚀 Automerge Test Runner")
    print("=" * 50)

    # Execute requested actions
    if args.clean:
        success &= clean_coverage()

    if args.install:
        success &= install_dependencies()

    if args.test:
        success &= run_tests_only()

    if args.coverage:
        success &= run_tests_with_coverage()

    if args.html:
        success &= generate_html_coverage()
        if success:
            html_path = os.path.abspath("htmlcov/index.html")
            print(f"📊 HTML coverage report: file:{html_path}")

    if args.xml:
        success &= generate_xml_coverage()

    if args.lint:
        success &= run_linting()

    print("\n" + "=" * 50)
    if success:
        print("🎉 All operations completed successfully!")
        sys.exit(0)
    else:
        print("💥 Some operations failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
