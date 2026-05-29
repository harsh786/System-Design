/**
 * Problem: Number of Recent Calls (LeetCode 933)
 * Approach: Queue-based sliding window simulation
 * Complexity: O(1) amortized per call
 * Production Analogy: Sliding window rate counter for API monitoring
 */
import java.util.*;
public class Problem10_NumberOfRecentCalls {
    Queue<Integer> q = new LinkedList<>();
    public int ping(int t) {
        q.offer(t);
        while (q.peek() < t - 3000) q.poll();
        return q.size();
    }
    public static void main(String[] args) {
        Problem10_NumberOfRecentCalls rc = new Problem10_NumberOfRecentCalls();
        System.out.println(rc.ping(1));    // 1
        System.out.println(rc.ping(100));  // 2
        System.out.println(rc.ping(3001)); // 3
        System.out.println(rc.ping(3002)); // 3
    }
}
