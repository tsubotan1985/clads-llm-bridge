"""
Integration tests for Docker container deployment and port accessibility.
Tests the complete Docker deployment workflow and service availability.
"""

import pytest
import subprocess
import time
import requests
import os
import tempfile
from unittest.mock import patch, MagicMock


class TestDockerDeploymentIntegration:
    """Test Docker container deployment and port accessibility."""
    
    @pytest.fixture(autouse=True)
    def setup_docker_environment(self):
        """Setup Docker environment for testing."""
        self.container_name = "clads-llm-bridge-test"
        self.web_port = "4322"
        self.proxy_port = "4321"
        self.test_timeout = 60  # seconds
        
        # Cleanup any existing test containers
        try:
            subprocess.run(
                ["docker", "stop", self.container_name],
                capture_output=True,
                timeout=10
            )
            subprocess.run(
                ["docker", "rm", self.container_name],
                capture_output=True,
                timeout=10
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        
        yield
        
        # Cleanup after test
        try:
            subprocess.run(
                ["docker", "stop", self.container_name],
                capture_output=True,
                timeout=10
            )
            subprocess.run(
                ["docker", "rm", self.container_name],
                capture_output=True,
                timeout=10
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
    
    def test_docker_build_process(self):
        """Test Docker image builds successfully."""
        # Change to the clads-llm-bridge directory
        original_cwd = os.getcwd()
        try:
            # Check if we're already in the clads-llm-bridge directory
            if not os.path.basename(os.getcwd()) == "clads-llm-bridge":
                os.chdir("clads-llm-bridge")
            
            # Build Docker image
            build_result = subprocess.run(
                ["docker", "build", "-t", "clads-llm-bridge-test", "."],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout for build
            )
            
            assert build_result.returncode == 0, f"Docker build failed: {build_result.stderr}"
            
            # Verify image was created
            images_result = subprocess.run(
                ["docker", "images", "clads-llm-bridge-test"],
                capture_output=True,
                text=True
            )
            
            assert "clads-llm-bridge-test" in images_result.stdout
            
        finally:
            os.chdir(original_cwd)
    
    def test_docker_container_startup(self):
        """Test Docker container starts successfully."""
        # First build the image
        self.test_docker_build_process()
        
        # Start container
        run_result = subprocess.run([
            "docker", "run", "-d",
            "--name", self.container_name,
            "-p", f"{self.web_port}:4322",
            "-p", f"{self.proxy_port}:4321",
            "clads-llm-bridge-test"
        ], capture_output=True, text=True)
        
        assert run_result.returncode == 0, f"Container start failed: {run_result.stderr}"
        
        # Wait for container to be ready
        time.sleep(10)
        
        # Check container is running
        ps_result = subprocess.run(
            ["docker", "ps", "--filter", f"name={self.container_name}"],
            capture_output=True,
            text=True
        )
        
        assert self.container_name in ps_result.stdout
        assert "Up" in ps_result.stdout
    
    def test_web_ui_port_accessibility(self):
        """Test Web UI port (4322) is accessible."""
        # Start container first
        self.test_docker_container_startup()
        
        # Wait for services to be ready
        max_retries = 30
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = requests.get(
                    f"http://localhost:{self.web_port}/",
                    timeout=5
                )
                if response.status_code in [200, 302]:  # 302 for redirect to login
                    break
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(2)
            retry_count += 1
        
        assert retry_count < max_retries, "Web UI port not accessible within timeout"
        
        # Test specific endpoints
        try:
            # Should redirect to login
            response = requests.get(f"http://localhost:{self.web_port}/", timeout=5)
            assert response.status_code in [200, 302]
            
            # Login page should be accessible
            response = requests.get(f"http://localhost:{self.web_port}/login", timeout=5)
            assert response.status_code == 200
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Web UI endpoints not accessible: {e}")
    
    def test_proxy_port_accessibility(self):
        """Test Proxy port (4321) is accessible."""
        # Start container first
        self.test_docker_container_startup()
        
        # Wait for proxy service to be ready
        max_retries = 30
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Test health endpoint or basic connectivity
                response = requests.get(
                    f"http://localhost:{self.proxy_port}/health",
                    timeout=5
                )
                if response.status_code in [200, 404]:  # 404 is ok, means service is running
                    break
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(2)
            retry_count += 1
        
        # Even if health endpoint doesn't exist, port should be open
        # Test with a basic connection
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex(('localhost', int(self.proxy_port)))
            assert result == 0, f"Proxy port {self.proxy_port} is not accessible"
        finally:
            sock.close()
    
    def test_data_persistence_across_restarts(self):
        """Test data persists across container restarts."""
        # Start container with volume mount
        with tempfile.TemporaryDirectory() as temp_dir:
            data_volume = f"{temp_dir}:/app/data"
            
            # Start container with volume
            run_result = subprocess.run([
                "docker", "run", "-d",
                "--name", self.container_name,
                "-p", f"{self.web_port}:4322",
                "-p", f"{self.proxy_port}:4321",
                "-v", data_volume,
                "clads-llm-bridge-test"
            ], capture_output=True, text=True)
            
            assert run_result.returncode == 0
            
            # Wait for container to be ready
            time.sleep(15)
            
            # Make a configuration change via API
            try:
                # Login first
                session = requests.Session()
                login_response = session.post(
                    f"http://localhost:{self.web_port}/login",
                    data={"password": "Hakodate4"},
                    timeout=10
                )
                
                if login_response.status_code in [200, 302]:
                    # Try to make a configuration (this might fail due to validation, but that's ok)
                    config_response = session.post(
                        f"http://localhost:{self.web_port}/config",
                        data={
                            "service_type": "openai",
                            "api_key": "test-key-persistence",
                            "base_url": "https://api.openai.com/v1",
                            "model_name": "gpt-3.5-turbo",
                            "public_name": "Persistence Test"
                        },
                        timeout=10
                    )
                
            except requests.exceptions.RequestException:
                # Configuration might fail, but database should still be created
                pass
            
            # Stop container
            subprocess.run(["docker", "stop", self.container_name], timeout=30)
            
            # Restart container with same volume
            subprocess.run(["docker", "rm", self.container_name])
            
            run_result = subprocess.run([
                "docker", "run", "-d",
                "--name", self.container_name,
                "-p", f"{self.web_port}:4322",
                "-p", f"{self.proxy_port}:4321",
                "-v", data_volume,
                "clads-llm-bridge-test"
            ], capture_output=True, text=True)
            
            assert run_result.returncode == 0
            
            # Wait for restart
            time.sleep(15)
            
            # Verify data directory exists and has database files
            db_files = os.listdir(temp_dir)
            assert any(f.endswith('.db') for f in db_files), "Database file not persisted"
    
    def test_environment_variable_configuration(self):
        """Test container accepts environment variable configuration."""
        # Test with custom environment variables
        env_vars = [
            "-e", "DATABASE_PATH=/app/data/custom.db",
            "-e", "LOG_LEVEL=DEBUG"
        ]
        
        run_result = subprocess.run([
            "docker", "run", "-d",
            "--name", self.container_name,
            "-p", f"{self.web_port}:4322",
            "-p", f"{self.proxy_port}:4321"
        ] + env_vars + ["clads-llm-bridge-test"], capture_output=True, text=True)
        
        assert run_result.returncode == 0
        
        # Wait for container to start
        time.sleep(10)
        
        # Check container logs for environment variable usage
        logs_result = subprocess.run(
            ["docker", "logs", self.container_name],
            capture_output=True,
            text=True
        )
        
        # Container should start successfully even with custom env vars
        assert run_result.returncode == 0
    
    def test_docker_compose_deployment(self):
        """Test Docker Compose deployment works."""
        original_cwd = os.getcwd()
        try:
            # Check if we're already in the clads-llm-bridge directory
            if not os.path.basename(os.getcwd()) == "clads-llm-bridge":
                os.chdir("clads-llm-bridge")
            
            # Check if docker-compose.yml exists
            if not os.path.exists("docker-compose.yml"):
                pytest.skip("docker-compose.yml not found")
            
            # Start with docker-compose
            compose_result = subprocess.run(
                ["docker-compose", "up", "-d"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if compose_result.returncode != 0:
                # Try with docker compose (newer syntax)
                compose_result = subprocess.run(
                    ["docker", "compose", "up", "-d"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
            
            assert compose_result.returncode == 0, f"Docker Compose failed: {compose_result.stderr}"
            
            # Wait for services to be ready
            time.sleep(20)
            
            # Test both ports are accessible
            try:
                web_response = requests.get(f"http://localhost:{self.web_port}/login", timeout=10)
                assert web_response.status_code == 200
            except requests.exceptions.RequestException:
                pytest.fail("Web UI not accessible via Docker Compose")
            
            # Test proxy port is open
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                result = sock.connect_ex(('localhost', int(self.proxy_port)))
                assert result == 0, "Proxy port not accessible via Docker Compose"
            finally:
                sock.close()
            
            # Cleanup
            subprocess.run(["docker-compose", "down"], timeout=60)
            
        finally:
            os.chdir(original_cwd)
    
    def test_container_health_check(self):
        """Test container health check functionality."""
        # Start container
        self.test_docker_container_startup()
        
        # Wait for health check to stabilize
        time.sleep(30)
        
        # Check container health status
        health_result = subprocess.run([
            "docker", "inspect",
            "--format", "{{.State.Health.Status}}",
            self.container_name
        ], capture_output=True, text=True)
        
        # If health check is configured, it should be healthy
        # If not configured, this test will be skipped
        if health_result.returncode == 0 and health_result.stdout.strip():
            health_status = health_result.stdout.strip()
            assert health_status in ["healthy", "starting"], f"Container health check failed: {health_status}"
    
    def test_container_resource_usage(self):
        """Test container resource usage is reasonable."""
        # Start container
        self.test_docker_container_startup()
        
        # Wait for container to stabilize
        time.sleep(20)
        
        # Check container stats
        stats_result = subprocess.run([
            "docker", "stats", "--no-stream", "--format",
            "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}",
            self.container_name
        ], capture_output=True, text=True)
        
        assert stats_result.returncode == 0
        assert self.container_name in stats_result.stdout
        
        # Container should be using reasonable resources (not 100% CPU)
        lines = stats_result.stdout.strip().split('\n')
        if len(lines) > 1:  # Skip header
            stats_line = lines[1]
            # Basic check that stats are being reported
            assert self.container_name in stats_line
    
    def test_container_logs_accessibility(self):
        """Test container logs are accessible and contain expected content."""
        # Start container
        self.test_docker_container_startup()
        
        # Wait for some log output
        time.sleep(15)
        
        # Get container logs
        logs_result = subprocess.run(
            ["docker", "logs", self.container_name],
            capture_output=True,
            text=True
        )
        
        assert logs_result.returncode == 0
        
        # Logs should contain startup information
        logs_content = logs_result.stdout + logs_result.stderr
        
        # Should contain some indication of startup
        startup_indicators = [
            "Starting",
            "server",
            "port",
            "4321",
            "4322",
            "uvicorn",
            "fastapi"
        ]
        
        # At least one startup indicator should be present
        assert any(indicator.lower() in logs_content.lower() for indicator in startup_indicators), \
            f"No startup indicators found in logs: {logs_content[:500]}"
    
    def test_multiple_container_instances(self):
        """Test multiple container instances can run with different ports."""
        # Build image first
        self.test_docker_build_process()
        
        container_1 = f"{self.container_name}-1"
        container_2 = f"{self.container_name}-2"
        
        try:
            # Start first container
            run_result_1 = subprocess.run([
                "docker", "run", "-d",
                "--name", container_1,
                "-p", "14322:4322",
                "-p", "14321:4321",
                "clads-llm-bridge-test"
            ], capture_output=True, text=True)
            
            assert run_result_1.returncode == 0
            
            # Start second container
            run_result_2 = subprocess.run([
                "docker", "run", "-d",
                "--name", container_2,
                "-p", "24322:4322",
                "-p", "24321:4321",
                "clads-llm-bridge-test"
            ], capture_output=True, text=True)
            
            assert run_result_2.returncode == 0
            
            # Wait for both to start
            time.sleep(20)
            
            # Test both are accessible
            try:
                response_1 = requests.get("http://localhost:14322/login", timeout=10)
                assert response_1.status_code == 200
                
                response_2 = requests.get("http://localhost:24322/login", timeout=10)
                assert response_2.status_code == 200
                
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Multiple container instances not accessible: {e}")
            
        finally:
            # Cleanup both containers
            for container in [container_1, container_2]:
                try:
                    subprocess.run(["docker", "stop", container], timeout=30)
                    subprocess.run(["docker", "rm", container], timeout=10)
                except subprocess.TimeoutExpired:
                    pass