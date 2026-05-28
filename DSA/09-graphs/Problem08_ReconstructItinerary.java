import java.util.*;

/**
 * Problem 8: Reconstruct Itinerary (LeetCode 332)
 * 
 * Approach: Hierholzer's algorithm for Eulerian path. Use PriorityQueue for lexical order.
 * Time: O(E log E), Space: O(E)
 * 
 * Production Analogy: Planning a network packet route that must traverse every link exactly once.
 */
public class Problem08_ReconstructItinerary {
    
    public List<String> findItinerary(List<List<String>> tickets) {
        Map<String, PriorityQueue<String>> graph = new HashMap<>();
        for (List<String> t : tickets)
            graph.computeIfAbsent(t.get(0), k -> new PriorityQueue<>()).offer(t.get(1));
        LinkedList<String> result = new LinkedList<>();
        dfs(graph, "JFK", result);
        return result;
    }
    
    private void dfs(Map<String, PriorityQueue<String>> graph, String airport, LinkedList<String> result) {
        PriorityQueue<String> pq = graph.get(airport);
        while (pq != null && !pq.isEmpty())
            dfs(graph, pq.poll(), result);
        result.addFirst(airport);
    }
    
    public static void main(String[] args) {
        Problem08_ReconstructItinerary sol = new Problem08_ReconstructItinerary();
        List<List<String>> t1 = Arrays.asList(Arrays.asList("MUC","LHR"), Arrays.asList("JFK","MUC"), Arrays.asList("SFO","SJC"), Arrays.asList("LHR","SFO"));
        System.out.println(sol.findItinerary(t1)); // [JFK, MUC, LHR, SFO, SJC]
        List<List<String>> t2 = Arrays.asList(Arrays.asList("JFK","SFO"), Arrays.asList("JFK","ATL"), Arrays.asList("SFO","ATL"), Arrays.asList("ATL","JFK"), Arrays.asList("ATL","SFO"));
        System.out.println(sol.findItinerary(t2)); // [JFK, ATL, JFK, SFO, ATL, SFO]
    }
}
