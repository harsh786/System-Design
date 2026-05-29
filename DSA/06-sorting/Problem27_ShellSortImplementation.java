import java.util.*;

/**
 * Problem 27: Shell Sort Implementation
 * 
 * Generalization of insertion sort using diminishing gap sequences.
 * 
 * Approach: Start with large gap, reduce. For each gap, do gapped insertion sort.
 * Time Complexity: O(n^(3/2)) with Knuth sequence, depends on gap sequence
 * Space Complexity: O(1)
 * Stability: Not stable
 * 
 * Production Analogy: Hierarchical data organization - coarse-grained sorting first
 * (like routing to correct region), then fine-grained within region.
 */
public class Problem27_ShellSortImplementation {
    
    public int[] shellSort(int[] nums) {
        int n = nums.length;
        // Knuth sequence: 1, 4, 13, 40, 121...
        int gap = 1;
        while (gap < n / 3) gap = gap * 3 + 1;
        
        while (gap >= 1) {
            for (int i = gap; i < n; i++) {
                int key = nums[i];
                int j = i;
                while (j >= gap && nums[j - gap] > key) {
                    nums[j] = nums[j - gap];
                    j -= gap;
                }
                nums[j] = key;
            }
            gap /= 3;
        }
        return nums;
    }
    
    public static void main(String[] args) {
        Problem27_ShellSortImplementation sol = new Problem27_ShellSortImplementation();
        
        System.out.println("Test 1: " + Arrays.toString(sol.shellSort(new int[]{12,34,54,2,3}))); // [2,3,12,34,54]
        System.out.println("Test 2: " + Arrays.toString(sol.shellSort(new int[]{9,8,7,6,5,4,3,2,1}))); // [1..9]
        System.out.println("Test 3: " + Arrays.toString(sol.shellSort(new int[]{1}))); // [1]
        System.out.println("Test 4: " + Arrays.toString(sol.shellSort(new int[]{-5,3,0,-1,2}))); // [-5,-1,0,2,3]
    }
}
