/**
 * Problem 4: Shell Sort with Sedgewick Gap Sequence
 * 
 * Sedgewick's 1986 sequence: 1, 5, 19, 41, 109, 209, 505, 929, ...
 * Formula: 4^k + 3*2^(k-1) + 1 for k >= 1, prefixed with 1
 * Alternative: 9*(4^k - 2^k) + 1 or 4^(k+2) - 6*2^(k+1) + 1
 * 
 * Worst case: O(n^(4/3))
 * This is one of the best known gap sequences for practical use.
 */
public class Problem04_ShellSortSedgewick {

    public static int[] generateSedgewickGaps(int n) {
        java.util.List<Integer> gaps = new java.util.ArrayList<>();
        gaps.add(1);
        
        int k = 1;
        while (true) {
            // Sedgewick's formula: alternating between two formulas
            int gap;
            if (k % 2 == 0) {
                gap = 9 * ((int)Math.pow(2, k) - (int)Math.pow(2, k/2)) + 1;
            } else {
                gap = 8 * (int)Math.pow(2, k) - 6 * (int)Math.pow(2, (k+1)/2) + 1;
            }
            if (gap >= n) break;
            gaps.add(gap);
            k++;
        }
        
        // Return in descending order
        int[] result = new int[gaps.size()];
        for (int i = 0; i < gaps.size(); i++) {
            result[i] = gaps.get(gaps.size() - 1 - i);
        }
        return result;
    }

    public static void shellSortSedgewick(int[] arr) {
        int n = arr.length;
        int[] gaps = generateSedgewickGaps(n);
        
        for (int gap : gaps) {
            for (int i = gap; i < n; i++) {
                int temp = arr[i];
                int j = i;
                while (j >= gap && arr[j - gap] > temp) {
                    arr[j] = arr[j - gap];
                    j -= gap;
                }
                arr[j] = temp;
            }
        }
    }

    public static void main(String[] args) {
        // Demonstrate Sedgewick gaps
        System.out.println("Sedgewick Gap Sequence for n=1000:");
        int[] gaps = generateSedgewickGaps(1000);
        System.out.print("Gaps: ");
        for (int g : gaps) System.out.print(g + " ");
        System.out.println("\n");

        // Sort test
        int[] arr = {64, 25, 12, 22, 11, 90, 45, 78, 33, 56, 1, 99, 42};
        System.out.print("Before: ");
        for (int v : arr) System.out.print(v + " ");
        System.out.println();

        shellSortSedgewick(arr);

        System.out.print("After:  ");
        for (int v : arr) System.out.print(v + " ");
        System.out.println();

        // Verify
        for (int i = 1; i < arr.length; i++) assert arr[i] >= arr[i-1];
        System.out.println("PASS - Sedgewick Shell Sort works correctly");
    }
}
