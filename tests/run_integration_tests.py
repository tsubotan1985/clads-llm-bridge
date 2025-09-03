#!/usr/bin/env python3
"""
Integration test runner for CLADS LLM Bridge.
Runs all integration tests in the correct order and provides comprehensive reporting.
"""

import sys
import subprocess
import os
import time
import argparse
from pathlib import Path


class IntegrationTestRunner:
    """Manages and runs integration tests."""
    
    def __init__(self):
        self.test_files = [
            "test_integration_config_workflow.py",
            "test_integration_proxy_functionality.py", 
            "test_integration_monitoring_accuracy.py",
            "test_integration_docker_deployment.py"
        ]
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    def run_test_file(self, test_file, verbose=False):
        """Run a specific test file."""
        print(f"\n{'='*60}")
        print(f"Running {test_file}")
        print(f"{'='*60}")
        
        cmd = ["python", "-m", "pytest", f"tests/{test_file}", "-v"]
        if verbose:
            cmd.append("-s")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout per test file
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            self.results[test_file] = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": duration,
                "success": result.returncode == 0
            }
            
            print(f"Duration: {duration:.2f} seconds")
            
            if result.returncode == 0:
                print(f"✅ {test_file} PASSED")
            else:
                print(f"❌ {test_file} FAILED")
                
            if verbose or result.returncode != 0:
                print("\nSTDOUT:")
                print(result.stdout)
                if result.stderr:
                    print("\nSTDERR:")
                    print(result.stderr)
                    
        except subprocess.TimeoutExpired:
            print(f"⏰ {test_file} TIMED OUT")
            self.results[test_file] = {
                "returncode": -1,
                "stdout": "",
                "stderr": "Test timed out",
                "duration": 600,
                "success": False
            }
        except Exception as e:
            print(f"💥 {test_file} ERROR: {e}")
            self.results[test_file] = {
                "returncode": -2,
                "stdout": "",
                "stderr": str(e),
                "duration": 0,
                "success": False
            }
    
    def run_all_tests(self, verbose=False, skip_docker=False):
        """Run all integration tests."""
        print("🚀 Starting CLADS LLM Bridge Integration Tests")
        print(f"Test files: {len(self.test_files)}")
        
        self.start_time = time.time()
        
        test_files_to_run = self.test_files.copy()
        if skip_docker:
            test_files_to_run = [f for f in test_files_to_run if "docker" not in f]
            print("⚠️  Skipping Docker tests")
        
        for test_file in test_files_to_run:
            self.run_test_file(test_file, verbose)
        
        self.end_time = time.time()
        self.print_summary()
    
    def print_summary(self):
        """Print test summary."""
        print(f"\n{'='*80}")
        print("INTEGRATION TEST SUMMARY")
        print(f"{'='*80}")
        
        total_duration = self.end_time - self.start_time
        passed = sum(1 for r in self.results.values() if r["success"])
        failed = len(self.results) - passed
        
        print(f"Total Duration: {total_duration:.2f} seconds")
        print(f"Tests Run: {len(self.results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        
        print(f"\n{'Test File':<40} {'Status':<10} {'Duration':<10}")
        print("-" * 60)
        
        for test_file, result in self.results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            duration = f"{result['duration']:.2f}s"
            print(f"{test_file:<40} {status:<10} {duration:<10}")
        
        if failed > 0:
            print(f"\n❌ {failed} test(s) failed")
            print("\nFailed test details:")
            for test_file, result in self.results.items():
                if not result["success"]:
                    print(f"\n{test_file}:")
                    if result["stderr"]:
                        print(f"  Error: {result['stderr'][:200]}...")
                    if result["stdout"]:
                        # Extract failure summary from pytest output
                        lines = result["stdout"].split('\n')
                        failure_lines = [line for line in lines if "FAILED" in line or "ERROR" in line]
                        for line in failure_lines[:5]:  # Show first 5 failure lines
                            print(f"  {line}")
        else:
            print("\n🎉 All integration tests passed!")
        
        return failed == 0
    
    def run_specific_test(self, test_name, verbose=False):
        """Run a specific test by name or pattern."""
        matching_files = [f for f in self.test_files if test_name in f]
        
        if not matching_files:
            print(f"❌ No test files found matching '{test_name}'")
            print(f"Available test files: {', '.join(self.test_files)}")
            return False
        
        self.start_time = time.time()
        
        for test_file in matching_files:
            self.run_test_file(test_file, verbose)
        
        self.end_time = time.time()
        self.print_summary()
        
        return all(r["success"] for r in self.results.values())


def check_prerequisites():
    """Check if prerequisites are available."""
    print("🔍 Checking prerequisites...")
    
    # Check if we're in the right directory
    if not os.path.exists("tests"):
        print("❌ Tests directory not found. Run from clads-llm-bridge directory.")
        return False
    
    # Check if pytest is available
    try:
        subprocess.run(["python", "-m", "pytest", "--version"], 
                      capture_output=True, check=True)
        print("✅ pytest available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ pytest not available. Install with: pip install pytest")
        return False
    
    # Check if Docker is available (for Docker tests)
    try:
        subprocess.run(["docker", "--version"], 
                      capture_output=True, check=True)
        print("✅ Docker available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Docker not available. Docker tests will be skipped.")
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run CLADS LLM Bridge integration tests")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Verbose output")
    parser.add_argument("--skip-docker", action="store_true",
                       help="Skip Docker deployment tests")
    parser.add_argument("--test", "-t", type=str,
                       help="Run specific test file (partial name matching)")
    parser.add_argument("--list", "-l", action="store_true",
                       help="List available test files")
    
    args = parser.parse_args()
    
    if not check_prerequisites():
        sys.exit(1)
    
    runner = IntegrationTestRunner()
    
    if args.list:
        print("Available integration test files:")
        for i, test_file in enumerate(runner.test_files, 1):
            print(f"  {i}. {test_file}")
        return
    
    # Change to clads-llm-bridge directory if not already there
    if os.path.basename(os.getcwd()) != "clads-llm-bridge":
        if os.path.exists("clads-llm-bridge"):
            os.chdir("clads-llm-bridge")
        else:
            print("❌ clads-llm-bridge directory not found")
            sys.exit(1)
    
    success = False
    
    if args.test:
        success = runner.run_specific_test(args.test, args.verbose)
    else:
        success = runner.run_all_tests(args.verbose, args.skip_docker)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()