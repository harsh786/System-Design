/**
 * Problem: Relative Sort Array (LeetCode 1122)
 * Approach: Counting sort with custom order
 * Complexity: O(n + k) time, O(k) space
 * Production Analogy: Custom priority ordering in task queues
 */
import java.util.*;
public class Problem26_RelativeSortArray {
    public int[] relativeSortArray(int[] arr1, int[] arr2) {
        int[] count = new int[1001];
        for (int n : arr1) count[n]++;
        int idx = 0;
        int[] res = new int[arr1.length];
        for (int n : arr2) while (count[n]-- > 0) res[idx++] = n;
        for (int i = 0; i < 1001; i++) while (count[i]-- > 0) res[idx++] = i;
        return res;
    }
    public static void main(String[] args) {
        System.out.println(Arrays.toString(new Problem26_RelativeSortArray().relativeSortArray(
            new int[]{2,3,1,3,2,4,6,7,9,2,19}, new int[]{2,1,4,3,9,6})));
    }
}
