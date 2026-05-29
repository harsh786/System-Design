/**
 * Problem: Count Elements With Maximum Frequency (LeetCode 3005)
 * Approach: Count frequencies, sum elements with max frequency
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Identifying dominant categories in analytics
 */
import java.util.*;
public class Problem46_CountElementsWithMaxFrequency {
    public int maxFrequencyElements(int[] nums) {
        Map<Integer, Integer> freq = new HashMap<>();
        int maxFreq = 0;
        for (int n : nums) { int f = freq.merge(n, 1, Integer::sum); maxFreq = Math.max(maxFreq, f); }
        int count = 0;
        for (int f : freq.values()) if (f == maxFreq) count += f;
        return count;
    }
    public static void main(String[] args) {
        System.out.println(new Problem46_CountElementsWithMaxFrequency()
            .maxFrequencyElements(new int[]{1,2,2,3,1,4})); // 4
    }
}
