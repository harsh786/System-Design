import java.util.*;

/**
 * Problem 52: DNS Resolver Cache with TTL
 * 
 * Production Relevance:
 * - DNS resolvers cache responses to reduce latency and upstream load
 * - TTL (Time To Live) determines when cached entries expire
 * - Hierarchical lookup: local cache -> recursive resolver -> authoritative
 * - Used in every OS, browser, CDN edge, corporate DNS (CoreDNS, Unbound)
 * 
 * Architect Considerations:
 * - Negative caching: cache NXDOMAIN responses too (with shorter TTL)
 * - TTL enforcement: stale entries can serve wrong IPs after DNS changes
 * - Hierarchical domain structure maps naturally to trie
 * - Wildcard records: *.example.com matches any subdomain
 */
public class Problem52_DNSResolverCacheWithTTL {

    static class DNSRecord {
        String name;
        String type; // A, AAAA, CNAME, MX
        String value;
        long ttlSeconds;
        long cachedAt;
        boolean isNegative; // NXDOMAIN cache

        DNSRecord(String name, String type, String value, long ttl) {
            this.name = name; this.type = type; this.value = value;
            this.ttlSeconds = ttl; this.cachedAt = System.currentTimeMillis() / 1000;
        }

        boolean isExpired(long now) { return (now - cachedAt) >= ttlSeconds; }
        long remainingTTL(long now) { return Math.max(0, ttlSeconds - (now - cachedAt)); }
    }

    static class DNSTrieNode {
        Map<String, DNSTrieNode> children = new HashMap<>();
        List<DNSRecord> records = new ArrayList<>();
        boolean isWildcard;
    }

    static class DNSCache {
        DNSTrieNode root = new DNSTrieNode();
        int hits = 0, misses = 0;
        long simulatedTime; // seconds since epoch

        DNSCache(long startTime) { this.simulatedTime = startTime; }

        void put(DNSRecord record) {
            // Split domain in reverse (com -> example -> www)
            String[] labels = record.name.split("\\.");
            DNSTrieNode node = root;
            for (int i = labels.length - 1; i >= 0; i--) {
                String label = labels[i];
                node.children.computeIfAbsent(label, k -> new DNSTrieNode());
                node = node.children.get(label);
                if (label.equals("*")) node.isWildcard = true;
            }
            // Remove expired records for same name/type
            node.records.removeIf(r -> r.name.equals(record.name) && r.type.equals(record.type));
            record.cachedAt = simulatedTime;
            node.records.add(record);
        }

        List<DNSRecord> lookup(String name, String type) {
            String[] labels = name.split("\\.");
            DNSTrieNode node = root;
            DNSTrieNode wildcardMatch = null;

            for (int i = labels.length - 1; i >= 0; i--) {
                // Check for wildcard at this level
                DNSTrieNode wc = node.children.get("*");
                if (wc != null) wildcardMatch = wc;

                DNSTrieNode next = node.children.get(labels[i]);
                if (next == null) {
                    // Try wildcard match
                    node = wildcardMatch;
                    break;
                }
                node = next;
            }

            if (node == null) { misses++; return List.of(); }

            List<DNSRecord> results = new ArrayList<>();
            for (DNSRecord r : node.records) {
                if (r.type.equals(type) && !r.isExpired(simulatedTime)) {
                    results.add(r);
                }
            }

            if (results.isEmpty()) misses++;
            else hits++;
            return results;
        }

        // Evict expired entries
        int evictExpired() {
            int[] evicted = {0};
            evictNode(root, evicted);
            return evicted[0];
        }

        private void evictNode(DNSTrieNode node, int[] count) {
            int before = node.records.size();
            node.records.removeIf(r -> r.isExpired(simulatedTime));
            count[0] += before - node.records.size();
            for (DNSTrieNode child : node.children.values()) evictNode(child, count);
        }

        void advanceTime(long seconds) { simulatedTime += seconds; }
        double hitRate() { return hits + misses == 0 ? 0 : (double) hits / (hits + misses); }
    }

    public static void main(String[] args) {
        System.out.println("=== DNS Resolver Cache with TTL ===\n");

        DNSCache cache = new DNSCache(1000);

        // Populate cache
        cache.put(new DNSRecord("www.example.com", "A", "93.184.216.34", 300));
        cache.put(new DNSRecord("api.example.com", "A", "93.184.216.35", 60));
        cache.put(new DNSRecord("*.cdn.example.com", "A", "13.32.0.1", 3600));
        cache.put(new DNSRecord("example.com", "MX", "mail.example.com", 3600));

        // Lookups
        System.out.println("Lookups at t=0:");
        printLookup(cache, "www.example.com", "A");
        printLookup(cache, "api.example.com", "A");
        printLookup(cache, "img.cdn.example.com", "A"); // wildcard match
        printLookup(cache, "unknown.example.com", "A"); // miss

        // Advance time past api TTL
        cache.advanceTime(61);
        System.out.println("\nAfter 61 seconds (api TTL=60s expired):");
        printLookup(cache, "api.example.com", "A"); // should miss
        printLookup(cache, "www.example.com", "A"); // still valid (TTL=300)

        System.out.printf("%nCache hit rate: %.0f%%%n", cache.hitRate() * 100);
        System.out.println("Evicted expired: " + cache.evictExpired());
    }

    static void printLookup(DNSCache cache, String name, String type) {
        List<DNSRecord> results = cache.lookup(name, type);
        if (results.isEmpty()) System.out.printf("  %-30s -> MISS%n", name);
        else results.forEach(r -> System.out.printf("  %-30s -> %s (TTL=%d remaining)%n",
                name, r.value, r.remainingTTL(cache.simulatedTime)));
    }
}
