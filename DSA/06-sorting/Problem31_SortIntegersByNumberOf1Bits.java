import java.util.*;

/**
 * Problem 31: Sort Integers by The Number of 1 Bits
 * 
 * Sort by number of 1 bits ascending, tiebreak by value ascending.
 * 
 * Approach: Custom comparator using Integer.bitCount().
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Sorting feature flags by activation count for feature rollout dashboards,
 * or sorting subnet masks by specificity.
 */
public class Problem31_SortIntegersByNumberOf1Bits {
    
    public int[] sortByBits(int[] arr) {
        Integer[] boxed = new Integer[arr.length];
        for (int i = 0; i < arr.length; i++) boxed[i] = arr[i];
        
        Arrays.sort(boxed, (a, b) -> {
            int ba = Integer.bitCount(a), bb = Integer.bitCount(b);
            return ba != bb ? ba - bb : a - b;
        });
        
        for (int i = 0; i < arr.length; i++) arr[i] = boxed[i];
        return arr;
    }
    
    public static void main(String[] args) {
        Problem31_SortIntegersByNumberOf1Bits sol = new Problem31_SortIntegersByNumberOf1Bits();
        
        System.out.println("Test 1: " + Arrays.toString(sol.sortByBits(new int[]{0,1,2,3,4,5,6,7,8})));
        // [0,1,2,4,8,3,5,6,7]
        
        System.out.println("Test 2: " + Arrays.toString(sol.sortByBits(new int[]{1024,512,256,128,64,32,16,8,4,2,1})));
        // [1,2,4,8,16,32,64,128,256,512,1024]
    }
}
