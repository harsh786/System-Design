import java.util.*;

/**
 * Problem 53: Feature Flag Hierarchical Lookup
 * 
 * Production Relevance:
 * - Feature flags often follow hierarchy: org > project > environment > user
 * - More specific settings override general ones (CSS specificity model)
 * - Used in LaunchDarkly, ConfigCat, internal feature management
 * - Trie enables efficient hierarchical resolution with inheritance
 * 
 * Architect Considerations:
 * - Inheritance: child inherits parent's flags unless overridden
 * - Evaluation order: most specific match wins
 * - Bulk evaluation: evaluate all flags for a context efficiently
 */
public class Problem53_FeatureFlagHierarchicalLookup {

    static class FlagValue {
        boolean enabled;
        String variant; // for multivariate flags
        int percentRollout; // 0-100

        FlagValue(boolean enabled, String variant, int rollout) {
            this.enabled = enabled; this.variant = variant; this.percentRollout = rollout;
        }

        @Override
        public String toString() {
            return String.format("enabled=%s, variant=%s, rollout=%d%%", enabled, variant, percentRollout);
        }
    }

    static class HierarchyNode {
        String segment;
        Map<String, HierarchyNode> children = new HashMap<>();
        Map<String, FlagValue> flags = new HashMap<>(); // flagName -> value at this level

        HierarchyNode(String segment) { this.segment = segment; }
    }

    static class FeatureFlagHierarchy {
        HierarchyNode root = new HierarchyNode("root");

        // Set flag at a specific path: e.g., "org:acme/project:web/env:prod"
        void setFlag(String path, String flagName, FlagValue value) {
            HierarchyNode node = root;
            for (String segment : path.split("/")) {
                node.children.computeIfAbsent(segment, HierarchyNode::new);
                node = node.children.get(segment);
            }
            node.flags.put(flagName, value);
        }

        // Resolve flag with hierarchical inheritance (most specific wins)
        FlagValue resolve(String path, String flagName) {
            HierarchyNode node = root;
            FlagValue result = root.flags.get(flagName); // global default

            for (String segment : path.split("/")) {
                node = node.children.get(segment);
                if (node == null) break;
                FlagValue override = node.flags.get(flagName);
                if (override != null) result = override; // more specific overrides
            }
            return result;
        }

        // Resolve ALL flags for a context (merge all levels)
        Map<String, FlagValue> resolveAll(String path) {
            Map<String, FlagValue> merged = new HashMap<>(root.flags);
            HierarchyNode node = root;

            for (String segment : path.split("/")) {
                node = node.children.get(segment);
                if (node == null) break;
                merged.putAll(node.flags); // override with more specific
            }
            return merged;
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Feature Flag Hierarchical Lookup ===\n");

        FeatureFlagHierarchy flags = new FeatureFlagHierarchy();

        // Global defaults
        flags.setFlag("", "dark-mode", new FlagValue(false, "off", 0));
        flags.setFlag("", "new-checkout", new FlagValue(false, "off", 0));

        // Org level
        flags.setFlag("org:acme", "dark-mode", new FlagValue(true, "auto", 50));

        // Project level
        flags.setFlag("org:acme/project:web", "new-checkout", new FlagValue(true, "variant-a", 100));

        // Environment override
        flags.setFlag("org:acme/project:web/env:staging", "new-checkout", new FlagValue(true, "variant-b", 100));
        flags.setFlag("org:acme/project:web/env:prod", "new-checkout", new FlagValue(true, "variant-a", 10));

        // Lookups
        System.out.println("Flag resolution:");
        String[] paths = {
            "org:acme/project:web/env:prod",
            "org:acme/project:web/env:staging",
            "org:acme/project:mobile",
            "org:other",
        };

        for (String path : paths) {
            System.out.printf("\n  Context: %s%n", path);
            FlagValue dm = flags.resolve(path, "dark-mode");
            FlagValue nc = flags.resolve(path, "new-checkout");
            System.out.printf("    dark-mode:    %s%n", dm);
            System.out.printf("    new-checkout: %s%n", nc);
        }

        System.out.println("\n  All flags for org:acme/project:web/env:prod:");
        flags.resolveAll("org:acme/project:web/env:prod")
             .forEach((k, v) -> System.out.printf("    %s: %s%n", k, v));
    }
}
