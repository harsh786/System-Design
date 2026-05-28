import java.util.*;

/**
 * Problem 11: Ugly Number II (LeetCode 264)
 * 
 * Approach: Min-heap generating ugly numbers by multiplying by 2,3,5. Use set to deduplicate.
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Generating sorted composite keys/IDs from multiple base factors
 * for distributed ID generation systems.
 */
public class Problem11_UglyNumberII {
    
    public int nthUglyNumber(int n) {
        PriorityQueue<Long> minHeap = new PriorityQueue<>();
        Set<Long> seen = new HashSet<>();
        minHeap.offer(1L);
        seen.add(1L);
        
        long result = 1;
        for (int i = 0; i < n; i++) {
            result = minHeap.poll();
            for (long factor : new long[]{2, 3, 5}) {
                long next = result * factor;
                if (seen.add(next)) minHeap.offer(next);
            }
        }
        return (int) result;
    }
    
    public static void main(String[] args) {
        Problem11_UglyNumberII sol = new Problem11_UglyNumberII();
        System.out.println(sol.nthUglyNumber(10)); // 12
        System.out.println(sol.nthUglyNumber(1));  // 1
        System.out.println(sol.nthUglyNumber(15)); // 24
    }
}
