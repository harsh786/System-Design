import java.util.*;

/**
 * Problem 24: Intersection of Two Arrays II
 * Return intersection including duplicates.
 *
 * Time Complexity: O(n + m)
 * Space Complexity: O(min(n, m))
 *
 * Production Analogy: Like matching supply and demand - each unit of supply
 * can only satisfy one unit of demand.
 */
public class Problem24_IntersectionOfTwoArraysII {
    public int[] intersect(int[] nums1, int[] nums2) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int n : nums1) map.merge(n, 1, Integer::sum);
        List<Integer> result = new ArrayList<>();
        for (int n : nums2) {
            if (map.getOrDefault(n, 0) > 0) {
                result.add(n);
                map.merge(n, -1, Integer::sum);
            }
        }
        return result.stream().mapToInt(Integer::intValue).toArray();
    }

    public static void main(String[] args) {
        Problem24_IntersectionOfTwoArraysII sol = new Problem24_IntersectionOfTwoArraysII();
        System.out.println(Arrays.toString(sol.intersect(new int[]{1,2,2,1}, new int[]{2,2}))); // [2,2]
        System.out.println(Arrays.toString(sol.intersect(new int[]{4,9,5}, new int[]{9,4,9,8,4}))); // [4,9]
    }
}
