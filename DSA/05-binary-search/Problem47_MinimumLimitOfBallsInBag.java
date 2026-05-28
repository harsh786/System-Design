/**
 * Problem 47: Minimum Limit of Balls in a Bag
 * 
 * Can split bags. Given maxOperations, minimize the maximum bag size.
 * 
 * Approach: Binary search on answer [1, max]. For each bag, splits needed = ceil(bag/mid)-1.
 * 
 * Time: O(n * log(max)), Space: O(1)
 * 
 * Production Analogy: Splitting oversized message queues into partitions
 * with limited operations to minimize max partition backlog.
 */
public class Problem47_MinimumLimitOfBallsInBag {
    public static int minimumSize(int[] nums, int maxOperations) {
        int lo = 1, hi = 0;
        for (int n : nums) hi = Math.max(hi, n);
        
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            long ops = 0;
            for (int n : nums) ops += (n - 1) / mid; // ceil(n/mid) - 1
            if (ops <= maxOperations) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    public static void main(String[] args) {
        System.out.println(minimumSize(new int[]{9}, 2));          // 3
        System.out.println(minimumSize(new int[]{2,4,8,2}, 4));    // 2
        System.out.println(minimumSize(new int[]{7,17}, 2));       // 7
    }
}
