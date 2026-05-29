/**
 * Problem 3: Shell Sort with Knuth Gap Sequence
 * 
 * Knuth's sequence: h = 3h + 1, starting from 1 → 1, 4, 13, 40, 121, 364, ...
 * Start with the largest h < n/3, then divide by 3 each iteration.
 * 
 * Time Complexity: O(n^(3/2)) - proven worst case
 * This is a significant improvement over Shell's original O(n^2)
 * 
 * The sequence is computed as: h_k = (3^k - 1) / 2
 * We find the largest h less than n/3, then work down.
 */
public class Problem03_ShellSortKnuth {

    public static void shellSortKnuth(int[] arr) {
        int n = arr.length;
        
        // Compute starting gap using Knuth's formula: h = 3h + 1
        int gap = 1;
        while (gap < n / 3) {
            gap = 3 * gap + 1; // 1, 4, 13, 40, 121, 364, 1093, ...
        }
        
        while (gap >= 1) {
            // Perform gapped insertion sort
            for (int i = gap; i < n; i++) {
                int temp = arr[i];
                int j = i;
                while (j >= gap && arr[j - gap] > temp) {
                    arr[j] = arr[j - gap];
                    j -= gap;
                }
                arr[j] = temp;
            }
            gap /= 3; // Reverse the formula: next gap is h/3
        }
    }

    public static void main(String[] args) {
        int[] arr = {88, 22, 44, 99, 11, 55, 77, 33, 66, 0, 100, 5};
        
        System.out.println("Knuth Gap Sequence Shell Sort");
        System.out.println("Sequence: 1, 4, 13, 40, 121, 364, ...");
        System.out.println();
        
        // Show gap sequence for this array size
        int n = arr.length;
        int gap = 1;
        System.out.print("Gaps used (in reverse order): ");
        java.util.List<Integer> gaps = new java.util.ArrayList<>();
        while (gap < n / 3) {
            gap = 3 * gap + 1;
        }
        while (gap >= 1) {
            gaps.add(gap);
            gap /= 3;
        }
        System.out.println(gaps);
        
        System.out.print("Before: ");
        printArray(arr);
        
        shellSortKnuth(arr);
        
        System.out.print("After:  ");
        printArray(arr);
        
        // Verify
        for (int i = 1; i < arr.length; i++) {
            assert arr[i] >= arr[i-1];
        }
        System.out.println("PASS");
    }

    private static void printArray(int[] arr) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < arr.length; i++) {
            sb.append(arr[i]);
            if (i < arr.length - 1) sb.append(", ");
        }
        System.out.println(sb.append("]"));
    }
}
