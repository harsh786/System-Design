import java.util.*;

/**
 * Problem 1: Radix Sort LSD (Least Significant Digit)
 * 
 * Sorts integers by processing digits from least significant to most significant.
 * Uses counting sort as a stable subroutine for each digit position.
 * 
 * Time: O(d * (n + k)) where d=digits, n=elements, k=base (usually 10)
 * Space: O(n + k)
 * Stable: Yes (critical for LSD radix sort correctness)
 * 
 * Key insight: Must use a STABLE sort at each digit level.
 * If we process LSD first, previous digit orderings are preserved by stability.
 */
public class Problem01_RadixSortLSD {

    public static void radixSortLSD(int[] arr) {
        if (arr.length == 0) return;
        
        int max = Arrays.stream(arr).max().getAsInt();
        
        // Process each digit position (exp = 1, 10, 100, ...)
        for (int exp = 1; max / exp > 0; exp *= 10) {
            countingSortByDigit(arr, exp);
        }
    }

    private static void countingSortByDigit(int[] arr, int exp) {
        int n = arr.length;
        int[] output = new int[n];
        int[] count = new int[10]; // Digits 0-9
        
        // Count occurrences of each digit
        for (int val : arr) {
            int digit = (val / exp) % 10;
            count[digit]++;
        }
        
        // Convert to cumulative count (positions)
        for (int i = 1; i < 10; i++) {
            count[i] += count[i - 1];
        }
        
        // Build output array (traverse right-to-left for stability)
        for (int i = n - 1; i >= 0; i--) {
            int digit = (arr[i] / exp) % 10;
            output[count[digit] - 1] = arr[i];
            count[digit]--;
        }
        
        System.arraycopy(output, 0, arr, 0, n);
    }

    public static void main(String[] args) {
        int[] arr = {170, 45, 75, 90, 802, 24, 2, 66};
        
        System.out.println("LSD Radix Sort");
        System.out.println("Before: " + Arrays.toString(arr));
        
        radixSortLSD(arr);
        
        System.out.println("After:  " + Arrays.toString(arr));
        
        // Verify
        for (int i = 1; i < arr.length; i++) assert arr[i] >= arr[i-1];
        System.out.println("PASS");
    }
}
