import java.util.*;

/**
 * Problem 24: Create Maximum Number (LeetCode 321)
 * 
 * Pick k digits from two arrays to form maximum number, preserving relative order.
 * 
 * Approach: For each split (i from nums1, k-i from nums2), find max subsequence
 * of length i from nums1 and k-i from nums2 using monotonic stack, then merge.
 * 
 * Monotonic Invariant: Decreasing stack with remaining capacity constraint.
 * 
 * Time: O(k * (m+n)), Space: O(k)
 * 
 * Production Analogy: Merging priority queues from multiple sources to form
 * the highest-priority combined sequence.
 */
public class Problem24_CreateMaximumNumber {
    
    public int[] maxNumber(int[] nums1, int[] nums2, int k) {
        int m = nums1.length, n = nums2.length;
        int[] best = new int[k];
        
        for (int i = Math.max(0, k - n); i <= Math.min(k, m); i++) {
            int[] sub1 = maxSubsequence(nums1, i);
            int[] sub2 = maxSubsequence(nums2, k - i);
            int[] merged = merge(sub1, sub2);
            if (compare(merged, 0, best, 0) > 0) best = merged;
        }
        return best;
    }
    
    private int[] maxSubsequence(int[] nums, int k) {
        int[] stack = new int[k];
        int top = -1;
        int remain = nums.length;
        for (int num : nums) {
            while (top >= 0 && stack[top] < num && top + 1 + remain - 1 >= k) top--;
            if (top < k - 1) stack[++top] = num;
            remain--;
        }
        return stack;
    }
    
    private int[] merge(int[] a, int[] b) {
        int[] result = new int[a.length + b.length];
        int i = 0, j = 0, k = 0;
        while (i < a.length && j < b.length) {
            result[k++] = compare(a, i, b, j) >= 0 ? a[i++] : b[j++];
        }
        while (i < a.length) result[k++] = a[i++];
        while (j < b.length) result[k++] = b[j++];
        return result;
    }
    
    private int compare(int[] a, int i, int[] b, int j) {
        while (i < a.length && j < b.length) {
            if (a[i] != b[j]) return a[i] - b[j];
            i++; j++;
        }
        return (a.length - i) - (b.length - j);
    }
    
    public static void main(String[] args) {
        Problem24_CreateMaximumNumber sol = new Problem24_CreateMaximumNumber();
        
        System.out.println(Arrays.toString(sol.maxNumber(new int[]{3,4,6,5}, new int[]{9,1,2,5,8,3}, 5)));
        // [9,8,6,5,3]
        
        System.out.println(Arrays.toString(sol.maxNumber(new int[]{6,7}, new int[]{6,0,4}, 5)));
        // [6,7,6,0,4]
        
        System.out.println(Arrays.toString(sol.maxNumber(new int[]{3,9}, new int[]{8,9}, 3)));
        // [9,8,9]
    }
}
