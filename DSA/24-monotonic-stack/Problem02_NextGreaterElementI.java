import java.util.*;

/**
 * Problem 2: Next Greater Element I (LeetCode 496)
 * 
 * Given two arrays nums1 (subset of nums2), find next greater element for each nums1[i] in nums2.
 * 
 * Monotonic Invariant: Decreasing stack on nums2. When a greater element arrives,
 * pop and map each popped element to the greater element.
 * 
 * Time: O(n + m), Space: O(n)
 * 
 * Production Analogy: Like a stock ticker - for each watched stock, find the next
 * time any stock in the stream exceeds its price.
 */
public class Problem02_NextGreaterElementI {
    
    public int[] nextGreaterElement(int[] nums1, int[] nums2) {
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
        Problem02_NextGreaterElementI sol = new Problem02_NextGreaterElementI();
        
        System.out.println(Arrays.toString(sol.nextGreaterElement(new int[]{4,1,2}, new int[]{1,3,4,2})));
        // Expected: [-1,3,-1]
        
        System.out.println(Arrays.toString(sol.nextGreaterElement(new int[]{2,4}, new int[]{1,2,3,4})));
        // Expected: [3,-1]
        
        System.out.println(Arrays.toString(sol.nextGreaterElement(new int[]{1}, new int[]{1})));
        // Expected: [-1]
    }
}
