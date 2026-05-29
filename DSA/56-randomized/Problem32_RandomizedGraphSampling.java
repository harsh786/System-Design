import java.util.*;

public class Problem32_RandomizedGraphSampling {
    // Random walk sampling on graph
    public static List<Integer> randomWalkSample(Map<Integer, List<Integer>> graph, int start, int steps) {
        Random rand = new Random();
        List<Integer> path = new ArrayList<>();
        int cur = start;
        for (int i = 0; i < steps; i++) {
            path.add(cur);
            List<Integer> neighbors = graph.getOrDefault(cur, Collections.emptyList());
            if (neighbors.isEmpty()) break;
            cur = neighbors.get(rand.nextInt(neighbors.size()));
        }
        return path;
    }

    public static void main(String[] args) {
        Map<Integer, List<Integer>> graph = new HashMap<>();
        graph.put(0, Arrays.asList(1,2)); graph.put(1, Arrays.asList(0,2,3));
        graph.put(2, Arrays.asList(0,1,3)); graph.put(3, Arrays.asList(1,2));
        System.out.println(randomWalkSample(graph, 0, 10));
    }
}
