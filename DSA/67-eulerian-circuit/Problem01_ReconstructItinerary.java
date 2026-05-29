import java.util.*;

/**
 * Problem 1: Reconstruct Itinerary (LeetCode 332) - Hierholzer's Algorithm
 * 
 * Given a list of airline tickets [from, to], reconstruct the itinerary in order.
 * Start from "JFK". If multiple valid itineraries, return lexicographically smallest.
 * 
 * This is finding an Eulerian path in a directed graph.
 * Hierholzer's Algorithm:
 * 1. Start from source, greedily follow edges (deleting them)
 * 2. When stuck (no outgoing edges), add current node to result (backtrack)
 * 3. Reverse the result
 * 
 * Time: O(E log E) for sorting, O(E) for traversal
 * Space: O(E)
 */
public class Problem01_ReconstructItinerary {

    public static List<String> findItinerary(List<List<String>> tickets) {
        // Build adjacency list with sorted destinations (for lexicographic order)
        Map<String, PriorityQueue<String>> graph = new HashMap<>();
        for (List<String> ticket : tickets) {
            graph.computeIfAbsent(ticket.get(0), k -> new PriorityQueue<>()).add(ticket.get(1));
        }
        
        LinkedList<String> result = new LinkedList<>();
        dfs("JFK", graph, result);
        return result;
    }

    private static void dfs(String airport, Map<String, PriorityQueue<String>> graph, 
                           LinkedList<String> result) {
        PriorityQueue<String> destinations = graph.get(airport);
        while (destinations != null && !destinations.isEmpty()) {
            String next = destinations.poll();
            dfs(next, graph, result);
        }
        result.addFirst(airport); // Add to front when stuck (post-order)
    }

    // Iterative version using explicit stack
    public static List<String> findItineraryIterative(List<List<String>> tickets) {
        Map<String, PriorityQueue<String>> graph = new HashMap<>();
        for (List<String> ticket : tickets) {
            graph.computeIfAbsent(ticket.get(0), k -> new PriorityQueue<>()).add(ticket.get(1));
        }
        
        LinkedList<String> result = new LinkedList<>();
        Deque<String> stack = new ArrayDeque<>();
        stack.push("JFK");
        
        while (!stack.isEmpty()) {
            String curr = stack.peek();
            PriorityQueue<String> dests = graph.get(curr);
            if (dests != null && !dests.isEmpty()) {
                stack.push(dests.poll());
            } else {
                result.addFirst(stack.pop());
            }
        }
        return result;
    }

    public static void main(String[] args) {
        // Example 1
        List<List<String>> tickets1 = Arrays.asList(
            Arrays.asList("MUC", "LHR"), Arrays.asList("JFK", "MUC"),
            Arrays.asList("SFO", "SJC"), Arrays.asList("LHR", "SFO"));
        System.out.println("Test 1: " + findItinerary(tickets1));
        // Expected: [JFK, MUC, LHR, SFO, SJC]

        // Example 2 - multiple valid paths, choose lexicographic
        List<List<String>> tickets2 = Arrays.asList(
            Arrays.asList("JFK", "SFO"), Arrays.asList("JFK", "ATL"),
            Arrays.asList("SFO", "ATL"), Arrays.asList("ATL", "JFK"),
            Arrays.asList("ATL", "SFO"));
        System.out.println("Test 2: " + findItinerary(tickets2));
        // Expected: [JFK, ATL, JFK, SFO, ATL, SFO]

        // Iterative version
        System.out.println("Test 2 (iterative): " + findItineraryIterative(tickets2));
    }
}
