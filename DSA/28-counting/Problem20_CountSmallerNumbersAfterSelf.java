/**
 * Problem: Count of Smaller Numbers After Self (LeetCode 315)
 * Approach: Merge sort with index tracking
 * Complexity: O(n log n) time, O(n) space
 * Production Analogy: Inversion counting for anomaly detection in sequences
 */
import java.util.*;
public class Problem20_CountSmallerNumbersAfterSelf {
    int[] counts;
    public List<Integer> countSmaller(int[] nums) {
        int n = nums.length;
        counts = new int[n];
        int[][] indexed = new int[n][2]; // [value, originalIndex]
        for (int i = 0; i < n; i++) indexed[i] = new int[]{nums[i], i};
        mergeSort(indexed, 0, n-1);
        List<Integer> res = new ArrayList<>();
        for (int c : counts) res.add(c);
        return res;
    }
    void mergeSort(int[][] arr, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo+hi)/2;
        mergeSort(arr, lo, mid); mergeSort(arr, mid+1, hi);
        int[][] merged = new int[hi-lo+1][2];
        int i=lo, j=mid+1, k=0, rightCount=0;
        while (i<=mid && j<=hi) {
            if (arr[j][0] < arr[i][0]) { rightCount++; merged[k++]=arr[j++]; }
            else { counts[arr[i][1]] += rightCount; merged[k++]=arr[i++]; }
        }
        while (i<=mid) { counts[arr[i][1]] += rightCount; merged[k++]=arr[i++]; }
        while (j<=hi) merged[k++]=arr[j++];
        System.arraycopy(merged, 0, arr, lo, merged.length);
    }
    public static void main(String[] args) {
        System.out.println(new Problem20_CountSmallerNumbersAfterSelf().countSmaller(new int[]{5,2,6,1})); // [2,1,1,0]
    }
}
