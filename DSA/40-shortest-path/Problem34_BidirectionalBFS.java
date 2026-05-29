import java.util.*;

/**
 * Problem: Bidirectional BFS
 * Find shortest path using BFS from both source and target.
 *
 * Approach: Alternate BFS from source and target, meet in middle
 *
 * Time Complexity: O(b^(d/2)) where b=branching factor, d=depth
 * Space Complexity: O(b^(d/2))
 *
 * Production Analogy: Meeting-in-the-middle search for social network connection distance.
 */
public class Problem34_BidirectionalBFS {

    public int shortestPath(Map<Integer, List<Integer>> graph, int src, int dst) {
        if (src == dst) return 0;
        Set<Integer> visitedS = new HashSet<>(), visitedD = new HashSet<>();
        Set<Integer> frontS = new HashSet<>(), frontD = new HashSet<>();
        frontS.add(src); visitedS.add(src);
        frontD.add(dst); visitedD.add(dst);
        int steps = 0;

        while (!frontS.isEmpty() && !frontD.isEmpty()) {
            steps++;
            if (frontS.size() > frontD.size()) { Set<Integer> t = frontS; frontS = frontD; frontD = t; Set<Integer> tv = visitedS; visitedS = visitedD; visitedD = tv; }
            Set<Integer> next = new HashSet<>();
            for (int node : frontS)
                for (int nei : graph.getOrDefault(node, Collections.emptyList())) {
                    if (visitedD.contains(nei)) return steps;
                    if (visitedS.add(nei)) next.add(nei);
                }
            frontS = next;
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem34_BidirectionalBFS solver = new Problem34_BidirectionalBFS();
        Map<Integer, List<Integer>> graph = new HashMap<>();
        graph.put(0, Arrays.asList(1, 2));
        graph.put(1, Arrays.asList(0, 3));
        graph.put(2, Arrays.asList(0, 3));
        graph.put(3, Arrays.asList(1, 2, 4));
        graph.put(4, Arrays.asList(3));
        System.out.println(solver.shortestPath(graph, 0, 4)); // 3
    }
}
