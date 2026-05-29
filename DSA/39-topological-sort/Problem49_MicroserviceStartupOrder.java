import java.util.*;

/**
 * Problem: Microservice Startup Order
 * Determine startup order for microservices with health-check dependencies.
 *
 * Approach: Topological sort with level-based parallel startup groups
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Docker Compose / Kubernetes init container ordering.
 */
public class Problem49_MicroserviceStartupOrder {

    public List<List<String>> startupGroups(Map<String, List<String>> services) {
        Map<String, Integer> inDeg = new HashMap<>();
        Map<String, List<String>> graph = new HashMap<>();

        for (String svc : services.keySet()) {
            inDeg.putIfAbsent(svc, 0);
            graph.putIfAbsent(svc, new ArrayList<>());
            for (String dep : services.get(svc)) {
                graph.computeIfAbsent(dep, k -> new ArrayList<>()).add(svc);
                inDeg.merge(svc, 1, Integer::sum);
                inDeg.putIfAbsent(dep, 0);
            }
        }

        Queue<String> q = new LinkedList<>();
        for (var e : inDeg.entrySet()) if (e.getValue() == 0) q.offer(e.getKey());

        List<List<String>> groups = new ArrayList<>();
        while (!q.isEmpty()) {
            List<String> group = new ArrayList<>();
            int size = q.size();
            for (int i = 0; i < size; i++) {
                String svc = q.poll(); group.add(svc);
                for (String nei : graph.getOrDefault(svc, Collections.emptyList()))
                    if (inDeg.merge(nei, -1, Integer::sum) == 0) q.offer(nei);
            }
            groups.add(group);
        }
        return groups;
    }

    public static void main(String[] args) {
        Problem49_MicroserviceStartupOrder solver = new Problem49_MicroserviceStartupOrder();
        Map<String, List<String>> svcs = new HashMap<>();
        svcs.put("api-gateway", Arrays.asList("auth-service", "user-service"));
        svcs.put("auth-service", Arrays.asList("db"));
        svcs.put("user-service", Arrays.asList("db"));
        svcs.put("db", Collections.emptyList());
        System.out.println(solver.startupGroups(svcs));
    }
}
