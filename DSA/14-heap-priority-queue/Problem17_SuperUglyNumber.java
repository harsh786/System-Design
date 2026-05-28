import java.util.*;

/**
 * Problem 17: Super Ugly Number (LeetCode 313)
 * 
 * Approach: Min-heap with pointers for each prime factor.
 * 
 * Time Complexity: O(N * K log K) where K = number of primes
 * Space Complexity: O(N + K)
 * 
 * Production Analogy: Generating sorted merge of multiple arithmetic sequences,
 * useful in distributed scheduling of periodic tasks with different intervals.
 */
public class Problem17_SuperUglyNumber {
    
    public int nthSuperUglyNumber(int n, int[] primes) {
        long[] ugly = new long[n];
        ugly[0] = 1;
        int[] idx = new int[primes.length];
        
        // min-heap: [value, primeIndex]
        PriorityQueue<long[]> pq = new PriorityQueue<>((a, b) -> Long.compare(a[0], b[0]));
        for (int i = 0; i < primes.length; i++) pq.offer(new long[]{primes[i], i});
        
        for (int i = 1; i < n; i++) {
            ugly[i] = pq.peek()[0];
            while (pq.peek()[0] == ugly[i]) {
                long[] top = pq.poll();
                int pi = (int) top[1];
                idx[pi]++;
                pq.offer(new long[]{ugly[idx[pi]] * primes[pi], pi});
            }
        }
        return (int) ugly[n - 1];
    }
    
    public static void main(String[] args) {
        Problem17_SuperUglyNumber sol = new Problem17_SuperUglyNumber();
        System.out.println(sol.nthSuperUglyNumber(12, new int[]{2, 7, 13, 19})); // 32
        System.out.println(sol.nthSuperUglyNumber(1, new int[]{2, 3, 5})); // 1
    }
}
