/**
 * Problem 44: Painter's Partition Problem
 * Minimize the maximum time any painter spends (binary search on answer).
 * 
 * D&C / Binary Search on Answer:
 * - DIVIDE: Binary search on the maximum allowed sum per partition
 * - CONQUER: For each candidate max-sum, greedily check if k painters suffice
 * - No explicit combine - binary search converges to optimal answer
 * 
 * Time: O(n * log(sum)), Space: O(1)
 * 
 * Production Analogy:
 * - Load balancing: minimize maximum load across k servers
 * - Parallel job scheduling: minimize makespan
 * - Splitting data across workers in MapReduce for balanced processing
 * - Kubernetes pod resource allocation
 */
public class Problem44_PaintersPartitionProblem {

    public static long minTime(int[] boards, int k) {
        long lo = 0, hi = 0;
        for (int b : boards) { lo = Math.max(lo, b); hi += b; }
        
        while (lo < hi) {
            long mid = lo + (hi - lo) / 2;
            if (canPaint(boards, k, mid)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    private static boolean canPaint(int[] boards, int k, long maxTime) {
        int painters = 1;
        long currentSum = 0;
        for (int b : boards) {
            if (currentSum + b > maxTime) {
                painters++;
                currentSum = b;
                if (painters > k) return false;
            } else {
                currentSum += b;
            }
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(minTime(new int[]{10, 20, 30, 40}, 2)); // 60
        System.out.println(minTime(new int[]{10, 10, 10, 10}, 2)); // 20
        System.out.println(minTime(new int[]{100, 200, 300, 400, 500}, 3)); // 500? No: [100,200,300],[400],[500] = 600
        System.out.println(minTime(new int[]{5, 10, 30, 20, 15}, 3)); // 35
        System.out.println(minTime(new int[]{1, 2, 3, 4, 5}, 1)); // 15
    }
}
