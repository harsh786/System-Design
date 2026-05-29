/**
 * Problem 36: Sort Integers by The Number of 1 Bits
 * Sort by popcount ascending, then by value ascending.
 * 
 * Approach: Custom comparator using Integer.bitCount.
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy: Prioritizing tasks by complexity (fewer active dependencies first).
 */
import java.util.*;

public class Problem36_SortIntegersByBits {
    public static int[] sortByBits(int[] arr) {
        Integer[] boxed = Arrays.stream(arr).boxed().toArray(Integer[]::new);
        Arrays.sort(boxed, (a, b) -> {
            int ca = Integer.bitCount(a), cb = Integer.bitCount(b);
            return ca != cb ? ca - cb : a - b;
        });
        return Arrays.stream(boxed).mapToInt(Integer::intValue).toArray();
    }

    public static void main(String[] args) {
        int[] r = sortByBits(new int[]{0,1,2,3,4,5,6,7,8});
        System.out.println(Arrays.toString(r));
        // [0,1,2,4,8,3,5,6,7]
    }
}
