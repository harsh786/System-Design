import java.util.*;

/**
 * Problem 10: SCC for Microservice Dependency Analysis
 * 
 * In microservice architectures, understanding dependency structure is critical:
 * - Circular dependencies prevent independent deployment
 * - Deployment order follows topological sort of condensation DAG
 * - Fault domains correspond to SCCs (if one fails, all in SCC likely fail)
 * 
 * This tool analyzes a service dependency graph and provides:
 * 1. Circular dependency groups (SCCs)
 * 2. Safe deployment order (topological sort of condensation)
 * 3. Blast radius analysis (what fails if a service goes down)
 */
public class Problem10_SCCMicroserviceDependency {

    static class ServiceGraph {
        Map<String, Set<String>> deps = new LinkedHashMap<>();
        
        void addService(String name) { deps.putIfAbsent(name, new HashSet<>()); }
        void addDependency(String from, String to) {
            addService(from); addService(to);
            deps.get(from).add(to);
        }

        void analyze() {
            // Map names to indices
            List<String> services = new ArrayList<>(deps.keySet());
            Map<String, Integer> idx = new HashMap<>();
            for (int i = 0; i < services.size(); i++) idx.put(services.get(i), i);
            int n = services.size();
            
            // Build graph
            List<List<Integer>> graph = new ArrayList<>();
            for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
            for (var entry : deps.entrySet()) {
                for (String dep : entry.getValue()) {
                    graph.get(idx.get(entry.getKey())).add(idx.get(dep));
                }
            }
            
            // Find SCCs (Kosaraju's)
            boolean[] visited = new boolean[n];
            Deque<Integer> stack = new ArrayDeque<>();
            for (int i = 0; i < n; i++) if (!visited[i]) dfs1(i, graph, visited, stack);
            
            List<List<Integer>> trans = new ArrayList<>();
            for (int i = 0; i < n; i++) trans.add(new ArrayList<>());
            for (int u = 0; u < n; u++) for (int v : graph.get(u)) trans.get(v).add(u);
            
            Arrays.fill(visited, false);
            List<List<String>> sccs = new ArrayList<>();
            int[] comp = new int[n];
            int compId = 0;
            while (!stack.isEmpty()) {
                int v = stack.pop();
                if (!visited[v]) {
                    List<Integer> scc = new ArrayList<>();
                    dfs2(v, trans, visited, scc);
                    List<String> sccNames = new ArrayList<>();
                    for (int node : scc) { sccNames.add(services.get(node)); comp[node] = compId; }
                    sccs.add(sccNames);
                    compId++;
                }
            }
            
            // Print analysis
            System.out.println("=== Microservice Dependency Analysis ===\n");
            System.out.println("Total services: " + n);
            System.out.println("Dependency groups (SCCs): " + sccs.size());
            
            boolean hasCycles = false;
            System.out.println("\n--- Circular Dependencies (CRITICAL) ---");
            for (List<String> scc : sccs) {
                if (scc.size() > 1) {
                    hasCycles = true;
                    System.out.println("  CYCLE: " + scc);
                }
            }
            if (!hasCycles) System.out.println("  None found (healthy architecture)");
            
            // Deployment order (reverse topological of condensation)
            System.out.println("\n--- Safe Deployment Order ---");
            // SCCs from Kosaraju are already in reverse topological order
            for (int i = sccs.size() - 1; i >= 0; i--) {
                System.out.println("  " + (sccs.size() - i) + ". " + sccs.get(i));
            }
            
            // Blast radius
            System.out.println("\n--- Blast Radius (if service fails) ---");
            // Count reachable nodes in reverse graph (who depends on this?)
            for (int i = 0; i < n; i++) {
                boolean[] reachable = new boolean[n];
                dfs2(i, trans, reachable, new ArrayList<>());
                // Reset visited for blast radius
                long count = 0;
                for (boolean b : reachable) if (b) count++;
                if (count > 2) { // Only show interesting ones
                    System.out.println("  " + services.get(i) + " failure affects " + (count-1) + " services");
                }
            }
        }

        private void dfs1(int u, List<List<Integer>> g, boolean[] vis, Deque<Integer> stack) {
            vis[u] = true;
            for (int v : g.get(u)) if (!vis[v]) dfs1(v, g, vis, stack);
            stack.push(u);
        }
        private void dfs2(int u, List<List<Integer>> g, boolean[] vis, List<Integer> result) {
            vis[u] = true; result.add(u);
            for (int v : g.get(u)) if (!vis[v]) dfs2(v, g, vis, result);
        }
    }

    public static void main(String[] args) {
        ServiceGraph sg = new ServiceGraph();
        
        // Typical e-commerce microservice architecture
        sg.addDependency("api-gateway", "auth-service");
        sg.addDependency("api-gateway", "product-service");
        sg.addDependency("api-gateway", "order-service");
        sg.addDependency("order-service", "inventory-service");
        sg.addDependency("order-service", "payment-service");
        sg.addDependency("payment-service", "notification-service");
        sg.addDependency("auth-service", "user-db");
        sg.addDependency("product-service", "product-db");
        // Introduce a cycle (bad practice)
        sg.addDependency("notification-service", "user-db");
        sg.addDependency("inventory-service", "order-service"); // Cycle!
        
        sg.analyze();
    }
}
