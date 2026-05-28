import java.util.*;

/**
 * Problem 14: Next Greater Element I (LeetCode 496)
 * 
 * Given nums1 (subset of nums2), find next greater element for each nums1[i] in nums2.
 * 
 * Approach: Build a map of next greater elements for all elements in nums2 using
 * monotonic stack, then look up for nums1.
 * 
 * Time Complexity: O(n + m) where n = nums2.length, m = nums1.length
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like precomputing "next available upgrade" for each service tier,
 * then answering customer queries in O(1).
 */
public class Problem14_NextGreaterElementI {

    public static int[] nextGreaterElement(int[] nums1, int[] nums2) {
        Map<Integer, Integer> map = new HashMap<>();
        Deque<Integer> stack = new ArrayDeque<>();
        for (int num : nums2) {
            while (!stack.isEmpty() && stack.peek() < num) {
                map.put(stack.pop(), num);
            }
            stack.push(num);
        }
        int[] result = new int[nums1.length];
        for (int i = 0; i < nums1.length; i++) {
            result[i] = map.getOrDefault(nums1[i], -1);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(nextGreaterElement(new int[]{4,1,2}, new int[]{1,3,4,2}))); // [-1,3,-1]
        System.out.println(Arrays.toString(nextGreaterElement(new int[]{2,4}, new int[]{1,2,3,4}))); // [3,-1]
    }
}
