"""
Production Deployment Manager for AI Systems

Handles canary deployments, progressive rollouts, metrics-based promotion/rollback,
prompt versioning, model version management, and feature flag integration.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import httpx
from kubernetes import client, config
from prometheus_api_client import PrometheusConnect

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

class DeploymentState(Enum):
    PENDING = "pending"
    CANARY_1_PERCENT = "canary_1_percent"
    CANARY_5_PERCENT = "canary_5_percent"
    CANARY_25_PERCENT = "canary_25_percent"
    FULL_ROLLOUT = "full_rollout"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class ComponentType(Enum):
    ORCHESTRATOR = "agent-orchestrator"
    RETRIEVAL = "retrieval-service"
    AI_GATEWAY = "ai-gateway"
    GUARDRAIL = "guardrail-service"
    PROMPT = "prompt"
    MODEL = "model"
    RETRIEVER_COLLECTION = "retriever-collection"


@dataclass
class DeploymentMetrics:
    """Metrics collected during canary observation."""
    error_rate: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    quality_score: float = 1.0
    guardrail_trigger_rate: float = 0.0
    token_cost_per_request: float = 0.0
    user_feedback_score: float = 1.0
    requests_total: int = 0
    errors_total: int = 0


@dataclass
class RolloutStage:
    """Definition of a rollout stage."""
    name: str
    traffic_percent: int
    duration_minutes: int
    min_requests: int = 100
    state: DeploymentState = DeploymentState.PENDING


@dataclass
class DeploymentBundle:
    """A versioned bundle of all AI components deployed together."""
    bundle_id: str
    version: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    components: dict[str, str] = field(default_factory=dict)
    # e.g., {"orchestrator": "v2.4.0", "prompt": "v6", "model": "gpt-4o-2024-08-06",
    #         "retriever_collection": "docs_v3"}
    state: DeploymentState = DeploymentState.PENDING
    metrics: Optional[DeploymentMetrics] = None


@dataclass
class RollbackThresholds:
    """Thresholds that trigger automatic rollback."""
    max_error_rate: float = 0.05
    max_p95_latency_ms: float = 10000.0
    min_quality_score: float = 0.80
    max_guardrail_trigger_rate: float = 0.10
    max_cost_increase_percent: float = 50.0
    min_user_feedback_score: float = 0.70


# =============================================================================
# METRICS COLLECTOR
# =============================================================================

class MetricsCollector:
    """Collects deployment metrics from Prometheus."""

    def __init__(self, prometheus_url: str):
        self.prom = PrometheusConnect(url=prometheus_url, disable_ssl=False)

    async def collect_metrics(
        self,
        track: str = "canary",
        namespace: str = "ai-production",
        window_minutes: int = 15,
    ) -> DeploymentMetrics:
        """Collect metrics for a deployment track (canary or stable)."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=window_minutes)
        duration = f"{window_minutes}m"

        metrics = DeploymentMetrics()

        # Error rate
        error_query = f"""
            sum(rate(http_requests_total{{
                namespace="{namespace}",
                track="{track}",
                status=~"5.."
            }}[{duration}])) /
            sum(rate(http_requests_total{{
                namespace="{namespace}",
                track="{track}"
            }}[{duration}]))
        """
        result = self.prom.custom_query(error_query)
        if result:
            metrics.error_rate = float(result[0]["value"][1])

        # Latency percentiles
        for percentile, field_name in [
            (0.50, "p50_latency_ms"),
            (0.95, "p95_latency_ms"),
            (0.99, "p99_latency_ms"),
        ]:
            latency_query = f"""
                histogram_quantile({percentile},
                    sum(rate(http_request_duration_seconds_bucket{{
                        namespace="{namespace}",
                        track="{track}"
                    }}[{duration}])) by (le)
                ) * 1000
            """
            result = self.prom.custom_query(latency_query)
            if result:
                setattr(metrics, field_name, float(result[0]["value"][1]))

        # Quality score (from eval service)
        quality_query = f"""
            avg(ai_response_quality_score{{
                namespace="{namespace}",
                track="{track}"
            }}[{duration}])
        """
        result = self.prom.custom_query(quality_query)
        if result:
            metrics.quality_score = float(result[0]["value"][1])

        # Guardrail trigger rate
        guardrail_query = f"""
            sum(rate(guardrail_blocks_total{{
                namespace="{namespace}",
                track="{track}"
            }}[{duration}])) /
            sum(rate(guardrail_checks_total{{
                namespace="{namespace}",
                track="{track}"
            }}[{duration}]))
        """
        result = self.prom.custom_query(guardrail_query)
        if result:
            metrics.guardrail_trigger_rate = float(result[0]["value"][1])

        # Request count
        count_query = f"""
            sum(increase(http_requests_total{{
                namespace="{namespace}",
                track="{track}"
            }}[{duration}]))
        """
        result = self.prom.custom_query(count_query)
        if result:
            metrics.requests_total = int(float(result[0]["value"][1]))

        return metrics


