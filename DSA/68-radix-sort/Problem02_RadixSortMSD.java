import java.util.*;

/**
 * Problem 2: Radix Sort MSD (Most Significant Digit)
 * 
 * Processes digits from most significant to least significant.
 * Recursively sorts each bucket from the previous digit.
 * 
 * Advantages over LSD:
 * - Can short-circuit (stop early for buckets of size 1)
 * - Works for variable-length strings naturally
 * - Can be done in-place (with more complex implementation)
 * 
 * Disadvantages:
 * - Recursive (stack overhead)
 * - Not as cache-friendly as LSD
 * - More complex implementation
 * 
 * Time: O(d * n) average, O(d * (n + k)) worst
 */
public class Problem02_RadixSortMSD {

    public static void radixSortMSD(int[] arr) {
        if (arr.length <= 1) return;
        int max = 0;
        for (int v : arr) max = Math.max(max, v);
        
        // Find number of digits in max
        int maxDigits = 0;
        int temp = max;
        while (temp > 0) { maxDigits++; temp /= 10; }
        
        msdSort(arr, 0, arr.length - 1, (int) Math.pow(10, maxDigits - 1));
    }

    private static void msdSort(int[] arr, int lo, int hi, int exp) {
        if (lo >= hi || exp == 0) return;
        
        // Counting sort by current digit
        int[] count = new int[12]; // 0-9 + boundaries
        int[] aux = new int[hi - lo + 1];
        
        for (int i = lo; i <= hi; i++) {
            int digit = (arr[i] / exp) % 10;
            count[digit + 1]++;
        }
        
        // Cumulative
        for (int i = 1; i < 11; i++) count[i] += count[i - 1];
        
        // Distribute
        for (int i = lo; i <= hi; i++) {
            int digit = (arr[i] / exp) % 10;
            aux[count[digit]++] = arr[i];
        }
        
        // Copy back
        System.arraycopy(aux, 0, arr, lo, hi - lo + 1);
        
        // Recursively sort each bucket
        // Reset count for bucket boundaries
        int[] bucketCount = new int[10];
        for (int i = lo; i <= hi; i++) {
            bucketCount[(arr[i] / exp) % 10]++;
        }
        
        int offset = lo;
        for (int d = 0; d < 10; d++) {
            if (bucketCount[d] > 1) {
                msdSort(arr, offset, offset + bucketCount[d] - 1, exp / 10);
            }
            offset += bucketCount[d];
        }
    }

    public static void main(String[] args) {
        int[] arr = {170, 45, 75, 90, 802, 24, 2, 66, 123, 999, 1, 500};
        
        System.out.println("MSD Radix Sort");
        System.out.println("Before: " + Arrays.toString(arr));
        
        radixSortMSD(arr);
        
        System.out.println("After:  " + Arrays.toString(arr));
        
        for (int i = 1; i < arr.length; i++) assert arr[i] >= arr[i-1];
        System.out.println("PASS");
    }
}
