import java.util.*;

/**
 * Problem: Event Ordering in Distributed System
 * Determine causal ordering of events using happens-before relationships.
 *
 * Approach: Topological sort on happens-before graph (Lamport clocks concept)
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Lamport/vector clock based event ordering in distributed tracing.
 */
public class Problem46_EventOrderingInDistributedSystem {

    public List<List<String>> causalOrder(Map<String, List<String>> happensBefore) {
        Map<String, Integer> inDeg = new HashMap<>();
        Map<String, List<String>> graph = new HashMap<>();

        for (String event : happensBefore.keySet()) {
            inDeg.putIfAbsent(event, 0);
            graph.putIfAbsent(event, new ArrayList<>());
            for (String after : happensBefore.get(event)) {
                graph.get(event).add(after);
                inDeg.merge(after, 1, Integer::sum);
                inDeg.putIfAbsent(after, 0);
                graph.putIfAbsent(after, new ArrayList<>());
            }
        }

        Queue<String> q = new LinkedList<>();
        for (var e : inDeg.entrySet()) if (e.getValue() == 0) q.offer(e.getKey());

        List<List<String>> levels = new ArrayList<>();
        while (!q.isEmpty()) {
            List<String> batch = new ArrayList<>();
            int size = q.size();
            for (int i = 0; i < size; i++) {
                String event = q.poll(); batch.add(event);
                for (String nei : graph.get(event))
                    if (inDeg.merge(nei, -1, Integer::sum) == 0) q.offer(nei);
            }
            levels.add(batch);
        }
        return levels;
    }

    public static void main(String[] args) {
        Problem46_EventOrderingInDistributedSystem solver = new Problem46_EventOrderingInDistributedSystem();
        Map<String, List<String>> hb = new HashMap<>();
        hb.put("send_A", Arrays.asList("recv_A"));
        hb.put("recv_A", Arrays.asList("process_B"));
        hb.put("send_C", Arrays.asList("recv_C"));
        hb.put("recv_C", Collections.emptyList());
        hb.put("process_B", Collections.emptyList());
        System.out.println(solver.causalOrder(hb));
    }
}
