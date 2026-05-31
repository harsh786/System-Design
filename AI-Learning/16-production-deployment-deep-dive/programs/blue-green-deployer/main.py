"""
Blue-Green Deployment Simulator for AI Models
=============================================

This program simulates the blue-green deployment pattern used in production AI systems.
The core idea: maintain TWO identical environments (blue and green). At any time, one is
"live" serving traffic, the other is "idle" and available for deploying new versions.

Key production concepts demonstrated:
- Dual environment management
- Health checks before traffic switching
- Atomic traffic cutover via load balancer
- Instant rollback by switching back
- Model validation in idle environment before promotion
"""

import time
import random
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class EnvironmentStatus(Enum):
    LIVE = "LIVE"
    IDLE = "IDLE"
    DEPLOYING = "DEPLOYING"
    UNHEALTHY = "UNHEALTHY"


@dataclass
class ModelVersion:
    name: str
    version: str
    accuracy: float
    latency_ms: float
    memory_mb: int

    def __str__(self):
        return f"{self.name} v{self.version} (acc={self.accuracy:.3f}, lat={self.latency_ms:.0f}ms)"


@dataclass
class Environment:
    name: str  # "blue" or "green"
    status: EnvironmentStatus = EnvironmentStatus.IDLE
    model: Optional[ModelVersion] = None
    health_score: float = 1.0
    requests_served: int = 0
    errors: int = 0

    def serve_request(self) -> bool:
        """Simulate serving a single inference request."""
        if self.status != EnvironmentStatus.LIVE:
            return False
        self.requests_served += 1
        # Simulate occasional errors based on model quality
        if random.random() > self.model.accuracy:
            self.errors += 1
            return False
        return True

    def run_health_check(self) -> float:
        """Run health check - returns score 0.0 to 1.0."""
        if self.model is None:
            return 0.0
        # Simulate health based on model properties and some randomness
        base_health = self.model.accuracy * 0.7 + 0.3
        noise = random.uniform(-0.05, 0.05)
        self.health_score = max(0.0, min(1.0, base_health + noise))
        return self.health_score


@dataclass
class LoadBalancer:
    """Simulates a load balancer that routes traffic to one environment."""
    active_environment: Optional[str] = None
    switch_count: int = 0

    def switch_to(self, env_name: str):
        print(f"    [LoadBalancer] Switching traffic: {self.active_environment} -> {env_name}")
        self.active_environment = env_name
        self.switch_count += 1


