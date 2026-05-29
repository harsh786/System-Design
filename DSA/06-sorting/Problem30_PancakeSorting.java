import java.util.*;

/**
 * Problem 30: Pancake Sorting
 * 
 * Sort array using only pancake flips (reverse prefix of any length).
 * 
 * Approach: Find max unsorted element, flip it to front, flip it to correct position.
 * Time Complexity: O(n²)
 * Space Complexity: O(n) for result list
 * 
 * Production Analogy: Stack-based reordering in warehouse robotics where you can only
 * reverse the top k items of a stack (like flipping a stack of pancakes).
 */
public class Problem30_PancakeSorting {
    
    public List<Integer> pancakeSort(int[] arr) {
        List<Integer> result = new ArrayList<>();
        int n = arr.length;
        
        for (int size = n; size > 1; size--) {
            // Find index of max in arr[0..size-1]
            int maxIdx = 0;
            for (int i = 1; i < size; i++) {
                if (arr[i] > arr[maxIdx]) maxIdx = i;
            }
            
            if (maxIdx == size - 1) continue;
            
            // Flip max to front
            if (maxIdx > 0) {
                flip(arr, maxIdx);
                result.add(maxIdx + 1);
            }
            // Flip to correct position
            flip(arr, size - 1);
            result.add(size);
        }
        return result;
    }
    
    private void flip(int[] arr, int k) {
        int i = 0, j = k;
        while (i < j) {
            int tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
            i++; j--;
        }
    }
    
    public static void main(String[] args) {
        Problem30_PancakeSorting sol = new Problem30_PancakeSorting();
        
        int[] t1 = {3,2,4,1};
        System.out.println("Test 1: " + sol.pancakeSort(t1) + " -> " + Arrays.toString(t1));
        
        int[] t2 = {1,2,3};
        System.out.println("Test 2: " + sol.pancakeSort(t2) + " -> " + Arrays.toString(t2));
        
        int[] t3 = {3,2,1};
        System.out.println("Test 3: " + sol.pancakeSort(t3) + " -> " + Arrays.toString(t3));
    }
}
