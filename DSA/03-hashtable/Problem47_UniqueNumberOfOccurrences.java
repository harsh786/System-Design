import java.util.*;

/**
 * Problem 47: Unique Number of Occurrences
 * Return true if the number of occurrences of each value is unique.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like validating that each priority level in a task queue
 * has a unique number of assigned workers (no resource contention).
 */
public class Problem47_UniqueNumberOfOccurrences {
    public boolean uniqueOccurrences(int[] arr) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : arr) freq.merge(n, 1, Integer::sum);
        return freq.size() == new HashSet<>(freq.values()).size();
    }

    public static void main(String[] args) {
        Problem47_UniqueNumberOfOccurrences sol = new Problem47_UniqueNumberOfOccurrences();
        System.out.println(sol.uniqueOccurrences(new int[]{1,2,2,1,1,3})); // true
        System.out.println(sol.uniqueOccurrences(new int[]{1,2})); // false
        System.out.println(sol.uniqueOccurrences(new int[]{-3,0,1,-3,1,1,1,-3,10,0})); // true
    }
}
