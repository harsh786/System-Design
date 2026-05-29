import java.util.*;

/**
 * Problem 53: Circular Dependency Detection in Modules
 * 
 * Production Relevance:
 * - Build systems (Bazel, Gradle), module bundlers (webpack), DI containers
 * - Circular deps cause: infinite loops in initialization, deadlocks, build failures
 * - Must detect AND report the cycle for developer to fix
 * - Go compiler, ESLint circular import rules, Spring circular bean refs
 * 
 * Architect Considerations:
 * - DFS with coloring: WHITE (unvisited), GRAY (in stack), BLACK (done)
 * - Report ALL cycles, not just first detected (for developer experience)
 * - Strongly connected components (Tarjan's) finds all circular groups
 */
public class Problem53_CircularDependencyDetectionModules {

    enum Color { WHITE, GRAY, BLACK }

    static class ModuleGraph {
        Map<String, Set<String>> imports = new LinkedHashMap<>();

        void addModule(String module, String... dependencies) {
            imports.computeIfAbsent(module, k -> new LinkedHashSet<>());
            for (String dep : dependencies) {
                imports.get(module).add(dep);
                imports.computeIfAbsent(dep, k -> new LinkedHashSet<>());
            }
        }

        // Detect all cycles using DFS with path tracking
        List<List<String>> findAllCycles() {
            List<List<String>> cycles = new ArrayList<>();
            Map<String, Color> color = new HashMap<>();
            imports.keySet().forEach(m -> color.put(m, Color.WHITE));

            for (String module : imports.keySet()) {
                if (color.get(module) == Color.WHITE) {
                    dfs(module, color, new LinkedList<>(), cycles);
                }
            }
            return cycles;
        }

        private void dfs(String node, Map<String, Color> color, LinkedList<String> path, List<List<String>> cycles) {
            color.put(node, Color.GRAY);
            path.addLast(node);

            for (String dep : imports.getOrDefault(node, Set.of())) {
                if (color.getOrDefault(dep, Color.WHITE) == Color.GRAY) {
                    // Found cycle: extract cycle from path
                    int cycleStart = path.indexOf(dep);
                    List<String> cycle = new ArrayList<>(path.subList(cycleStart, path.size()));
                    cycle.add(dep); // close the cycle
                    cycles.add(cycle);
                } else if (color.getOrDefault(dep, Color.WHITE) == Color.WHITE) {
                    dfs(dep, color, path, cycles);
                }
            }

            path.removeLast();
            color.put(node, Color.BLACK);
        }

        // Tarjan's SCC to find all circular dependency groups
        List<List<String>> findSCCs() {
            List<List<String>> sccs = new ArrayList<>();
            Map<String, Integer> index = new HashMap<>(), lowlink = new HashMap<>();
            Set<String> onStack = new HashSet<>();
            Deque<String> stack = new ArrayDeque<>();
            int[] counter = {0};

            for (String node : imports.keySet()) {
                if (!index.containsKey(node)) {
                    tarjan(node, index, lowlink, onStack, stack, sccs, counter);
                }
            }
            return sccs;
        }

        private void tarjan(String v, Map<String, Integer> index, Map<String, Integer> lowlink,
                           Set<String> onStack, Deque<String> stack, List<List<String>> sccs, int[] counter) {
            index.put(v, counter[0]);
            lowlink.put(v, counter[0]);
            counter[0]++;
            stack.push(v);
            onStack.add(v);

            for (String w : imports.getOrDefault(v, Set.of())) {
                if (!index.containsKey(w)) {
                    tarjan(w, index, lowlink, onStack, stack, sccs, counter);
                    lowlink.put(v, Math.min(lowlink.get(v), lowlink.get(w)));
                } else if (onStack.contains(w)) {
                    lowlink.put(v, Math.min(lowlink.get(v), index.get(w)));
                }
            }

            if (lowlink.get(v).equals(index.get(v))) {
                List<String> scc = new ArrayList<>();
                String w;
                do {
                    w = stack.pop();
                    onStack.remove(w);
                    scc.add(w);
                } while (!w.equals(v));
                if (scc.size() > 1) sccs.add(scc); // Only report non-trivial SCCs
            }
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Circular Dependency Detection in Modules ===\n");

        ModuleGraph graph = new ModuleGraph();
        graph.addModule("UserService", "AuthService", "DatabaseService");
        graph.addModule("AuthService", "TokenService", "UserService"); // Circular!
        graph.addModule("TokenService", "CryptoService");
        graph.addModule("OrderService", "PaymentService", "InventoryService");
        graph.addModule("PaymentService", "OrderService"); // Circular!
        graph.addModule("InventoryService");
        graph.addModule("DatabaseService");
        graph.addModule("CryptoService");

        List<List<String>> cycles = graph.findAllCycles();
        System.out.println("Cycles detected: " + cycles.size());
        for (List<String> cycle : cycles) {
            System.out.println("  " + String.join(" -> ", cycle));
        }

        System.out.println("\nStrongly Connected Components (circular groups):");
        List<List<String>> sccs = graph.findSCCs();
        for (List<String> scc : sccs) {
            System.out.println("  " + scc);
        }
    }
}
