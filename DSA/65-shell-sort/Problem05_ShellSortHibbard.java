/**
 * Problem 5: Shell Sort with Hibbard Gap Sequence
 * 
 * Hibbard's sequence: 2^k - 1 → 1, 3, 7, 15, 31, 63, 127, 255, ...
 * 
 * Key properties:
 * - Worst case: O(n^(3/2)) - proven by Hibbard
 * - All gaps are odd, which helps avoid the pathological cases
 *   where Shell's original (all even except 1) fails
 * - Consecutive gaps are coprime (GCD = 1), ensuring better mixing
 * 
 * The problem with Shell's original sequence n/2, n/4, ..., 2, 1 is that
 * elements in even positions are never compared with odd positions until gap=1.
 */
public class Problem05_ShellSortHibbard {

    public static void shellSortHibbard(int[] arr) {
        int n = arr.length;
        
        // Find largest Hibbard gap < n: 2^k - 1
        int k = 1;
        while ((1 << (k + 1)) - 1 < n) {
            k++;
        }
        
        // Sort using gaps 2^k - 1, 2^(k-1) - 1, ..., 3, 1
        while (k >= 1) {
            int gap = (1 << k) - 1; // 2^k - 1
            
            for (int i = gap; i < n; i++) {
                int temp = arr[i];
                int j = i;
                while (j >= gap && arr[j - gap] > temp) {
                    arr[j] = arr[j - gap];
                    j -= gap;
                }
                arr[j] = temp;
            }
            k--;
        }
    }

    public static void main(String[] args) {
        System.out.println("Hibbard Gap Sequence: 2^k - 1");
        System.out.println("Gaps: 1, 3, 7, 15, 31, 63, 127, 255, 511, ...\n");

        // Demonstrate the pathological case for Shell's original
        // Array where even/odd positions are separately sorted but interleaved
        int[] pathological = {2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15};
        System.out.print("Pathological for Shell's gaps: ");
        for (int v : pathological) System.out.print(v + " ");
        System.out.println();

        shellSortHibbard(pathological);
        System.out.print("After Hibbard sort:           ");
        for (int v : pathological) System.out.print(v + " ");
        System.out.println();

        // Verify
        for (int i = 1; i < pathological.length; i++) assert pathological[i] >= pathological[i-1];
        
        // Performance comparison
        int size = 10000;
        int[] arr = new int[size];
        java.util.Random rand = new java.util.Random(42);
        for (int i = 0; i < size; i++) arr[i] = rand.nextInt(100000);
        
        long start = System.nanoTime();
        shellSortHibbard(arr);
        long elapsed = System.nanoTime() - start;
        
        for (int i = 1; i < arr.length; i++) assert arr[i] >= arr[i-1];
        System.out.printf("%nHibbard sort of %d elements: %.2f ms - PASS%n", size, elapsed / 1e6);
    }
}
