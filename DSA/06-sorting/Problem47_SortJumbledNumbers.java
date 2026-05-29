import java.util.*;

/**
 * Problem 47: Sort Jumbled Numbers
 * 
 * Given a mapping of digits 0-9, sort numbers by their mapped values.
 * 
 * Approach: Compute mapped value for each number, sort by mapped value (stable).
 * Time Complexity: O(n * d * log n) where d = max digits
 * Space Complexity: O(n)
 * 
 * Production Analogy: Locale-specific sorting in internationalized applications where
 * character mappings differ (e.g., sorting encoded data by decoded values).
 */
public class Problem47_SortJumbledNumbers {
    
    public int[] sortJumbled(int[] mapping, int[] nums) {
        int n = nums.length;
        int[][] pairs = new int[n][2]; // [mappedValue, originalIndex]
        
        for (int i = 0; i < n; i++) {
            pairs[i] = new int[]{getMapped(nums[i], mapping), i};
        }
        
        Arrays.sort(pairs, (a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        
        int[] result = new int[n];
        for (int i = 0; i < n; i++) result[i] = nums[pairs[i][1]];
        return result;
    }
    
    private int getMapped(int num, int[] mapping) {
        if (num == 0) return mapping[0];
        int result = 0, place = 1;
        while (num > 0) {
            result += mapping[num % 10] * place;
            place *= 10;
            num /= 10;
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem47_SortJumbledNumbers sol = new Problem47_SortJumbledNumbers();
        
        System.out.println("Test 1: " + Arrays.toString(sol.sortJumbled(
            new int[]{8,9,4,0,2,1,3,5,7,6}, new int[]{991,338,38})));
        // [338,38,991]
        
        System.out.println("Test 2: " + Arrays.toString(sol.sortJumbled(
            new int[]{0,1,2,3,4,5,6,7,8,9}, new int[]{789,456,123})));
        // [123,456,789]
        
        System.out.println("Test 3: " + Arrays.toString(sol.sortJumbled(
            new int[]{9,8,7,6,5,4,3,2,1,0}, new int[]{0,1,2,3,4,5,6,7,8,9})));
        // [9,8,7,6,5,4,3,2,1,0]
    }
}
