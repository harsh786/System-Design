package numbertheory;

/**
 * Problem 3: Ugly Number II (LeetCode 264)
 * 
 * Approach: Three-pointer DP. Maintain pointers for multiples of 2, 3, 5.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 */
public class Problem03_UglyNumberII {
    
    public int nthUglyNumber(int n) {
        int[] ugly = new int[n];
        ugly[0] = 1;
        int p2 = 0, p3 = 0, p5 = 0;
        for (int i = 1; i < n; i++) {
            int next = Math.min(ugly[p2] * 2, Math.min(ugly[p3] * 3, ugly[p5] * 5));
            ugly[i] = next;
            if (next == ugly[p2] * 2) p2++;
            if (next == ugly[p3] * 3) p3++;
            if (next == ugly[p5] * 5) p5++;
        }
        return ugly[n - 1];
    }
    
    public static void main(String[] args) {
        Problem03_UglyNumberII sol = new Problem03_UglyNumberII();
        System.out.println(sol.nthUglyNumber(10)); // 12
    }
}
