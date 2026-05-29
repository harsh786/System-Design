import java.util.*;

/**
 * Problem 4: Valid Arrangement of Pairs (LeetCode 2097)
 * 
 * Given 0-indexed 2D array pairs where pairs[i] = [start_i, end_i],
 * arrange pairs such that end_i-1 == start_i for each consecutive pair.
 * 
 * This is finding an Eulerian path in a directed graph where:
 * - Each pair [a, b] is an edge from a to b
 * - We need to find a path that uses all edges exactly once
 * 
 * Time: O(V + E), Space: O(V + E)
 */
public class Problem04_ValidArrangementOfPairs {

    public static int[][] validArrangement(int[][] pairs) {
        // Build graph
        Map<Integer, Deque<Integer>> graph = new HashMap<>();
        Map<Integer, Integer> inDeg = new HashMap<>();
        Map<Integer, Integer> outDeg = new HashMap<>();
        
        for (int[] pair : pairs) {
            graph.computeIfAbsent(pair[0], k -> new ArrayDeque<>()).add(pair[1]);
            outDeg.merge(pair[0], 1, Integer::sum);
            inDeg.merge(pair[1], 1, Integer::sum);
        }
        
        // Find start node (outDegree - inDegree == 1), or any node if Eulerian circuit
        int startNode = pairs[0][0];
        for (int node : outDeg.keySet()) {
            if (outDeg.getOrDefault(node, 0) - inDeg.getOrDefault(node, 0) == 1) {
                startNode = node;
                break;
            }
        }
        
        // Hierholzer's algorithm
        LinkedList<Integer> path = new LinkedList<>();
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(startNode);
        
        while (!stack.isEmpty()) {
            int curr = stack.peek();
            Deque<Integer> neighbors = graph.getOrDefault(curr, new ArrayDeque<>());
            if (!neighbors.isEmpty()) {
                stack.push(neighbors.poll());
            } else {
                path.addFirst(stack.pop());
            }
        }
        
        // Convert path to pairs
        int[][] result = new int[pairs.length][2];
        Iterator<Integer> it = path.iterator();
        int prev = it.next();
        int idx = 0;
        while (it.hasNext()) {
            int curr = it.next();
            result[idx++] = new int[]{prev, curr};
            prev = curr;
        }
        return result;
    }

    public static void main(String[] args) {
        // Example 1
        int[][] pairs1 = {{5,1},{4,5},{11,9},{9,4}};
        int[][] result1 = validArrangement(pairs1);
        System.out.println("Input: " + Arrays.deepToString(pairs1));
        System.out.println("Output: " + Arrays.deepToString(result1));
        // Verify chaining
        for (int i = 1; i < result1.length; i++) {
            assert result1[i-1][1] == result1[i][0] : "Chain broken!";
        }
        System.out.println("Valid chain: YES\n");

        // Example 2
        int[][] pairs2 = {{1,3},{3,2},{2,1}};
        int[][] result2 = validArrangement(pairs2);
        System.out.println("Input: " + Arrays.deepToString(pairs2));
        System.out.println("Output: " + Arrays.deepToString(result2));
    }
}
