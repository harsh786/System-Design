import java.util.*;

/**
 * Problem 10: Radix Sort Performance Analysis
 * 
 * When to use radix sort vs comparison sorts:
 * - Radix: O(d * n) where d = digits/width of keys
 * - Comparison: O(n log n)
 * - Radix wins when d < log n (i.e., key size is small relative to n)
 * - For 32-bit integers: radix wins when n > 2^32/base ≈ when n is large enough
 * 
 * Practical considerations:
 * - Cache behavior (radix sort scatters data)
 * - Memory usage (needs O(n) extra)
 * - Branch prediction (counting sort has no branches in inner loop)
 */
public class Problem10_RadixSortPerformance {

    static void radixSort10(int[] arr) {
        int max = 0;
        for (int v : arr) max = Math.max(max, v);
        int n = arr.length;
        int[] output = new int[n];
        for (int exp = 1; max/exp > 0; exp *= 10) {
            int[] count = new int[10];
            for (int v : arr) count[(v/exp)%10]++;
            for (int i = 1; i < 10; i++) count[i] += count[i-1];
            for (int i = n-1; i >= 0; i--) output[--count[(arr[i]/exp)%10]] = arr[i];
            System.arraycopy(output, 0, arr, 0, n);
        }
    }

    static void radixSort256(int[] arr) {
        int n = arr.length;
        int[] aux = new int[n];
        for (int shift = 0; shift < 32; shift += 8) {
            int[] count = new int[257];
            for (int v : arr) count[((v>>>shift)&0xFF)+1]++;
            for (int i = 1; i <= 256; i++) count[i] += count[i-1];
            for (int v : arr) aux[count[(v>>>shift)&0xFF]++] = v;
            System.arraycopy(aux, 0, arr, 0, n);
        }
    }

    public static void main(String[] args) {
        int[] sizes = {1000, 10000, 100000, 1000000};
        Random rand = new Random(42);
        
        System.out.println("Radix Sort Performance Analysis");
        System.out.printf("%-10s %-12s %-12s %-12s%n", "Size", "Base-10", "Base-256", "Arrays.sort");
        System.out.println("-".repeat(46));

        for (int n : sizes) {
            int[] data = new int[n];
            for (int i = 0; i < n; i++) data[i] = rand.nextInt(Integer.MAX_VALUE);
            
            int[] a1 = data.clone(), a2 = data.clone(), a3 = data.clone();
            
            long t1 = System.nanoTime();
            radixSort10(a1);
            long time1 = System.nanoTime() - t1;

            long t2 = System.nanoTime();
            radixSort256(a2);
            long time2 = System.nanoTime() - t2;

            long t3 = System.nanoTime();
            Arrays.sort(a3);
            long time3 = System.nanoTime() - t3;

            System.out.printf("%-10d %-12.2f %-12.2f %-12.2f%n", 
                n, time1/1e6, time2/1e6, time3/1e6);
        }
        
        System.out.println("\nKey Takeaways:");
        System.out.println("- Base-256 (4 passes) beats Base-10 (10 passes for large values)");
        System.out.println("- Arrays.sort uses dual-pivot quicksort (good cache behavior)");
        System.out.println("- Radix sort shines for large n with bounded key size");
        System.out.println("- Extra memory requirement is the main drawback");
    }
}
