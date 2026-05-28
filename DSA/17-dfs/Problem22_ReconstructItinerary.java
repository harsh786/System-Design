import java.util.*;

/**
 * Problem: Reconstruct Itinerary (LeetCode 332)
 * Approach: Hierholzer's algorithm - DFS with priority queue for lexical order, post-order collection
 * Time: O(E*logE), Space: O(E)
 * Production Analogy: Reconstructing an optimal delivery route visiting all segments exactly once
 */
public class Problem22_ReconstructItinerary {
    Map<String, PriorityQueue<String>> graph = new HashMap<>();
    LinkedList<String> route = new LinkedList<>();

    public List<String> findItinerary(List<List<String>> tickets) {
        for (List<String> t : tickets)
            graph.computeIfAbsent(t.get(0), k -> new PriorityQueue<>()).add(t.get(1));
        dfs("JFK");
        return route;
    }

    private void dfs(String airport) {
        PriorityQueue<String> next = graph.get(airport);
        while (next != null && !next.isEmpty()) dfs(next.poll());
        route.addFirst(airport);
    }

    public static void main(String[] args) {
        List<List<String>> tickets = Arrays.asList(
            Arrays.asList("MUC","LHR"), Arrays.asList("JFK","MUC"),
            Arrays.asList("SFO","SJC"), Arrays.asList("LHR","SFO"));
        System.out.println(new Problem22_ReconstructItinerary().findItinerary(tickets));
    }
}
