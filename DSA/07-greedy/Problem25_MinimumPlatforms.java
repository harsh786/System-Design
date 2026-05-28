/**
 * Problem 25: Minimum Platforms (GFG)
 *
 * Greedy Choice: Sort arrivals and departures. Count overlapping intervals.
 *
 * Time: O(n log n), Space: O(1)
 *
 * Production Analogy: Minimum number of connection pool slots for overlapping DB queries.
 */
import java.util.*;
public class Problem25_MinimumPlatforms {
    
    public static int findPlatform(int[] arr, int[] dep) {
        Arrays.sort(arr);
        Arrays.sort(dep);
        int platforms = 0, max = 0, i = 0, j = 0;
        while (i < arr.length) {
            if (arr[i] <= dep[j]) { platforms++; i++; }
            else { platforms--; j++; }
            max = Math.max(max, platforms);
        }
        return max;
    }
    
    public static void main(String[] args) {
        System.out.println(findPlatform(new int[]{900,940,950,1100,1500,1800},
                                         new int[]{910,1200,1120,1130,1900,2000})); // 3
        System.out.println(findPlatform(new int[]{900,1100,1235}, new int[]{1000,1200,1240})); // 1
    }
}
