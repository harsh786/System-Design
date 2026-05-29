/**
 * Problem: Intersection of Two Arrays II (LeetCode 350)
 * Approach: Count elements in smaller array, match against larger
 * Complexity: O(m+n) time, O(min(m,n)) space
 * Production Analogy: Finding common items between two datasets (join operation)
 */
import java.util.*;
public class Problem10_IntersectionOfTwoArraysII {
    public int[] intersect(int[] nums1, int[] nums2) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int n : nums1) map.merge(n, 1, Integer::sum);
        List<Integer> res = new ArrayList<>();
        for (int n : nums2) {
            if (map.getOrDefault(n, 0) > 0) { res.add(n); map.merge(n, -1, Integer::sum); }
        }
        return res.stream().mapToInt(Integer::intValue).toArray();
    }
    public static void main(String[] args) {
        System.out.println(Arrays.toString(new Problem10_IntersectionOfTwoArraysII()
            .intersect(new int[]{1,2,2,1}, new int[]{2,2}))); // [2,2]
    }
}
