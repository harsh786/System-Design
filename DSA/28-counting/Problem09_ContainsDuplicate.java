/**
 * Problem: Contains Duplicate (LeetCode 217)
 * Approach: HashSet for seen elements
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Duplicate detection in event processing pipelines
 */
import java.util.*;
public class Problem09_ContainsDuplicate {
    public boolean containsDuplicate(int[] nums) {
        Set<Integer> seen = new HashSet<>();
        for (int n : nums) if (!seen.add(n)) return true;
        return false;
    }
    public static void main(String[] args) {
        System.out.println(new Problem09_ContainsDuplicate().containsDuplicate(new int[]{1,2,3,1})); // true
    }
}
