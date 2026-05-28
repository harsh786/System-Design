import java.util.*;

/**
 * Problem 23: Intersection of Two Arrays
 * Return unique intersection elements.
 *
 * Time Complexity: O(n + m)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like finding common users between two feature flag groups
 * for A/B test overlap analysis.
 */
public class Problem23_IntersectionOfTwoArrays {
    public int[] intersection(int[] nums1, int[] nums2) {
        Set<Integer> set = new HashSet<>(), result = new HashSet<>();
        for (int n : nums1) set.add(n);
        for (int n : nums2) if (set.contains(n)) result.add(n);
        return result.stream().mapToInt(Integer::intValue).toArray();
    }

    public static void main(String[] args) {
        Problem23_IntersectionOfTwoArrays sol = new Problem23_IntersectionOfTwoArrays();
        System.out.println(Arrays.toString(sol.intersection(new int[]{1,2,2,1}, new int[]{2,2}))); // [2]
        System.out.println(Arrays.toString(sol.intersection(new int[]{4,9,5}, new int[]{9,4,9,8,4}))); // [4,9]
    }
}
