/**
 * Problem: Number of Good Pairs (LeetCode 1512)
 * Approach: For each number, count of pairs = count*(count-1)/2
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Combinatorial counting for recommendation pair generation
 */
import java.util.*;
public class Problem13_NumberOfGoodPairs {
    public int numIdenticalPairs(int[] nums) {
        Map<Integer, Integer> count = new HashMap<>();
        int pairs = 0;
        for (int n : nums) {
            int c = count.getOrDefault(n, 0);
            pairs += c;
            count.put(n, c+1);
        }
        return pairs;
    }
    public static void main(String[] args) {
        System.out.println(new Problem13_NumberOfGoodPairs().numIdenticalPairs(new int[]{1,2,3,1,1,3})); // 4
    }
}
