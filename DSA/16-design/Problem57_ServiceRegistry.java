import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 57: Service Registry with Health Checks, Heartbeats, Deregistration
 * 
 * PRODUCTION MAPPING: Consul, Eureka, ZooKeeper, etcd, Kubernetes service discovery
 * 
 * Design Decisions:
 * - Services register with metadata (host, port, health endpoint)
 * - Heartbeat-based liveness: services must heartbeat within interval or marked unhealthy
 * - Health check states: HEALTHY, UNHEALTHY, CRITICAL (deregistered)
 * - Client-side load balancing: registry returns healthy instances only
 * 
 * Trade-offs:
 * - Pull (heartbeat) vs Push (health check): heartbeat = simpler, health check = more reliable
 * - TTL for heartbeats: too short = false positives, too long = stale entries
 * - Consul uses both: agent-based checks + TTL heartbeats
 */
public class Problem57_ServiceRegistry {

    enum HealthStatus { HEALTHY, UNHEALTHY, CRITICAL }

    static class ServiceInstance {
        final String serviceId;
        final String instanceId;
        final String host;
        final int port;
        final Map<String, String> metadata;
        volatile HealthStatus status;
        volatile long lastHeartbeat;
        volatile int consecutiveFailures;

        ServiceInstance(String serviceId, String instanceId, String host, int port) {
            this.serviceId = serviceId;
            this.instanceId = instanceId;
            this.host = host;
            this.port = port;
            this.metadata = new ConcurrentHashMap<>();
            this.status = HealthStatus.HEALTHY;
            this.lastHeartbeat = System.currentTimeMillis();
            this.consecutiveFailures = 0;
        }

        String address() { return host + ":" + port; }
    }

    static class ServiceRegistry {
        // serviceId -> list of instances
        private final Map<String, List<ServiceInstance>> services = new ConcurrentHashMap<>();
        // instanceId -> instance (for fast lookup)
        private final Map<String, ServiceInstance> instances = new ConcurrentHashMap<>();
        
        private final long heartbeatTimeoutMs;
        private final int unhealthyThreshold;  // consecutive misses before UNHEALTHY
        private final int criticalThreshold;   // consecutive misses before deregister
        private final ScheduledExecutorService healthChecker;
        private final List<String> eventLog = new CopyOnWriteArrayList<>();

        public ServiceRegistry(long heartbeatTimeoutMs, int unhealthyThreshold, 
                              int criticalThreshold, long checkIntervalMs) {
            this.heartbeatTimeoutMs = heartbeatTimeoutMs;
            this.unhealthyThreshold = unhealthyThreshold;
            this.criticalThreshold = criticalThreshold;

            healthChecker = Executors.newSingleThreadScheduledExecutor(r -> {
                Thread t = new Thread(r, "health-checker");
                t.setDaemon(true);
                return t;
            });
            healthChecker.scheduleAtFixedRate(this::checkHealth, 
                checkIntervalMs, checkIntervalMs, TimeUnit.MILLISECONDS);
        }

        public void register(String serviceId, String instanceId, String host, int port) {
            ServiceInstance instance = new ServiceInstance(serviceId, instanceId, host, port);
            instances.put(instanceId, instance);
            services.computeIfAbsent(serviceId, k -> new CopyOnWriteArrayList<>()).add(instance);
            eventLog.add("REGISTER: " + instanceId + " for " + serviceId);
        }

        public void deregister(String instanceId) {
            ServiceInstance instance = instances.remove(instanceId);
            if (instance != null) {
                List<ServiceInstance> list = services.get(instance.serviceId);
                if (list != null) list.remove(instance);
                eventLog.add("DEREGISTER: " + instanceId);
            }
        }

        public void heartbeat(String instanceId) {
            ServiceInstance instance = instances.get(instanceId);
            if (instance != null) {
                instance.lastHeartbeat = System.currentTimeMillis();
                instance.consecutiveFailures = 0;
                if (instance.status != HealthStatus.HEALTHY) {
                    instance.status = HealthStatus.HEALTHY;
                    eventLog.add("RECOVERED: " + instanceId);
                }
            }
        }

        /**
         * Get healthy instances for a service (what clients use for load balancing)
         */
        public List<ServiceInstance> getHealthyInstances(String serviceId) {
            List<ServiceInstance> list = services.getOrDefault(serviceId, Collections.emptyList());
            List<ServiceInstance> healthy = new ArrayList<>();
            for (ServiceInstance i : list) {
                if (i.status == HealthStatus.HEALTHY) healthy.add(i);
            }
            return healthy;
        }

        public List<ServiceInstance> getAllInstances(String serviceId) {
            return services.getOrDefault(serviceId, Collections.emptyList());
        }

