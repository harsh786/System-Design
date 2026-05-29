import java.util.*;

/**
 * Problem 60: Graph-based Feature Flag Dependencies
 * 
 * Production Relevance:
 * - Feature flags often depend on other flags (e.g., "new-checkout" requires "payment-v2")
 * - Dependency graph prevents enabling a flag without its prerequisites
 * - Used in LaunchDarkly, Unleash, internal feature management platforms
 * - Prevents broken user experiences from partial feature activation
 * 
 * Architect Considerations:
 * - Cycle detection: mutual dependencies indicate design smell
 * - Transitive closure: what flags become available when we enable X?
 * - Kill switch propagation: disabling a flag cascades to dependents
 */
public class Problem60_GraphBasedFeatureFlagDependencies {

    static class FeatureFlag {
        String id;
        String description;
        boolean enabled;
        Set<String> requires = new LinkedHashSet<>(); // prerequisites

        FeatureFlag(String id, String description, String... requires) {
            this.id = id; this.description = description;
            this.requires.addAll(Arrays.asList(requires));
        }
    }

    static class FeatureFlagSystem {
        Map<String, FeatureFlag> flags = new LinkedHashMap<>();

        void register(FeatureFlag flag) { flags.put(flag.id, flag); }

        // Can this flag be enabled? (all prerequisites must be enabled)
        boolean canEnable(String flagId) {
            FeatureFlag flag = flags.get(flagId);
            if (flag == null) return false;
            for (String req : flag.requires) {
                FeatureFlag dep = flags.get(req);
                if (dep == null || !dep.enabled) return false;
                // Transitive check
                if (!canEnable(req) && !dep.enabled) return false;
            }
            return true;
        }

        // Enable flag with dependency validation
        List<String> enable(String flagId) {
            List<String> errors = new ArrayList<>();
            FeatureFlag flag = flags.get(flagId);
            if (flag == null) { errors.add("Flag not found: " + flagId); return errors; }

            for (String req : flag.requires) {
                FeatureFlag dep = flags.get(req);
                if (dep == null) errors.add("Missing dependency: " + req);
                else if (!dep.enabled) errors.add("Dependency not enabled: " + req);
            }

            if (errors.isEmpty()) flag.enabled = true;
            return errors;
        }

        // Disable flag and cascade to dependents
        Set<String> disable(String flagId) {
            Set<String> cascaded = new LinkedHashSet<>();
            FeatureFlag flag = flags.get(flagId);
            if (flag == null || !flag.enabled) return cascaded;

            flag.enabled = false;
            cascaded.add(flagId);

            // Find all flags that depend on this one (reverse dependencies)
            for (FeatureFlag f : flags.values()) {
                if (f.enabled && f.requires.contains(flagId)) {
                    cascaded.addAll(disable(f.id)); // Recursive cascade
                }
            }
            return cascaded;
        }

        // What flags become available if we enable a given flag?
        Set<String> whatUnlocks(String flagId) {
            Set<String> unlocked = new HashSet<>();
            // Temporarily enable
            flags.get(flagId).enabled = true;
            for (FeatureFlag f : flags.values()) {
                if (!f.enabled && !f.id.equals(flagId) && canEnable(f.id)) {
                    unlocked.add(f.id);
                }
            }
            flags.get(flagId).enabled = false; // Restore
            return unlocked;
        }

        // Detect cycles in dependency graph
        boolean hasCycles() {
            Set<String> visited = new HashSet<>(), inStack = new HashSet<>();
            for (String id : flags.keySet()) {
                if (!visited.contains(id) && dfsHasCycle(id, visited, inStack)) return true;
            }
            return false;
        }

        private boolean dfsHasCycle(String node, Set<String> visited, Set<String> inStack) {
            visited.add(node); inStack.add(node);
            for (String dep : flags.get(node).requires) {
                if (!visited.contains(dep) && flags.containsKey(dep)) {
                    if (dfsHasCycle(dep, visited, inStack)) return true;
                } else if (inStack.contains(dep)) return true;
            }
            inStack.remove(node);
            return false;
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Graph-based Feature Flag Dependencies ===\n");

        FeatureFlagSystem system = new FeatureFlagSystem();
        system.register(new FeatureFlag("payment-v2", "New payment processor"));
        system.register(new FeatureFlag("new-checkout", "Redesigned checkout flow", "payment-v2"));
        system.register(new FeatureFlag("one-click-buy", "One click purchase", "new-checkout", "payment-v2"));
        system.register(new FeatureFlag("dark-mode", "Dark mode UI"));
        system.register(new FeatureFlag("premium-theme", "Premium themes", "dark-mode"));

        System.out.println("Has cycles: " + system.hasCycles());

        // Try enabling one-click-buy without prerequisites
        List<String> errors = system.enable("one-click-buy");
        System.out.println("\nEnable one-click-buy: " + (errors.isEmpty() ? "OK" : "FAILED: " + errors));

        // Enable in correct order
        system.enable("payment-v2");
        system.enable("new-checkout");
        errors = system.enable("one-click-buy");
        System.out.println("Enable payment-v2 -> new-checkout -> one-click-buy: " + (errors.isEmpty() ? "OK" : "FAILED"));

        // What does dark-mode unlock?
        System.out.println("\nEnabling dark-mode unlocks: " + system.whatUnlocks("dark-mode"));

        // Kill switch: disable payment-v2, cascades
        System.out.println("\nDisabling payment-v2 cascades to: " + system.disable("payment-v2"));
    }
}
