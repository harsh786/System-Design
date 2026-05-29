/**
 * Problem 40: Smallest Good Base
 * For number n (string), find smallest base k where n = 1 + k + k^2 + ... + k^m.
 *
 * Approach: For each possible length m (from max to min), binary search for k.
 * n = (k^(m+1) - 1) / (k - 1). Max m is log2(n).
 * Time Complexity: O(log^2(n))
 * Space Complexity: O(1)
 *
 * Production Analogy: Like finding optimal radix for number representation
 * in compression algorithms.
 */
public class Problem40_SmallestGoodBase {

    public static String smallestGoodBase(String n) {
        long num = Long.parseLong(n);
        // Try from longest representation (smallest base) to shortest
        for (int m = (int) (Math.log(num) / Math.log(2)); m >= 2; m--) {
            long lo = 2, hi = (long) Math.pow(num, 1.0 / m) + 1;
            while (lo <= hi) {
                long mid = lo + (hi - lo) / 2;
                long sum = 0, cur = 1;
                for (int i = 0; i <= m; i++) {
                    sum += cur;
                    if (sum > num) break;
                    cur *= mid;
                }
                if (sum == num) return String.valueOf(mid);
                else if (sum < num) lo = mid + 1;
                else hi = mid - 1;
            }
        }
        return String.valueOf(num - 1); // base (n-1), representation "11"
    }

    public static void main(String[] args) {
        System.out.println(smallestGoodBase("13"));          // "3" (1+3+9=13)
        System.out.println(smallestGoodBase("4681"));        // "8"
        System.out.println(smallestGoodBase("1000000000000000000")); // "999999999999999999"
    }
}
