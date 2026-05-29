import java.util.*;

/**
 * Problem 51: Dependency Resolution with Version Conflicts
 * 
 * Production Relevance:
 * - Package managers (npm, Maven, pip) must resolve version conflicts in dependency graphs
 * - Diamond dependency problem: A->B->D@1.0, A->C->D@2.0
 * - Strategies: newest wins, nearest wins (npm), fail on conflict (strict)
 * - Maven's "dependency mediation" uses nearest-first BFS
 * 
 * Architect Considerations:
 * - SAT solver approach for complex constraints (e.g., Pub/Dart solver)
 * - Lock files ensure reproducible builds across environments
 * - Semantic versioning compatibility ranges add complexity
 */
public class Problem51_DependencyResolutionVersionConflicts {

    static class Dependency {
        String name;
        String version;
        List<Dependency> transitive;

        Dependency(String name, String version, Dependency... deps) {
            this.name = name;
            this.version = version;
            this.transitive = Arrays.asList(deps);
        }
    }

    enum Strategy { NEAREST_WINS, NEWEST_WINS, FAIL_ON_CONFLICT }

    static class DependencyResolver {
        private final Strategy strategy;

        DependencyResolver(Strategy strategy) { this.strategy = strategy; }

        public Map<String, String> resolve(List<Dependency> roots) throws Exception {
            // BFS with depth tracking
            Map<String, String> resolved = new LinkedHashMap<>();
            Map<String, Integer> depthMap = new HashMap<>();
            Map<String, List<String>> conflicts = new HashMap<>();
            Queue<Map.Entry<Dependency, Integer>> queue = new LinkedList<>();

            for (Dependency root : roots) {
                queue.offer(Map.entry(root, 0));
            }

            while (!queue.isEmpty()) {
                Map.Entry<Dependency, Integer> entry = queue.poll();
                Dependency dep = entry.getKey();
                int depth = entry.getValue();

                if (resolved.containsKey(dep.name)) {
                    String existing = resolved.get(dep.name);
                    if (!existing.equals(dep.version)) {
                        conflicts.computeIfAbsent(dep.name, k -> new ArrayList<>(List.of(existing)))
                                .add(dep.version);

                        switch (strategy) {
                            case FAIL_ON_CONFLICT:
                                throw new Exception("Conflict: " + dep.name + " " + existing + " vs " + dep.version);
                            case NEAREST_WINS:
                                if (depth < depthMap.get(dep.name)) {
                                    resolved.put(dep.name, dep.version);
                                    depthMap.put(dep.name, depth);
                                }
                                break;
                            case NEWEST_WINS:
                                if (compareVersions(dep.version, existing) > 0) {
                                    resolved.put(dep.name, dep.version);
                                }
                                break;
                        }
                    }
                    continue;
                }

                resolved.put(dep.name, dep.version);
                depthMap.put(dep.name, depth);
                for (Dependency child : dep.transitive) {
                    queue.offer(Map.entry(child, depth + 1));
                }
            }

            if (!conflicts.isEmpty()) {
                System.out.println("  Conflicts resolved: " + conflicts);
            }
            return resolved;
        }

        private int compareVersions(String v1, String v2) {
            String[] p1 = v1.split("\\.");
            String[] p2 = v2.split("\\.");
            for (int i = 0; i < Math.max(p1.length, p2.length); i++) {
                int n1 = i < p1.length ? Integer.parseInt(p1[i]) : 0;
                int n2 = i < p2.length ? Integer.parseInt(p2[i]) : 0;
                if (n1 != n2) return Integer.compare(n1, n2);
            }
            return 0;
        }
    }

    public static void main(String[] args) throws Exception {
        System.out.println("=== Dependency Resolution with Version Conflicts ===\n");

        // Diamond: app -> libA -> utils@1.0, app -> libB -> utils@2.0
        Dependency utils1 = new Dependency("utils", "1.0");
        Dependency utils2 = new Dependency("utils", "2.0");
        Dependency libA = new Dependency("libA", "3.0", utils1);
        Dependency libB = new Dependency("libB", "1.5", utils2);

        System.out.println("Strategy: NEAREST_WINS");
        DependencyResolver nearest = new DependencyResolver(Strategy.NEAREST_WINS);
        Map<String, String> result = nearest.resolve(List.of(libA, libB));
        System.out.println("  Resolved: " + result);

        System.out.println("\nStrategy: NEWEST_WINS");
        DependencyResolver newest = new DependencyResolver(Strategy.NEWEST_WINS);
        result = newest.resolve(List.of(libA, libB));
        System.out.println("  Resolved: " + result);

        System.out.println("\nStrategy: FAIL_ON_CONFLICT");
        try {
            new DependencyResolver(Strategy.FAIL_ON_CONFLICT).resolve(List.of(libA, libB));
        } catch (Exception e) {
            System.out.println("  Exception: " + e.getMessage());
        }
    }
}