# =============================================================================
# CANARY DEPLOYMENT CONTROLLER
# =============================================================================

class CanaryDeploymentController:
    """
    Manages progressive canary rollouts with automatic promotion/rollback.
    
    Rollout stages:
    1. 1% traffic for 15 minutes (smoke test)
    2. 5% traffic for 30 minutes (initial validation)
    3. 25% traffic for 60 minutes (confidence building)
    4. 100% traffic (full rollout)
    """

    DEFAULT_STAGES = [
        RolloutStage("smoke", 1, 15, min_requests=50),
        RolloutStage("initial", 5, 30, min_requests=200),
        RolloutStage("confidence", 25, 60, min_requests=1000),
        RolloutStage("full", 100, 0, min_requests=0),
    ]

    def __init__(
        self,
        namespace: str = "ai-production",
        prometheus_url: str = "http://prometheus.observability.svc:9090",
        kubeconfig: Optional[str] = None,
        stages: Optional[list[RolloutStage]] = None,
        thresholds: Optional[RollbackThresholds] = None,
    ):
        self.namespace = namespace
        self.metrics_collector = MetricsCollector(prometheus_url)
        self.thresholds = thresholds or RollbackThresholds()
        self.stages = stages or self.DEFAULT_STAGES

        # Initialize Kubernetes client
        if kubeconfig:
            config.load_kube_config(kubeconfig)
        else:
            config.load_incluster_config()
        self.apps_v1 = client.AppsV1Api()
        self.networking_v1 = client.CustomObjectsApi()

    async def execute_rollout(self, bundle: DeploymentBundle) -> DeploymentBundle:
        """Execute a full progressive rollout."""
        logger.info(f"Starting rollout for bundle {bundle.bundle_id} (v{bundle.version})")

        for i, stage in enumerate(self.stages):
            logger.info(f"Stage {i+1}/{len(self.stages)}: {stage.name} ({stage.traffic_percent}%)")

            # Set traffic weight
            await self._set_traffic_weight(stage.traffic_percent)
            bundle.state = self._state_for_percent(stage.traffic_percent)

            if stage.duration_minutes == 0:
                # Final stage - no observation needed
                break

            # Observe metrics during stage duration
            passed = await self._observe_stage(stage)

            if not passed:
                logger.error(f"Stage {stage.name} failed metrics check. Rolling back.")
                await self._rollback(bundle)
                bundle.state = DeploymentState.ROLLED_BACK
                return bundle

            logger.info(f"Stage {stage.name} passed. Promoting to next stage.")

        bundle.state = DeploymentState.FULL_ROLLOUT
        logger.info(f"Rollout complete for bundle {bundle.bundle_id}")
        return bundle

    async def _observe_stage(self, stage: RolloutStage) -> bool:
        """Observe metrics during a stage and decide pass/fail."""
        check_interval = 60  # Check every 60 seconds
        elapsed = 0
        total_duration = stage.duration_minutes * 60

        while elapsed < total_duration:
            await asyncio.sleep(check_interval)
            elapsed += check_interval

            # Collect metrics
            canary_metrics = await self.metrics_collector.collect_metrics(
                track="canary", window_minutes=5
            )
            stable_metrics = await self.metrics_collector.collect_metrics(
                track="stable", window_minutes=5
            )

            # Check thresholds
            if not self._check_thresholds(canary_metrics, stable_metrics):
                return False

            # Check minimum requests
            if elapsed > total_duration / 2 and canary_metrics.requests_total < stage.min_requests / 2:
                logger.warning(f"Low traffic on canary: {canary_metrics.requests_total} requests")

            logger.info(
                f"  [{elapsed}s/{total_duration}s] "
                f"error_rate={canary_metrics.error_rate:.4f} "
                f"p95={canary_metrics.p95_latency_ms:.0f}ms "
                f"quality={canary_metrics.quality_score:.3f}"
            )

        # Final check with full window
        final_metrics = await self.metrics_collector.collect_metrics(
            track="canary", window_minutes=stage.duration_minutes
        )
        return self._check_thresholds(final_metrics)

    def _check_thresholds(
        self,
        canary: DeploymentMetrics,
        stable: Optional[DeploymentMetrics] = None,
    ) -> bool:
        """Check if canary metrics are within acceptable thresholds."""
        t = self.thresholds

        if canary.error_rate > t.max_error_rate:
            logger.error(f"Error rate {canary.error_rate:.4f} exceeds threshold {t.max_error_rate}")
            return False

        if canary.p95_latency_ms > t.max_p95_latency_ms:
            logger.error(f"P95 latency {canary.p95_latency_ms:.0f}ms exceeds threshold {t.max_p95_latency_ms}")
            return False

        if canary.quality_score < t.min_quality_score:
            logger.error(f"Quality score {canary.quality_score:.3f} below threshold {t.min_quality_score}")
            return False

        if canary.guardrail_trigger_rate > t.max_guardrail_trigger_rate:
            logger.error(f"Guardrail rate {canary.guardrail_trigger_rate:.4f} exceeds threshold")
            return False

        # Compare with stable if available
        if stable and stable.p95_latency_ms > 0:
            latency_increase = (canary.p95_latency_ms - stable.p95_latency_ms) / stable.p95_latency_ms
            if latency_increase > 0.5:  # 50% increase
                logger.error(f"Latency regression: {latency_increase:.1%} increase vs stable")
                return False

        return True

    async def _set_traffic_weight(self, canary_percent: int):
        """Update HTTPRoute traffic weights."""
        stable_percent = 100 - canary_percent
        patch = [
            {"op": "replace", "path": "/spec/rules/0/backendRefs/0/weight", "value": stable_percent},
            {"op": "replace", "path": "/spec/rules/0/backendRefs/1/weight", "value": canary_percent},
        ]
        self.networking_v1.patch_namespaced_custom_object(
            group="gateway.networking.k8s.io",
            version="v1",
            namespace=self.namespace,
            plural="httproutes",
            name="ai-platform-routes",
            body=patch,
        )
        logger.info(f"Traffic weights: stable={stable_percent}%, canary={canary_percent}%")

    async def _rollback(self, bundle: DeploymentBundle):
        """Rollback canary deployment."""
        await self._set_traffic_weight(0)
        # Scale down canary
        self.apps_v1.patch_namespaced_deployment_scale(
            name="agent-orchestrator-canary",
            namespace=self.namespace,
            body={"spec": {"replicas": 0}},
        )
        logger.info(f"Rolled back bundle {bundle.bundle_id}")

    def _state_for_percent(self, percent: int) -> DeploymentState:
        mapping = {
            1: DeploymentState.CANARY_1_PERCENT,
            5: DeploymentState.CANARY_5_PERCENT,
            25: DeploymentState.CANARY_25_PERCENT,
            100: DeploymentState.FULL_ROLLOUT,
        }
        return mapping.get(percent, DeploymentState.PENDING)


