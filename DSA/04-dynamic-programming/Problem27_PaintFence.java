/**
 * Problem 27: Paint Fence
 * 
 * n posts, k colors. No more than 2 adjacent posts same color.
 * 
 * State: same = ways where last two are same color, diff = ways where different
 * same[i] = diff[i-1] (can only repeat if previous two were different)
 * diff[i] = (same[i-1] + diff[i-1]) * (k-1)
 * 
 * Time: O(n), Space: O(1)
 */
public class Problem27_PaintFence {

    public static int numWays(int n, int k) {
        if (n == 0) return 0;
        if (n == 1) return k;
        int same = k, diff = k * (k - 1);
        for (int i = 3; i <= n; i++) {
            int newSame = diff;
            int newDiff = (same + diff) * (k - 1);
            same = newSame;
            diff = newDiff;
        }
        return same + diff;
    }

    public static void main(String[] args) {
        System.out.println("=== Paint Fence ===");
        System.out.println(numWays(3, 2)); // 6
        System.out.println(numWays(1, 1)); // 1
        System.out.println(numWays(7, 2)); // 42
    }
}
