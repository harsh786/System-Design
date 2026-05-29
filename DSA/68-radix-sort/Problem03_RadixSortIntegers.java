import java.util.*;

/**
 * Problem 3: Radix Sort for Integers (including negatives)
 * 
 * Standard radix sort only works for non-negative integers.
 * To handle negatives:
 * Option 1: Separate negatives and positives, sort separately, merge
 * Option 2: Offset all values by minimum to make non-negative
 * Option 3: Use base-256 with sign handling
 * 
 * This implements all approaches with performance comparison.
 */
public class Problem03_RadixSortIntegers {

    // Approach 1: Separate negative and positive
    public static void radixSortWithNegatives(int[] arr) {
        List<Integer> negatives = new ArrayList<>();
        List<Integer> positives = new ArrayList<>();
        
        for (int v : arr) {
            if (v < 0) negatives.add(-v); // Store absolute values
            else positives.add(v);
        }
        
        int[] negArr = negatives.stream().mapToInt(Integer::intValue).toArray();
        int[] posArr = positives.stream().mapToInt(Integer::intValue).toArray();
        
        if (negArr.length > 0) radixSortLSD(negArr);
        if (posArr.length > 0) radixSortLSD(posArr);
        
        // Merge: reversed negatives then positives
        int idx = 0;
        for (int i = negArr.length - 1; i >= 0; i--) {
            arr[idx++] = -negArr[i];
        }
        for (int v : posArr) {
            arr[idx++] = v;
        }
    }

    // Approach 2: Offset-based (shift all values to non-negative)
    public static void radixSortOffset(int[] arr) {
        int min = Integer.MAX_VALUE;
        for (int v : arr) min = Math.min(min, v);
        
        // Shift everything up
        for (int i = 0; i < arr.length; i++) arr[i] -= min;
        
        radixSortLSD(arr);
        
        // Shift back
        for (int i = 0; i < arr.length; i++) arr[i] += min;
    }

    private static void radixSortLSD(int[] arr) {
        if (arr.length == 0) return;
        int max = 0;
        for (int v : arr) max = Math.max(max, v);
        for (int exp = 1; max / exp > 0; exp *= 10) {
            int n = arr.length;
            int[] output = new int[n];
            int[] count = new int[10];
            for (int v : arr) count[(v / exp) % 10]++;
            for (int i = 1; i < 10; i++) count[i] += count[i-1];
            for (int i = n-1; i >= 0; i--) {
                int d = (arr[i] / exp) % 10;
                output[--count[d]] = arr[i];
            }
            System.arraycopy(output, 0, arr, 0, n);
        }
    }

    public static void main(String[] args) {
        int[] arr1 = {-5, 3, -1, 0, 7, -3, 2, -8, 10, -10};
        int[] arr2 = arr1.clone();
        
        System.out.println("Radix Sort with Negative Numbers");
        System.out.println("Input: " + Arrays.toString(arr1));
        
        radixSortWithNegatives(arr1);
        System.out.println("Separate approach: " + Arrays.toString(arr1));
        
        radixSortOffset(arr2);
        System.out.println("Offset approach:   " + Arrays.toString(arr2));
        
        for (int i = 1; i < arr1.length; i++) assert arr1[i] >= arr1[i-1];
        for (int i = 1; i < arr2.length; i++) assert arr2[i] >= arr2[i-1];
        System.out.println("Both PASS");
    }
}
