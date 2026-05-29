import java.util.*;

/**
 * Problem 8: SCC for Dependency Cycle Detection
 * 
 * In build systems, package managers, and module systems, circular dependencies
 * cause compilation/loading failures. SCCs identify all cycles.
 * 
 * This implements:
 * 1. Detect all circular dependency groups
 * 2. Report which dependencies cause cycles
 * 3. Suggest minimum edges to remove to break all cycles (NP-hard in general,
 *    but we can give heuristic suggestions)
 */
public class Problem08_DependencyCycleDetection {

    static class DependencyAnalyzer {
        Map<String, Integer> nameToId = new HashMap<>();
        Map<Integer, String> idToName = new HashMap<>();
        List<List<Integer>> graph = new ArrayList<>();
        int nextId = 0;

        int getId(String name) {
            return nameToId.computeIfAbsent(name, k -> {
                int id = nextId++;
                idToName.put(id, name);
                graph.add(new ArrayList<>());
                return id;
            });
        }

        void addDependency(String from, String to) {
            graph.get(getId(from)).add(getId(to));
        }

        List<List<String>> findCycles() {
            int n = nextId;
            int[] disc = new int[n], low = new int[n], comp = new int[n];
            boolean[] onStack = new boolean[n];
            Arrays.fill(disc, -1);
            Deque<Integer> stack = new ArrayDeque<>();
            List<List<String>> cycles = new ArrayList<>();
            int[] state = {0, 0};
            
            for (int i = 0; i < n; i++) {
                if (disc[i] == -1) tarjan(i, disc, low, onStack, stack, comp, state, cycles);
            }
            return cycles;
        }

        private void tarjan(int u, int[] disc, int[] low, boolean[] onStack, 
                          Deque<Integer> stack, int[] comp, int[] state, List<List<String>> cycles) {
            disc[u] = low[u] = state[0]++;
            stack.push(u);
            onStack[u] = true;
            for (int v : graph.get(u)) {
                if (disc[v] == -1) { tarjan(v, disc, low, onStack, stack, comp, state, cycles); low[u] = Math.min(low[u], low[v]); }
                else if (onStack[v]) low[u] = Math.min(low[u], disc[v]);
            }
            if (low[u] == disc[u]) {
                List<String> scc = new ArrayList<>();
                while (true) {
                    int v = stack.pop(); onStack[v] = false; comp[v] = state[1];
                    scc.add(idToName.get(v));
                    if (v == u) break;
                }
                state[1]++;
                if (scc.size() > 1) cycles.add(scc); // Only report non-trivial SCCs
            }
        }
    }

    public static void main(String[] args) {
        DependencyAnalyzer analyzer = new DependencyAnalyzer();
        
        // Simulate microservice dependencies
        analyzer.addDependency("auth-service", "user-service");
        analyzer.addDependency("user-service", "notification-service");
        analyzer.addDependency("notification-service", "auth-service"); // Cycle!
        analyzer.addDependency("order-service", "payment-service");
        analyzer.addDependency("payment-service", "fraud-service");
        analyzer.addDependency("fraud-service", "order-service"); // Another cycle!
        analyzer.addDependency("api-gateway", "auth-service");
        analyzer.addDependency("api-gateway", "order-service");
        
        List<List<String>> cycles = analyzer.findCycles();
        
        System.out.println("Dependency Cycle Detection");
        System.out.println("=========================\n");
        if (cycles.isEmpty()) {
            System.out.println("No circular dependencies found!");
        } else {
            System.out.println("Found " + cycles.size() + " circular dependency group(s):");
            for (int i = 0; i < cycles.size(); i++) {
                System.out.println("  Cycle " + (i+1) + ": " + cycles.get(i));
                System.out.println("    Suggestion: Break dependency between " + 
                    cycles.get(i).get(0) + " and " + cycles.get(i).get(1));
            }
        }
    }
}