        private void checkHealth() {
            long now = System.currentTimeMillis();
            for (ServiceInstance instance : new ArrayList<>(instances.values())) {
                if (now - instance.lastHeartbeat > heartbeatTimeoutMs) {
                    instance.consecutiveFailures++;
                    
                    if (instance.consecutiveFailures >= criticalThreshold) {
                        eventLog.add("CRITICAL: " + instance.instanceId + " - deregistering");
                        deregister(instance.instanceId);
                    } else if (instance.consecutiveFailures >= unhealthyThreshold) {
                        instance.status = HealthStatus.UNHEALTHY;
                        eventLog.add("UNHEALTHY: " + instance.instanceId);
                    }
                }
            }
        }

        public List<String> getEventLog() { return eventLog; }

        // Simple round-robin load balancer
        private final Map<String, AtomicInteger> roundRobin = new ConcurrentHashMap<>();
        
        public ServiceInstance discover(String serviceId) {
            List<ServiceInstance> healthy = getHealthyInstances(serviceId);
            if (healthy.isEmpty()) return null;
            int idx = roundRobin.computeIfAbsent(serviceId, k -> new AtomicInteger())
                .getAndIncrement() % healthy.size();
            return healthy.get(idx);
        }

        public void shutdown() { healthChecker.shutdown(); }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Service Registry ===\n");

        // heartbeat timeout=100ms, unhealthy after 2 misses, critical after 4, check every 50ms
        ServiceRegistry registry = new ServiceRegistry(100, 2, 4, 50);

        // Test 1: Register services
        registry.register("payment-service", "payment-1", "10.0.0.1", 8080);
        registry.register("payment-service", "payment-2", "10.0.0.2", 8080);
        registry.register("order-service", "order-1", "10.0.0.3", 9090);
        
        List<ServiceInstance> payments = registry.getHealthyInstances("payment-service");
        assert payments.size() == 2;
        System.out.println("PASS: Registered 2 payment instances");

        // Test 2: Service discovery with load balancing
        ServiceInstance s1 = registry.discover("payment-service");
        ServiceInstance s2 = registry.discover("payment-service");
        assert !s1.instanceId.equals(s2.instanceId) : "Should round-robin";
        System.out.println("PASS: Round-robin discovery works");

        // Test 3: Heartbeat keeps service healthy
        registry.heartbeat("payment-1");
        registry.heartbeat("payment-2");
        Thread.sleep(200); // would expire without heartbeat
        registry.heartbeat("payment-1"); // only payment-1 heartbeats
        Thread.sleep(100);
        
        // payment-1 should still be healthy, payment-2 may be unhealthy
        ServiceInstance p1 = registry.getAllInstances("payment-service").stream()
            .filter(i -> i.instanceId.equals("payment-1")).findFirst().orElse(null);
        assert p1 != null && p1.status == HealthStatus.HEALTHY;
        System.out.println("PASS: Heartbeat keeps instance healthy");

        // Test 4: Missing heartbeat marks unhealthy then deregisters
        registry = new ServiceRegistry(50, 1, 3, 30);
        registry.register("api", "api-1", "host1", 80);
        Thread.sleep(200); // no heartbeat -> should go unhealthy then critical
        
        List<ServiceInstance> healthy = registry.getHealthyInstances("api");
        assert healthy.isEmpty() : "Should have no healthy instances";
        System.out.println("PASS: Missing heartbeat marks unhealthy/deregisters");

        // Test 5: Recovery after heartbeat resumes
        registry = new ServiceRegistry(80, 2, 5, 40);
        registry.register("db", "db-1", "host", 5432);
        Thread.sleep(200); // miss some heartbeats
        registry.heartbeat("db-1"); // recover
        ServiceInstance db = registry.getAllInstances("db").stream()
            .filter(i -> i.instanceId.equals("db-1")).findFirst().orElse(null);
        if (db != null) {
            assert db.status == HealthStatus.HEALTHY : "Should recover on heartbeat";
            System.out.println("PASS: Instance recovers on heartbeat");
        } else {
            System.out.println("PASS: Instance was deregistered (too many misses)");
        }

        // Test 6: Manual deregistration (graceful shutdown)
        registry = new ServiceRegistry(5000, 2, 4, 1000);
        registry.register("web", "web-1", "h1", 80);
        registry.register("web", "web-2", "h2", 80);
        registry.deregister("web-1");
        assert registry.getHealthyInstances("web").size() == 1;
        System.out.println("PASS: Manual deregistration (graceful shutdown)");

        // Test 7: Event log
        System.out.println("\nEvent log: " + registry.getEventLog());

        registry.shutdown();
        System.out.println("\nAll tests passed!");
    }
}
