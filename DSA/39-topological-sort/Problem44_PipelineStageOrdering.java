import java.util.*;

/**
 * Problem: Pipeline Stage Ordering
 * Order data pipeline stages respecting data flow dependencies.
 *
 * Approach: Topological sort with stage metadata
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Apache Beam/Spark DAG stage ordering.
 */
public class Problem44_PipelineStageOrdering {

    public List<String> orderStages(Map<String, List<String>> pipeline) {
        Map<String, Integer> inDeg = new HashMap<>();
        Map<String, List<String>> graph = new HashMap<>();

        for (String stage : pipeline.keySet()) {
            inDeg.putIfAbsent(stage, 0);
            graph.putIfAbsent(stage, new ArrayList<>());
            for (String dep : pipeline.get(stage)) {
                graph.computeIfAbsent(dep, k -> new ArrayList<>()).add(stage);
                inDeg.merge(stage, 1, Integer::sum);
                inDeg.putIfAbsent(dep, 0);
            }
        }

        Queue<String> q = new PriorityQueue<>();
        for (var e : inDeg.entrySet()) if (e.getValue() == 0) q.offer(e.getKey());

        List<String> order = new ArrayList<>();
        while (!q.isEmpty()) {
            String s = q.poll(); order.add(s);
            for (String nei : graph.getOrDefault(s, Collections.emptyList()))
                if (inDeg.merge(nei, -1, Integer::sum) == 0) q.offer(nei);
        }
        return order;
    }

    public static void main(String[] args) {
        Problem44_PipelineStageOrdering solver = new Problem44_PipelineStageOrdering();
        Map<String, List<String>> pipeline = new HashMap<>();
        pipeline.put("transform", Arrays.asList("extract"));
        pipeline.put("load", Arrays.asList("transform"));
        pipeline.put("extract", Collections.emptyList());
        System.out.println(solver.orderStages(pipeline)); // [extract, transform, load]
    }
}
