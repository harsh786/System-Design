import java.util.*;

/**
 * Problem 17: Beautiful Array (LeetCode 932)
 * An array is beautiful if for every i < k < j, nums[k]*2 != nums[i]+nums[j]
 * 
 * D&C Approach:
 * - Key insight: if arr is beautiful, then 2*arr and 2*arr-1 are also beautiful
 * - DIVIDE: Separate into odd-indexed and even-indexed positions
 * - CONQUER: Recursively build beautiful arrays for each
 * - COMBINE: Odds on left, evens on right (odd+even can never equal 2*anything)
 * 
 * Time: O(n log n), Space: O(n log n)
 * 
 * Production Analogy:
 * - Constructing conflict-free schedules via recursive partitioning
 * - Frequency assignment in wireless networks avoiding interference
 */
public class Problem17_BeautifulArray {

    public static int[] beautifulArray(int n) {
        List<Integer> result = new ArrayList<>();
        result.add(1);
        
        while (result.size() < n) {
            List<Integer> next = new ArrayList<>();
            // Odd positions first (2*x - 1)
            for (int x : result) if (2 * x - 1 <= n) next.add(2 * x - 1);
            // Even positions (2*x)
            for (int x : result) if (2 * x <= n) next.add(2 * x);
            result = next;
        }
        
        return result.stream().mapToInt(Integer::intValue).toArray();
    }

    private static boolean isBeautiful(int[] arr) {
        for (int i = 0; i < arr.length; i++)
            for (int j = i + 2; j < arr.length; j++)
                for (int k = i + 1; k < j; k++)
                    if (arr[k] * 2 == arr[i] + arr[j]) return false;
        return true;
    }

    public static void main(String[] args) {
        int[] r1 = beautifulArray(4);
        System.out.println(Arrays.toString(r1) + " valid=" + isBeautiful(r1));
        int[] r2 = beautifulArray(5);
        System.out.println(Arrays.toString(r2) + " valid=" + isBeautiful(r2));
        int[] r3 = beautifulArray(1);
        System.out.println(Arrays.toString(r3) + " valid=" + isBeautiful(r3));
        int[] r4 = beautifulArray(8);
        System.out.println(Arrays.toString(r4) + " valid=" + isBeautiful(r4));
    }
}