class BlueGreenDeployer:
    """
    Orchestrates blue-green deployments for AI model serving.
    
    In production, this would coordinate with:
    - Container orchestrators (Kubernetes)
    - Load balancers (ALB/NLB, Envoy, Istio)
    - Model registries (MLflow, SageMaker Model Registry)
    - Monitoring systems (Prometheus, Datadog)
    """

    def __init__(self):
        self.blue = Environment(name="blue")
        self.green = Environment(name="green")
        self.lb = LoadBalancer()
        self.deployment_history: List[Dict] = []
        self.health_check_threshold = 0.85
        self.validation_requests = 50

    def get_live_env(self) -> Optional[Environment]:
        if self.lb.active_environment == "blue":
            return self.blue
        elif self.lb.active_environment == "green":
            return self.green
        return None

    def get_idle_env(self) -> Environment:
        if self.lb.active_environment == "blue":
            return self.green
        return self.blue

    def deploy_model(self, model: ModelVersion) -> bool:
        """
        Deploy a new model version using blue-green strategy.
        
        Steps:
        1. Deploy to IDLE environment
        2. Run health checks on idle environment
        3. Run validation traffic (shadow/synthetic requests)
        4. If healthy, switch traffic atomically
        5. Keep old environment as rollback target
        """
        print(f"\n{'='*60}")
        print(f"  DEPLOYING: {model}")
        print(f"{'='*60}")

        idle_env = self.get_idle_env()
        live_env = self.get_live_env()

        # Step 1: Deploy to idle environment
        print(f"\n  Step 1: Deploying to {idle_env.name.upper()} environment (currently idle)")
        idle_env.status = EnvironmentStatus.DEPLOYING
        time.sleep(0.3)  # Simulate deployment time
        idle_env.model = model
        print(f"    Model loaded into {idle_env.name} environment")

        # Step 2: Health checks
        print(f"\n  Step 2: Running health checks on {idle_env.name}...")
        health_scores = []
        for i in range(5):
            score = idle_env.run_health_check()
            health_scores.append(score)
            status_icon = "✓" if score >= self.health_check_threshold else "✗"
            print(f"    Health check {i+1}/5: {score:.3f} {status_icon}")
            time.sleep(0.1)

        avg_health = sum(health_scores) / len(health_scores)
        if avg_health < self.health_check_threshold:
            print(f"\n  ✗ DEPLOYMENT ABORTED: Health score {avg_health:.3f} < threshold {self.health_check_threshold}")
            idle_env.status = EnvironmentStatus.UNHEALTHY
            idle_env.model = None
            return False

        # Step 3: Validation traffic
        print(f"\n  Step 3: Sending {self.validation_requests} validation requests...")
        idle_env.status = EnvironmentStatus.LIVE  # Temporarily live for validation
        successes = 0
        for _ in range(self.validation_requests):
            if idle_env.serve_request():
                successes += 1
        success_rate = successes / self.validation_requests
        print(f"    Validation success rate: {success_rate:.1%} ({successes}/{self.validation_requests})")

        if success_rate < 0.9:
            print(f"\n  ✗ DEPLOYMENT ABORTED: Validation success rate too low")
            idle_env.status = EnvironmentStatus.IDLE
            idle_env.model = None
            return False

        # Step 4: Atomic traffic switch
        print(f"\n  Step 4: Switching traffic atomically...")
        if live_env:
            live_env.status = EnvironmentStatus.IDLE
            print(f"    {live_env.name.upper()} marked as idle (available for rollback)")
        idle_env.status = EnvironmentStatus.LIVE
        self.lb.switch_to(idle_env.name)
        print(f"    {idle_env.name.upper()} is now LIVE")

        # Record deployment
        self.deployment_history.append({
            "model": str(model),
            "environment": idle_env.name,
            "health_score": avg_health,
            "validation_rate": success_rate,
            "timestamp": time.time()
        })

        print(f"\n  ✓ DEPLOYMENT SUCCESSFUL")
        return True

    def rollback(self) -> bool:
        """
        Instant rollback by switching traffic back to previous environment.
        This is the KEY advantage of blue-green: rollback is just a LB switch.
        """
        print(f"\n{'='*60}")
        print(f"  ROLLBACK INITIATED")
        print(f"{'='*60}")

        live_env = self.get_live_env()
        idle_env = self.get_idle_env()

        if idle_env.model is None:
            print("  ✗ Cannot rollback: no previous version available")
            return False

        print(f"  Rolling back: {live_env.name} -> {idle_env.name}")
        print(f"  Previous model: {idle_env.model}")

        live_env.status = EnvironmentStatus.IDLE
        idle_env.status = EnvironmentStatus.LIVE
        self.lb.switch_to(idle_env.name)

        print(f"  ✓ ROLLBACK COMPLETE - Traffic now on {idle_env.name.upper()}")
        return True

    def simulate_traffic(self, num_requests: int):
        """Simulate production traffic hitting the live environment."""
        live_env = self.get_live_env()
        if not live_env:
            print("  No live environment to serve traffic!")
            return

        print(f"\n  Simulating {num_requests} production requests on {live_env.name.upper()}...")
        successes = 0
        for _ in range(num_requests):
            if live_env.serve_request():
                successes += 1
        print(f"    Results: {successes}/{num_requests} successful ({successes/num_requests:.1%})")

    def print_status(self):
        """Print current state of both environments."""
        print(f"\n  {'─'*50}")
        print(f"  Environment Status:")
        for env in [self.blue, self.green]:
            model_str = str(env.model) if env.model else "No model"
            arrow = " ◄── TRAFFIC" if env.status == EnvironmentStatus.LIVE else ""
            print(f"    {env.name.upper():6} | {env.status.value:10} | {model_str}{arrow}")
        print(f"  {'─'*50}")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          BLUE-GREEN DEPLOYMENT SIMULATOR                     ║