# =============================================================================
# PROMPT VERSION MANAGER
# =============================================================================

class PromptVersionManager:
    """
    Manages prompt versions as ConfigMaps in Kubernetes.
    Supports instant rollback by switching ConfigMap versions.
    """

    def __init__(self, namespace: str = "ai-production"):
        self.namespace = namespace
        config.load_incluster_config()
        self.core_v1 = client.CoreV1Api()

    def deploy_prompt_version(self, version: str, prompts: dict[str, str]) -> str:
        """Deploy a new prompt version as a ConfigMap."""
        configmap_name = f"prompt-configs-v{version}"

        configmap = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(
                name=configmap_name,
                namespace=self.namespace,
                labels={
                    "app.kubernetes.io/component": "prompts",
                    "version": version,
                },
                annotations={
                    "deployed-at": datetime.utcnow().isoformat(),
                    "deployed-by": "deployment-manager",
                },
            ),
            data=prompts,
        )

        try:
            self.core_v1.create_namespaced_config_map(self.namespace, configmap)
        except client.exceptions.ApiException as e:
            if e.status == 409:  # Already exists
                self.core_v1.replace_namespaced_config_map(
                    configmap_name, self.namespace, configmap
                )
            else:
                raise

        logger.info(f"Deployed prompt version {version}")
        return configmap_name

    def activate_prompt_version(self, version: str, deployments: list[str]):
        """Switch active prompt version for given deployments (hot-reload via ConfigMap swap)."""
        configmap_name = f"prompt-configs-v{version}"

        # Verify ConfigMap exists
        self.core_v1.read_namespaced_config_map(configmap_name, self.namespace)

        # Update the canonical 'prompt-configs' ConfigMap reference
        # This triggers a rolling update in pods watching this ConfigMap
        for deployment_name in deployments:
            patch = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "prompt-version": version,
                                "prompt-updated-at": datetime.utcnow().isoformat(),
                            }
                        },
                        "spec": {
                            "volumes": [
                                {
                                    "name": "prompts",
                                    "configMap": {"name": configmap_name},
                                }
                            ]
                        },
                    }
                }
            }
            apps_v1 = client.AppsV1Api()
            apps_v1.patch_namespaced_deployment(
                deployment_name, self.namespace, patch
            )

        logger.info(f"Activated prompt version {version} for {deployments}")

    def rollback_prompt(self, target_version: str, deployments: list[str]):
        """Rollback to a previous prompt version."""
        logger.info(f"Rolling back prompts to version {target_version}")
        self.activate_prompt_version(target_version, deployments)

    def list_prompt_versions(self) -> list[dict[str, Any]]:
        """List all available prompt versions."""
        configmaps = self.core_v1.list_namespaced_config_map(
            self.namespace,
            label_selector="app.kubernetes.io/component=prompts",
        )
        versions = []
        for cm in configmaps.items:
            versions.append({
                "name": cm.metadata.name,
                "version": cm.metadata.labels.get("version", "unknown"),
                "created": cm.metadata.creation_timestamp.isoformat(),
                "keys": list(cm.data.keys()) if cm.data else [],
            })
        return sorted(versions, key=lambda x: x["created"], reverse=True)


