import java.util.*;

/**
 * Problem 65: Cache Invalidation Dependency Graph
 * 
 * Production Relevance:
 * - "Cache invalidation is one of the two hard problems in CS"
 * - When entity X changes, all cached views derived from X must be invalidated
 * - Used in CDN purging, ORM cache (Hibernate L2), materialized view refresh
 * - Graph tracks: which caches depend on which source data
 * 
 * Architect Considerations:
 * - Transitive invalidation: A depends on B depends on C; C changes -> invalidate A,B
 * - Batch invalidation to avoid thundering herd
 * - TTL as fallback for missed invalidations
 * - Versioned caching: stale-while-revalidate pattern
 */
public class Problem65_CacheInvalidationDependencyGraph {

    static class CacheEntry {
        String key;
        String value;
        long version;
        long ttlMs;
        long createdAt;
        Set<String> dependsOn = new HashSet<>(); // source data keys

        CacheEntry(String key, String value, long version, long ttlMs, String... deps) {
            this.key = key; this.value = value; this.version = version;
            this.ttlMs = ttlMs; this.createdAt = System.currentTimeMillis();
            this.dependsOn.addAll(Arrays.asList(deps));
        }

        boolean isExpired(long now) { return now - createdAt > ttlMs; }
    }

    static class CacheInvalidationGraph {
        Map<String, CacheEntry> cache = new LinkedHashMap<>();
        // Reverse index: source -> set of cache keys that depend on it
        Map<String, Set<String>> dependencyIndex = new HashMap<>();
        List<String> invalidationLog = new ArrayList<>();
        int invalidationCount = 0;

        void put(CacheEntry entry) {
            cache.put(entry.key, entry);
            for (String dep : entry.dependsOn) {
                dependencyIndex.computeIfAbsent(dep, k -> new HashSet<>()).add(entry.key);
            }
        }

        CacheEntry get(String key) { return cache.get(key); }

        // Invalidate all caches affected by source data change
        Set<String> invalidate(String sourceKey) {
            Set<String> invalidated = new LinkedHashSet<>();
            Queue<String> queue = new LinkedList<>();
            queue.offer(sourceKey);

            while (!queue.isEmpty()) {
                String key = queue.poll();
                Set<String> dependents = dependencyIndex.getOrDefault(key, Set.of());
                for (String dep : dependents) {
                    if (invalidated.add(dep)) {
                        cache.remove(dep);
                        invalidationCount++;
                        invalidationLog.add("INVALIDATE: " + dep + " (caused by: " + sourceKey + ")");
                        // Transitive: this cache may be a dependency of other caches
                        queue.offer(dep);
                    }
                }
            }

            // Clean up dependency index
            for (String inv : invalidated) {
                dependencyIndex.values().forEach(s -> s.remove(inv));
            }
            return invalidated;
        }

        // Batch invalidation with deduplication (avoid thundering herd)
        Map<String, Set<String>> planBatchInvalidation(List<String> changedSources) {
            Map<String, Set<String>> plan = new LinkedHashMap<>();
            Set<String> allInvalidated = new HashSet<>();
            for (String source : changedSources) {
                Set<String> affected = new HashSet<>();
                Queue<String> q = new LinkedList<>();
                q.offer(source);
                while (!q.isEmpty()) {
                    String key = q.poll();
                    for (String dep : dependencyIndex.getOrDefault(key, Set.of())) {
                        if (allInvalidated.add(dep)) {
                            affected.add(dep);
                            q.offer(dep);
                        }
                    }
                }
                if (!affected.isEmpty()) plan.put(source, affected);
            }
            return plan;
        }

        int size() { return cache.size(); }
    }

    public static void main(String[] args) {
        System.out.println("=== Cache Invalidation Dependency Graph ===\n");

        CacheInvalidationGraph graph = new CacheInvalidationGraph();

        // Source data: users, products
        // Derived caches depend on source data
        graph.put(new CacheEntry("user:1:profile", "{name:Alice}", 1, 60000, "user:1"));
        graph.put(new CacheEntry("user:1:dashboard", "{stats:...}", 1, 60000, "user:1", "orders:user1"));
        graph.put(new CacheEntry("product:1:detail", "{name:Widget}", 1, 60000, "product:1"));
        graph.put(new CacheEntry("homepage:featured", "{products:[...]}", 1, 30000, "product:1", "product:2"));
        graph.put(new CacheEntry("user:1:recommendations", "{recs:[...]}", 1, 60000, "user:1", "product:1"));

        System.out.println("Cache entries: " + graph.size());

        // User 1 updates their profile
        System.out.println("\n--- user:1 data changes ---");
        Set<String> invalidated = graph.invalidate("user:1");
        System.out.println("Invalidated: " + invalidated);
        System.out.println("Cache entries remaining: " + graph.size());

        // Batch invalidation planning
        graph.put(new CacheEntry("user:1:profile", "{name:Alice2}", 2, 60000, "user:1"));
        graph.put(new CacheEntry("product:1:detail", "{name:Widget2}", 2, 60000, "product:1"));
        graph.put(new CacheEntry("homepage:featured", "{v2}", 2, 30000, "product:1"));

        System.out.println("\n--- Batch invalidation plan for [product:1, product:2] ---");
        Map<String, Set<String>> plan = graph.planBatchInvalidation(List.of("product:1", "product:2"));
        plan.forEach((source, affected) -> System.out.printf("  %s -> %s%n", source, affected));

        System.out.println("\nTotal invalidations: " + graph.invalidationCount);
    }
}
