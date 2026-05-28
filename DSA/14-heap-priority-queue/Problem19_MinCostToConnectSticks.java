import java.util.*;

/**
 * Problem 19: Minimum Cost to Connect Sticks (LeetCode 1167)
 * 
 * Approach: Min-heap. Always merge two smallest sticks (Huffman coding idea).
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Optimal merge of sorted files/partitions - minimizing total
 * I/O cost when merging multiple data segments in a database compaction.
 */
public class Problem19_MinCostToConnectSticks {
    
    public int connectSticks(int[] sticks) {
        PriorityQueue<Integer> pq = new PriorityQueue<>();
        for (int s : sticks) pq.offer(s);
        
        int cost = 0;
        while (pq.size() > 1) {
            int sum = pq.poll() + pq.poll();
            cost += sum;
            pq.offer(sum);
        }
        return cost;
    }
    
    public static void main(String[] args) {
        Problem19_MinCostToConnectSticks sol = new Problem19_MinCostToConnectSticks();
        System.out.println(sol.connectSticks(new int[]{2, 4, 3})); // 14
        System.out.println(sol.connectSticks(new int[]{1, 8, 3, 5})); // 30
        System.out.println(sol.connectSticks(new int[]{5})); // 0
    }
}
