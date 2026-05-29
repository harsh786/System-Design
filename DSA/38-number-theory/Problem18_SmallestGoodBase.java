package numbertheory;

/**
 * Problem 18: Smallest Good Base (LeetCode 483)
 * 
 * Approach: n = 1 + k + k^2 + ... + k^(m-1) for some base k and length m.
 * Try m from large to small (max m = log2(n)), binary search for k.
 * 
 * Time Complexity: O(log^2 n)
 * Space Complexity: O(1)
 */
public class Problem18_SmallestGoodBase {
    
    public String smallestGoodBase(String n) {
        long num = Long.parseLong(n);
        for (int m = 63; m >= 2; m--) {
            long k = (long) Math.pow(num, 1.0 / (m - 1));
            if (k <= 1) continue;
            long sum = 0, cur = 1;
            for (int i = 0; i < m; i++) { sum += cur; cur *= k; }
            if (sum == num) return Long.toString(k);
        }
        return Long.toString(num - 1);
    }
    
    public static void main(String[] args) {
        Problem18_SmallestGoodBase sol = new Problem18_SmallestGoodBase();
        System.out.println(sol.smallestGoodBase("13"));  // 3 (111 in base 3)
        System.out.println(sol.smallestGoodBase("4681")); // 8
    }
}