# =============================================================================
# MODEL VERSION MANAGER
# =============================================================================

class ModelVersionManager:
    """
    Manages model versions via AI Gateway configuration.
    Supports A/B testing between model versions.
    """

    def __init__(self, ai_gateway_url: str = "http://ai-gateway.ai-production.svc"):
        self.gateway_url = ai_gateway_url

    async def get_current_model_config(self) -> dict:
        """Get current model routing configuration."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.gateway_url}/admin/config")
            response.raise_for_status()
            return response.json()

    async def update_model_routing(self, config: dict):
        """Update model routing configuration."""
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.gateway_url}/admin/config",
                json=config,
            )
            response.raise_for_status()
        logger.info(f"Updated model routing: {config}")

    async def set_primary_model(self, model: str, fallbacks: list[str]):
        """Set the primary model with fallback chain."""
        config = {
            "primary": model,
            "fallbacks": fallbacks,
            "routing_strategy": "primary_with_fallback",
        }
        await self.update_model_routing(config)

    async def set_ab_test(self, model_a: str, model_b: str, b_percent: int = 10):
        """Set up A/B test between two models."""
        config = {
            "routing_strategy": "weighted",
            "routes": [
                {"model": model_a, "weight": 100 - b_percent},
                {"model": model_b, "weight": b_percent},
            ],
        }
        await self.update_model_routing(config)
        logger.info(f"A/B test: {model_a} ({100-b_percent}%) vs {model_b} ({b_percent}%)")

    async def rollback_model(self, target_model: str, fallbacks: list[str]):
        """Rollback to a previous model version."""
        logger.info(f"Rolling back model to {target_model}")
        await self.set_primary_model(target_model, fallbacks)


# =============================================================================
# RETRIEVER VERSION MANAGER
# =============================================================================

class RetrieverVersionManager:
    """
    Manages vector DB collection versions for retriever rollback.
    Collections are versioned: docs_v1, docs_v2, docs_v3
    """

    def __init__(self, namespace: str = "ai-production"):
        self.namespace = namespace
        config.load_incluster_config()
        self.apps_v1 = client.AppsV1Api()

    def set_active_collection(self, collection_name: str):
        """Point retrieval service to a specific collection."""
        patch = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "retrieval-service",
                                "env": [
                                    {
                                        "name": "COLLECTION_NAME",
                                        "value": collection_name,
                                    }
                                ],
                            }
                        ]
                    },
                    "metadata": {
                        "annotations": {
                            "collection-version": collection_name,
                            "collection-updated-at": datetime.utcnow().isoformat(),
                        }
                    },
                }
            }
        }
        self.apps_v1.patch_namespaced_deployment(
            "retrieval-service", self.namespace, patch
        )
        logger.info(f"Active collection set to: {collection_name}")

    def rollback_collection(self, target_collection: str):
        """Rollback to a previous collection version."""
        logger.info(f"Rolling back retriever to collection: {target_collection}")
        self.set_active_collection(target_collection)


# =============================================================================
# FEATURE FLAG INTEGRATION
# =============================================================================

class FeatureFlagManager:
    """
    Integrates with feature flag service (LaunchDarkly/Unleash/custom)
    for controlling AI feature rollouts.
    """

    def __init__(self, feature_flag_url: str, api_key: str):
        self.url = feature_flag_url
        self.api_key = api_key

    async def get_flag(self, flag_key: str, user_context: Optional[dict] = None) -> Any:
        """Get feature flag value."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/api/flags/{flag_key}/evaluate",
                json={"context": user_context or {}},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            return response.json()["value"]

    async def set_flag(self, flag_key: str, value: Any, percentage: Optional[int] = None):
        """Update a feature flag."""
        payload: dict[str, Any] = {"value": value}
        if percentage is not None:
            payload["rollout_percentage"] = percentage

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.url}/api/flags/{flag_key}",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
        logger.info(f"Flag {flag_key} = {value} (rollout: {percentage}%)")

    async def progressive_flag_rollout(
        self,
        flag_key: str,
        value: Any,
        stages: list[int] = [1, 5, 25, 50, 100],
        stage_duration_minutes: int = 30,
    ):
        """Progressively roll out a feature flag."""
        for percentage in stages:
            await self.set_flag(flag_key, value, percentage)
            logger.info(f"Flag {flag_key} at {percentage}%")

            if percentage < 100:
                await asyncio.sleep(stage_duration_minutes * 60)


