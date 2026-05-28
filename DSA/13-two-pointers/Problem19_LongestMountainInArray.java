/**
 * Problem 19: Longest Mountain in Array
 * 
 * Find longest subarray that forms a mountain (up then down).
 * 
 * Approach: For each peak, expand left and right to find mountain length.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like detecting the longest traffic spike pattern
 * (ramp-up then ramp-down) in a time-series monitoring dashboard.
 */
public class Problem19_LongestMountainInArray {
    public static int longestMountain(int[] arr) {
        int n = arr.length, longest = 0;
        int i = 1;
        while (i < n - 1) {
            if (arr[i] > arr[i-1] && arr[i] > arr[i+1]) {
                int left = i - 1, right = i + 1;
                while (left > 0 && arr[left-1] < arr[left]) left--;
                while (right < n - 1 && arr[right+1] < arr[right]) right++;
                longest = Math.max(longest, right - left + 1);
                i = right + 1;
            } else {
                i++;
            }
        }
        return longest;
    }

    public static void main(String[] args) {
        System.out.println(longestMountain(new int[]{2,1,4,7,3,2,5})); // 5
        System.out.println(longestMountain(new int[]{2,2,2})); // 0
        System.out.println(longestMountain(new int[]{0,1,2,3,4,5,4,3,2,1,0})); // 11
    }
}
