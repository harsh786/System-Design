/**
 * Problem: Unique Number of Occurrences (LeetCode 1207)
 * Approach: Count frequencies, check uniqueness with set
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Validating distribution uniqueness in load balancing
 */
import java.util.*;
public class Problem24_UniqueNumberOfOccurrences {
    public boolean uniqueOccurrences(int[] arr) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : arr) freq.merge(n, 1, Integer::sum);
        return freq.size() == new HashSet<>(freq.values()).size();
    }
    public static void main(String[] args) {
        System.out.println(new Problem24_UniqueNumberOfOccurrences().uniqueOccurrences(new int[]{1,2,2,1,1,3})); // true
    }
}