# =============================================================================
# COMPOSITE DEPLOYMENT ORCHESTRATOR
# =============================================================================

class DeploymentOrchestrator:
    """
    Orchestrates deployments across all AI components.
    Handles composite rollouts and coordinated rollbacks.
    """

    def __init__(
        self,
        namespace: str = "ai-production",
        prometheus_url: str = "http://prometheus.observability.svc:9090",
        ai_gateway_url: str = "http://ai-gateway.ai-production.svc",
        feature_flag_url: str = "http://feature-flags.ai-production.svc",
        feature_flag_key: str = "",
    ):
        self.canary_controller = CanaryDeploymentController(
            namespace=namespace,
            prometheus_url=prometheus_url,
        )
        self.prompt_manager = PromptVersionManager(namespace)
        self.model_manager = ModelVersionManager(ai_gateway_url)
        self.retriever_manager = RetrieverVersionManager(namespace)
        self.feature_flags = FeatureFlagManager(feature_flag_url, feature_flag_key)
        self.namespace = namespace
        self._deployment_history: list[DeploymentBundle] = []

    async def deploy_bundle(self, bundle: DeploymentBundle) -> DeploymentBundle:
        """
        Deploy a complete bundle with progressive rollout.
        
        Order of operations:
        1. Deploy prompt changes (ConfigMap update)
        2. Update model routing (AI Gateway config)
        3. Update retriever collection if changed
        4. Execute canary rollout for service code changes
        """
        logger.info(f"Deploying bundle {bundle.bundle_id}: {bundle.components}")

        try:
            # Step 1: Prompt deployment
            if "prompt" in bundle.components:
                prompt_version = bundle.components["prompt"]
                self.prompt_manager.activate_prompt_version(
                    prompt_version, ["agent-orchestrator", "guardrail-service"]
                )

            # Step 2: Model routing update
            if "model" in bundle.components:
                model = bundle.components["model"]
                fallbacks = bundle.components.get("model_fallbacks", ["gpt-4", "claude-3-sonnet"])
                await self.model_manager.set_primary_model(model, fallbacks)

            # Step 3: Retriever collection update
            if "retriever_collection" in bundle.components:
                collection = bundle.components["retriever_collection"]
                self.retriever_manager.set_active_collection(collection)

            # Step 4: Service code canary rollout
            if "orchestrator" in bundle.components:
                bundle = await self.canary_controller.execute_rollout(bundle)

            # Record deployment
            self._deployment_history.append(bundle)
            return bundle

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            await self.rollback_bundle(bundle)
            bundle.state = DeploymentState.FAILED
            return bundle

    async def rollback_bundle(self, failed_bundle: DeploymentBundle):
        """Rollback to the last successful deployment bundle."""
        # Find last successful bundle
        previous = None
        for b in reversed(self._deployment_history):
            if b.state == DeploymentState.FULL_ROLLOUT and b.bundle_id != failed_bundle.bundle_id:
                previous = b
                break

        if not previous:
            logger.error("No previous successful bundle to rollback to!")
            return

        logger.info(f"Rolling back to bundle {previous.bundle_id}")

        # Rollback each component
        if "prompt" in previous.components:
            self.prompt_manager.rollback_prompt(
                previous.components["prompt"],
                ["agent-orchestrator", "guardrail-service"],
            )

        if "model" in previous.components:
            await self.model_manager.rollback_model(
                previous.components["model"],
                previous.components.get("model_fallbacks", []),
            )

        if "retriever_collection" in previous.components:
            self.retriever_manager.rollback_collection(
                previous.components["retriever_collection"]
            )

        # Rollback canary traffic
        await self.canary_controller._set_traffic_weight(0)

    async def get_deployment_status(self) -> dict[str, Any]:
        """Get current deployment status across all components."""
        prompt_versions = self.prompt_manager.list_prompt_versions()
        model_config = await self.model_manager.get_current_model_config()

        return {
            "current_bundle": self._deployment_history[-1].__dict__ if self._deployment_history else None,
            "prompt_versions": prompt_versions[:5],
            "model_config": model_config,
            "deployment_history_count": len(self._deployment_history),
        }


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================

