import java.util.*;

/**
 * Problem 5: Radix Sort for Binary Representations
 * 
 * Using binary (base-2) or higher powers of 2 (base-256, base-65536) as the radix.
 * 
 * Base-256 radix sort on 32-bit integers:
 * - 4 passes (one per byte)
 * - Very efficient: only 4 passes regardless of value magnitude
 * - Uses 256-bucket counting sort per pass
 * 
 * This is how many high-performance sorting libraries work internally.
 */
public class Problem05_RadixSortBinary {

    // Base-256 LSD radix sort (4 passes for 32-bit integers)
    public static void radixSort256(int[] arr) {
        int n = arr.length;
        int[] aux = new int[n];
        
        // 4 passes, one for each byte (bits 0-7, 8-15, 16-23, 24-31)
        for (int shift = 0; shift < 32; shift += 8) {
            int[] count = new int[257]; // 256 buckets + 1
            
            // Handle sign bit in the last pass (shift=24)
            // Flip bit 7 of the last byte to sort negative numbers correctly
            
            for (int i = 0; i < n; i++) {
                int byteVal = (arr[i] >> shift) & 0xFF;
                if (shift == 24) byteVal ^= 0x80; // Flip sign bit
                count[byteVal + 1]++;
            }
            
            // Cumulative
            for (int i = 1; i <= 256; i++) count[i] += count[i-1];
            
            // Distribute
            for (int i = 0; i < n; i++) {
                int byteVal = (arr[i] >> shift) & 0xFF;
                if (shift == 24) byteVal ^= 0x80;
                aux[count[byteVal]++] = arr[i];
            }
            
            System.arraycopy(aux, 0, arr, 0, n);
        }
    }

    // Base-2 radix sort (bit-by-bit, 32 passes) - for educational purposes
    public static void radixSortBitByBit(int[] arr) {
        int n = arr.length;
        for (int bit = 0; bit < 31; bit++) { // Skip sign bit for now
            // Partition: 0-bits before 1-bits (stable)
            int[] zeros = new int[n], ones = new int[n];
            int zi = 0, oi = 0;
            for (int v : arr) {
                if (((v >> bit) & 1) == 0) zeros[zi++] = v;
                else ones[oi++] = v;
            }
            System.arraycopy(zeros, 0, arr, 0, zi);
            System.arraycopy(ones, 0, arr, zi, oi);
        }
        // Handle sign bit (bit 31): 1s (negative) before 0s (positive)
        int[] neg = new int[n], pos = new int[n];
        int ni = 0, pi = 0;
        for (int v : arr) {
            if (v < 0) neg[ni++] = v;
            else pos[pi++] = v;
        }
        System.arraycopy(neg, 0, arr, 0, ni);
        System.arraycopy(pos, 0, arr, ni, pi);
    }

    public static void main(String[] args) {
        int[] arr1 = {-5, 100, -200, 50, 0, Integer.MAX_VALUE, Integer.MIN_VALUE, 42, -1};
        int[] arr2 = arr1.clone();
        
        System.out.println("Binary Radix Sort");
        System.out.println("Input: " + Arrays.toString(arr1));
        
        radixSort256(arr1);
        System.out.println("Base-256 (4 passes): " + Arrays.toString(arr1));
        
        radixSortBitByBit(arr2);
        System.out.println("Bit-by-bit (32 passes): " + Arrays.toString(arr2));
        
        for (int i = 1; i < arr1.length; i++) assert arr1[i] >= arr1[i-1];
        for (int i = 1; i < arr2.length; i++) assert arr2[i] >= arr2[i-1];
        System.out.println("Both PASS");
        
        // Performance comparison
        Random rand = new Random(42);
        int[] large = new int[100000];
        for (int i = 0; i < large.length; i++) large[i] = rand.nextInt();
        int[] copy = large.clone();
        
        long t1 = System.nanoTime();
        radixSort256(large);
        System.out.printf("%nBase-256 on 100k ints: %.2f ms%n", (System.nanoTime()-t1)/1e6);
        
        long t2 = System.nanoTime();
        Arrays.sort(copy);
        System.out.printf("Arrays.sort on 100k ints: %.2f ms%n", (System.nanoTime()-t2)/1e6);
    }
}
