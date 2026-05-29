import java.util.*;

/**
 * Problem 7: Longest Cycle in a Graph (LeetCode 2360)
 * 
 * Given a directed graph where each node has at most one outgoing edge,
 * return the length of the longest cycle. Return -1 if no cycle.
 * 
 * Since each node has at most one outgoing edge (functional graph),
 * the structure is a collection of "rho"-shaped components (tail + cycle).
 * 
 * Approach: DFS with timestamping to detect and measure cycles.
 * Time: O(n), Space: O(n)
 */
public class Problem07_LongestCycle {

    public static int longestCycle(int[] edges) {
        int n = edges.length;
        int[] visited = new int[n]; // 0=unvisited, -1=done, >0=timestamp
        int longest = -1;
        int time = 1;
        
        for (int i = 0; i < n; i++) {
            if (visited[i] != 0) continue;
            
            int startTime = time;
            int curr = i;
            
            // Follow the path, marking with current timestamp
            while (curr != -1 && visited[curr] == 0) {
                visited[curr] = time++;
                curr = edges[curr];
            }
            
            // If we hit a node visited in THIS traversal, we found a cycle
            if (curr != -1 && visited[curr] >= startTime) {
                int cycleLen = time - visited[curr];
                longest = Math.max(longest, cycleLen);
            }
            
            // Mark all nodes in this traversal as done
            curr = i;
            while (curr != -1 && visited[curr] != -1 && visited[curr] >= startTime) {
                int next = edges[curr];
                visited[curr] = -1;
                curr = next;
            }
        }
        return longest;
    }

    public static void main(String[] args) {
        // Example 1: edges[i] = next node from i, -1 = no outgoing
        int[] edges1 = {3, 3, 4, 2, 3};
        // 0->3->2->4->3 (cycle: 3->2->4->3, length 3)
        System.out.println("LeetCode 2360: Longest Cycle");
        System.out.println("edges = " + Arrays.toString(edges1));
        System.out.println("Longest cycle: " + longestCycle(edges1)); // 3

        int[] edges2 = {2, -1, 3, 1};
        // 0->2->3->1 (no cycle since 1->-1)
        System.out.println("\nedges = " + Arrays.toString(edges2));
        System.out.println("Longest cycle: " + longestCycle(edges2)); // -1

        // Functional graph with multiple cycles
        int[] edges3 = {1, 2, 0, 4, 5, 3, 7, 8, 6};
        // Cycle 0->1->2->0 (len 3), Cycle 3->4->5->3 (len 3), Cycle 6->7->8->6 (len 3)
        System.out.println("\nedges = " + Arrays.toString(edges3));
        System.out.println("Longest cycle: " + longestCycle(edges3)); // 3
    }
}