async def main():
    """CLI for deployment management."""
    import argparse

    parser = argparse.ArgumentParser(description="AI Platform Deployment Manager")
    subparsers = parser.add_subparsers(dest="command")

    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy a bundle")
    deploy_parser.add_argument("--bundle-id", required=True)
    deploy_parser.add_argument("--version", required=True)
    deploy_parser.add_argument("--prompt-version", default=None)
    deploy_parser.add_argument("--model", default=None)
    deploy_parser.add_argument("--collection", default=None)
    deploy_parser.add_argument("--image-tag", default=None)

    # Rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Rollback deployment")
    rollback_parser.add_argument("--component", choices=["all", "prompt", "model", "retriever"])
    rollback_parser.add_argument("--target-version", required=True)

    # Status command
    subparsers.add_parser("status", help="Get deployment status")

    # Promote prompt command
    prompt_parser = subparsers.add_parser("prompt", help="Manage prompts")
    prompt_parser.add_argument("action", choices=["deploy", "activate", "rollback", "list"])
    prompt_parser.add_argument("--version", default=None)

    args = parser.parse_args()

    orchestrator = DeploymentOrchestrator(
        prometheus_url="http://prometheus.observability.svc:9090",
    )

    if args.command == "deploy":
        components = {}
        if args.prompt_version:
            components["prompt"] = args.prompt_version
        if args.model:
            components["model"] = args.model
        if args.collection:
            components["retriever_collection"] = args.collection
        if args.image_tag:
            components["orchestrator"] = args.image_tag

        bundle = DeploymentBundle(
            bundle_id=args.bundle_id,
            version=args.version,
            components=components,
        )
        result = await orchestrator.deploy_bundle(bundle)
        print(json.dumps({"state": result.state.value, "bundle_id": result.bundle_id}))

    elif args.command == "rollback":
        if args.component == "prompt":
            orchestrator.prompt_manager.rollback_prompt(
                args.target_version, ["agent-orchestrator", "guardrail-service"]
            )
        elif args.component == "model":
            await orchestrator.model_manager.rollback_model(args.target_version, [])
        elif args.component == "retriever":
            orchestrator.retriever_manager.rollback_collection(args.target_version)
        else:
            # Full rollback not implemented via CLI - use deploy with previous bundle
            print("Full rollback requires specifying a previous bundle ID")

    elif args.command == "status":
        status = await orchestrator.get_deployment_status()
        print(json.dumps(status, indent=2, default=str))

    elif args.command == "prompt":
        pm = PromptVersionManager()
        if args.action == "list":
            versions = pm.list_prompt_versions()
            print(json.dumps(versions, indent=2, default=str))
        elif args.action == "activate" and args.version:
            pm.activate_prompt_version(args.version, ["agent-orchestrator", "guardrail-service"])
            print(f"Activated prompt version {args.version}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(main())