║          For AI Model Serving Infrastructure                 ║
╠══════════════════════════════════════════════════════════════╣
║  Pattern: Maintain two identical environments.               ║
║  Deploy to idle, validate, then switch traffic atomically.   ║
║  Rollback = just switch back. Near-zero downtime.            ║
╚══════════════════════════════════════════════════════════════╝
""")

    deployer = BlueGreenDeployer()

    # Define model versions to deploy
    models = [
        ModelVersion("sentiment-bert", "1.0.0", accuracy=0.92, latency_ms=45, memory_mb=2048),
        ModelVersion("sentiment-bert", "1.1.0", accuracy=0.95, latency_ms=42, memory_mb=2048),
        ModelVersion("sentiment-bert", "1.2.0", accuracy=0.55, latency_ms=80, memory_mb=4096),  # Bad version!
        ModelVersion("sentiment-bert", "1.1.1", accuracy=0.96, latency_ms=40, memory_mb=2048),  # Hotfix
    ]

    # --- Scenario 1: Initial deployment ---
    print("\n" + "━"*60)
    print("  SCENARIO 1: Initial deployment of v1.0.0")
    print("━"*60)
    deployer.deploy_model(models[0])
    deployer.print_status()
    deployer.simulate_traffic(100)

    # --- Scenario 2: Upgrade to v1.1.0 ---
    print("\n" + "━"*60)
    print("  SCENARIO 2: Upgrading to v1.1.0 (improved accuracy)")
    print("━"*60)
    deployer.deploy_model(models[1])
    deployer.print_status()
    deployer.simulate_traffic(100)

    # --- Scenario 3: Bad deployment (v1.2.0 has poor accuracy) ---
    print("\n" + "━"*60)
    print("  SCENARIO 3: Deploying v1.2.0 (this version is BAD)")
    print("━"*60)
    result = deployer.deploy_model(models[2])
    if not result:
        print("\n  The deployment system caught the bad model BEFORE it reached users!")
        print("  This is why we validate in the idle environment first.")
    deployer.print_status()

    # --- Scenario 4: Deploy hotfix ---
    print("\n" + "━"*60)
    print("  SCENARIO 4: Deploying hotfix v1.1.1")
    print("━"*60)
    deployer.deploy_model(models[3])
    deployer.print_status()
    deployer.simulate_traffic(100)

    # --- Scenario 5: Rollback demonstration ---
    print("\n" + "━"*60)
    print("  SCENARIO 5: Simulating need for rollback")
    print("━"*60)
    print("  Imagine we detect issues in production monitoring...")
    deployer.rollback()
    deployer.print_status()

    # --- Summary ---
    print(f"""
{'━'*60}
  DEPLOYMENT HISTORY
{'━'*60}""")
    for i, dep in enumerate(deployer.deployment_history, 1):
        print(f"  {i}. {dep['model']} -> {dep['environment']} (health={dep['health_score']:.3f})")

    print(f"""
{'━'*60}
  KEY TAKEAWAYS
{'━'*60}
  1. Blue-green gives you INSTANT rollback (just a LB switch)
  2. New versions are validated BEFORE receiving real traffic
  3. You need 2x the infrastructure (cost tradeoff for safety)
  4. The "idle" environment can be used for pre-production testing
  5. Atomic switchover means users never see partial deployments
  6. For AI models specifically:
     - Validate accuracy/latency in idle env with shadow traffic
     - Health checks should include model-specific metrics
     - Memory requirements may differ between versions
     
  In production, this pattern is implemented with:
  - Kubernetes Deployments with service switching
  - AWS CodeDeploy with Blue/Green configuration
  - Istio/Envoy for traffic management
  - CloudFront/ALB weighted target groups
{'━'*60}
""")


if __name__ == "__main__":
    main()
