import java.util.*;

/**
 * Problem 3: Contains Duplicate
 * Return true if any value appears at least twice.
 * 
 * Production Analogy: Duplicate request detection in an API gateway - 
 * use a Set to track seen request IDs.
 * 
 * Brute Force: O(n^2) - compare all pairs
 * Optimal: O(n) time, O(n) space - HashSet
 */
public class Problem03_ContainsDuplicate {

    public static boolean containsDuplicate(int[] nums) {
        Set<Integer> seen = new HashSet<>();
        for (int n : nums) if (!seen.add(n)) return true;
        return false;
    }

    public static void main(String[] args) {
        System.out.println(containsDuplicate(new int[]{1,2,3,1}));   // true
        System.out.println(containsDuplicate(new int[]{1,2,3,4}));   // false
        System.out.println(containsDuplicate(new int[]{1,1,1,3,3})); // true
        System.out.println(containsDuplicate(new int[]{}));           // false
    }
}
