/**
 * Problem: Count Good Meals (LeetCode 1711)
 * Approach: For each element check all powers of 2 as target sum
 * Complexity: O(n * 22) time, O(n) space
 * Production Analogy: Finding complementary pairs in matching systems
 */
import java.util.*;
public class Problem38_CountGoodMeals {
    public int countPairs(int[] deliciousness) {
        Map<Integer, Integer> map = new HashMap<>();
        int MOD = 1_000_000_007;
        long count = 0;
        for (int d : deliciousness) {
            for (int i = 0; i <= 21; i++) {
                int target = (1 << i) - d;
                count += map.getOrDefault(target, 0);
            }
            map.merge(d, 1, Integer::sum);
        }
        return (int)(count % MOD);
    }
    public static void main(String[] args) {
        System.out.println(new Problem38_CountGoodMeals().countPairs(new int[]{1,3,5,7,9})); // 4
    }
}
