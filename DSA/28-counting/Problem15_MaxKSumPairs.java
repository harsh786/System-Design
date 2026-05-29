/**
 * Problem: Max Number of K-Sum Pairs (LeetCode 1679)
 * Approach: HashMap counting complements
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Matching engine in trading systems (buy/sell order pairing)
 */
import java.util.*;
public class Problem15_MaxKSumPairs {
    public int maxOperations(int[] nums, int k) {
        Map<Integer, Integer> map = new HashMap<>();
        int count = 0;
        for (int n : nums) {
            int comp = k - n;
            if (map.getOrDefault(comp, 0) > 0) { count++; map.merge(comp, -1, Integer::sum); }
            else map.merge(n, 1, Integer::sum);
        }
        return count;
    }
    public static void main(String[] args) {
        System.out.println(new Problem15_MaxKSumPairs().maxOperations(new int[]{1,2,3,4}, 5)); // 2
    }
}
