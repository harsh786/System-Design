/**
 * Problem 50: Create Maximum Number (LeetCode 321)
 *
 * Greedy Choice: For each split (i from nums1, k-i from nums2), find max subsequence 
 * of each length, then merge greedily picking the lexicographically larger.
 *
 * Time: O(k * (m + n + k)), Space: O(k)
 *
 * Production Analogy: Merging two priority streams to form maximum combined priority sequence.
 */
public class Problem50_CreateMaximumNumber {
    
    public static int[] maxNumber(int[] nums1, int[] nums2, int k) {
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
    
    private static int[] maxSubsequence(int[] nums, int k) {
        int[] stack = new int[k];
        int top = -1, drop = nums.length - k;
        for (int num : nums) {
            while (top >= 0 && stack[top] < num && drop > 0) { top--; drop--; }
            if (top < k - 1) stack[++top] = num;
            else drop--;
        }
        return stack;
    }
    
    private static int[] merge(int[] a, int[] b) {
        int[] res = new int[a.length + b.length];
        int i = 0, j = 0, idx = 0;
        while (i < a.length && j < b.length) {
            res[idx++] = compare(a, i, b, j) >= 0 ? a[i++] : b[j++];
        }
        while (i < a.length) res[idx++] = a[i++];
        while (j < b.length) res[idx++] = b[j++];
        return res;
    }
    
    private static int compare(int[] a, int i, int[] b, int j) {
        while (i < a.length && j < b.length) {
            if (a[i] != b[j]) return a[i] - b[j];
            i++; j++;
        }
        return (a.length - i) - (b.length - j);
    }
    
    public static void main(String[] args) {
        int[] res1 = maxNumber(new int[]{3,4,6,5}, new int[]{9,1,2,5,8,3}, 5);
        for (int r : res1) System.out.print(r); // 98653
        System.out.println();
        
        int[] res2 = maxNumber(new int[]{6,7}, new int[]{6,0,4}, 5);
        for (int r : res2) System.out.print(r); // 67604
        System.out.println();
        
        int[] res3 = maxNumber(new int[]{3,9}, new int[]{8,9}, 3);
        for (int r : res3) System.out.print(r); // 989
        System.out.println();
    }
}
