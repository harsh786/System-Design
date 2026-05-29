import java.util.*;

/**
 * Problem 60: Configuration Override Resolution (hierarchical)
 * 
 * Production Relevance:
 * - Config systems: global defaults -> env-specific -> service-specific -> instance override
 * - Used in Spring Cloud Config, Consul KV, etcd, Azure App Configuration
 * - Hierarchical key paths: /app/service-a/database/timeout
 * - Feature: more specific path overrides less specific (like CSS cascade)
 * 
 * Architect Considerations:
 * - Atomic updates: config change at any level should propagate instantly
 * - Watch/subscribe: notify services when their config changes
 * - Version history for rollback
 * - Trie structure enables efficient prefix scans (get all keys under /app/service-a/)
 */
public class Problem60_ConfigurationOverrideResolution {

    static class ConfigValue {
        String value;
        long version;
        long timestamp;
        String source; // which level set this

        ConfigValue(String value, String source) {
            this.value = value; this.source = source;
            this.version = System.nanoTime(); this.timestamp = System.currentTimeMillis();
        }

        @Override
        public String toString() { return value + " (from " + source + ")"; }
    }

    static class ConfigNode {
        Map<String, ConfigNode> children = new LinkedHashMap<>();
        ConfigValue localValue; // value set at this exact path
        List<ConfigChangeListener> watchers = new ArrayList<>();
    }

    interface ConfigChangeListener {
        void onConfigChange(String path, ConfigValue oldVal, ConfigValue newVal);
    }

    static class HierarchicalConfig {
        ConfigNode root = new ConfigNode();
        List<String> changeLog = new ArrayList<>();

        // Set value at specific path
        void set(String path, String value, String source) {
            String[] segments = path.split("/");
            ConfigNode node = root;
            for (int i = 1; i < segments.length; i++) {
                node.children.computeIfAbsent(segments[i], k -> new ConfigNode());
                node = node.children.get(segments[i]);
            }
            ConfigValue oldVal = node.localValue;
            node.localValue = new ConfigValue(value, source);
            changeLog.add(String.format("SET %s = %s [%s]", path, value, source));
            notifyWatchers(node, path, oldVal, node.localValue);
        }

        // Get resolved value (most specific path that has a value)
        ConfigValue get(String path) {
            String[] segments = path.split("/");
            ConfigNode node = root;
            ConfigValue resolved = root.localValue; // global default

            for (int i = 1; i < segments.length; i++) {
                node = node.children.get(segments[i]);
                if (node == null) break;
                if (node.localValue != null) resolved = node.localValue;
            }
            return resolved;
        }

        // Get all keys under a prefix (prefix scan)
        Map<String, ConfigValue> getPrefix(String prefix) {
            Map<String, ConfigValue> results = new LinkedHashMap<>();
            String[] segments = prefix.split("/");
            ConfigNode node = root;

            for (int i = 1; i < segments.length; i++) {
                node = node.children.get(segments[i]);
                if (node == null) return results;
            }

            collectAll(node, prefix, results);
            return results;
        }

        private void collectAll(ConfigNode node, String path, Map<String, ConfigValue> results) {
            if (node.localValue != null) results.put(path, node.localValue);
            for (Map.Entry<String, ConfigNode> child : node.children.entrySet()) {
                collectAll(child.getValue(), path + "/" + child.getKey(), results);
            }
        }

        // Watch for changes at a path (including children)
        void watch(String path, ConfigChangeListener listener) {
            String[] segments = path.split("/");
            ConfigNode node = root;
            for (int i = 1; i < segments.length; i++) {
                node.children.computeIfAbsent(segments[i], k -> new ConfigNode());
                node = node.children.get(segments[i]);
            }
            node.watchers.add(listener);
        }

        private void notifyWatchers(ConfigNode node, String path, ConfigValue oldVal, ConfigValue newVal) {
            for (ConfigChangeListener l : node.watchers) l.onConfigChange(path, oldVal, newVal);
        }

        // Resolve with explicit override order
        ConfigValue resolveWithLayers(String path, List<String> layers) {
            ConfigValue result = null;
            for (String layer : layers) {
                ConfigValue v = get(layer + path);
                if (v != null) result = v;
            }
            return result;
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Configuration Override Resolution ===\n");

        HierarchicalConfig config = new HierarchicalConfig();

        // Set defaults at various levels
        config.set("/database/timeout", "30000", "global-default");
        config.set("/database/pool-size", "10", "global-default");
        config.set("/database/host", "db.internal", "global-default");

        // Environment override
        config.set("/prod/database/timeout", "5000", "env:prod");
        config.set("/prod/database/pool-size", "50", "env:prod");

        // Service-specific override
        config.set("/prod/api-service/database/timeout", "3000", "service:api");
        config.set("/prod/api-service/database/host", "db-primary.prod", "service:api");

        // Resolution
        System.out.println("Config resolution:");
        System.out.println("  /database/timeout -> " + config.get("/database/timeout"));
        System.out.println("  /prod/database/timeout -> " + config.get("/prod/database/timeout"));
        System.out.println("  /prod/api-service/database/timeout -> " + config.get("/prod/api-service/database/timeout"));
        System.out.println("  /prod/api-service/database/pool-size -> " + config.get("/prod/api-service/database/pool-size"));

        // Prefix scan
        System.out.println("\nAll config under /prod/api-service:");
        config.getPrefix("/prod/api-service").forEach((k, v) -> System.out.printf("  %s = %s%n", k, v));

        // Watch
        config.watch("/prod/database", (path, old, newVal) ->
                System.out.printf("  WATCH: %s changed to %s%n", path, newVal.value));
        System.out.println("\nUpdating /prod/database/timeout:");
        config.set("/prod/database/timeout", "4000", "hotfix");

        System.out.println("\nChange log:");
        config.changeLog.forEach(l -> System.out.println("  " + l));
    }
}
