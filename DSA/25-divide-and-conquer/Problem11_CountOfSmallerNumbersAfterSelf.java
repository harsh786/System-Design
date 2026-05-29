import java.util.*;

/**
 * Problem 11: Count of Smaller Numbers After Self (LeetCode 315)
 * 
 * D&C Approach (Enhanced Merge Sort):
 * - DIVIDE: Split array into halves
 * - CONQUER: Recursively sort and count for each half
 * - COMBINE: During merge, when element from right goes before left element,
 *   count how many right elements are smaller
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy:
 * - Counting out-of-order events in distributed event streams
 * - Measuring "rank changes" in real-time leaderboard systems
 */
public class Problem11_CountOfSmallerNumbersAfterSelf {

    public static List<Integer> countSmaller(int[] nums) {
        int n = nums.length;
        int[] counts = new int[n];
        int[][] indexed = new int[n][2]; // [value, original index]
        for (int i = 0; i < n; i++) indexed[i] = new int[]{nums[i], i};
        
        mergeSort(indexed, counts, 0, n - 1);
        
        List<Integer> result = new ArrayList<>();
        for (int c : counts) result.add(c);
        return result;
    }

    private static void mergeSort(int[][] arr, int[] counts, int lo, int hi) {
        if (lo >= hi) return;
        int mid = lo + (hi - lo) / 2;
        mergeSort(arr, counts, lo, mid);
        mergeSort(arr, counts, mid + 1, hi);
        merge(arr, counts, lo, mid, hi);
    }

    private static void merge(int[][] arr, int[] counts, int lo, int mid, int hi) {
        int[][] temp = new int[hi - lo + 1][2];
        int i = lo, j = mid + 1, k = 0;
        int rightCount = 0; // Elements from right that went before current left element
        
        while (i <= mid && j <= hi) {
            if (arr[j][0] < arr[i][0]) {
                rightCount++;
                temp[k++] = arr[j++];
            } else {
                counts[arr[i][1]] += rightCount;
                temp[k++] = arr[i++];
            }
        }
        while (i <= mid) {
            counts[arr[i][1]] += rightCount;
            temp[k++] = arr[i++];
        }
        while (j <= hi) temp[k++] = arr[j++];
        System.arraycopy(temp, 0, arr, lo, temp.length);
    }

    public static void main(String[] args) {
        System.out.println(countSmaller(new int[]{5,2,6,1}));   // [2,1,1,0]
        System.out.println(countSmaller(new int[]{-1}));        // [0]
        System.out.println(countSmaller(new int[]{-1,-1}));     // [0,0]
        System.out.println(countSmaller(new int[]{2,0,1}));     // [2,0,0]
        System.out.println(countSmaller(new int[]{1,2,3,4}));   // [0,0,0,0]
    }
}
