/**
 * Problem 12: Boats to Save People (LeetCode 881)
 *
 * Greedy Choice: Sort by weight. Pair heaviest with lightest if possible.
 *
 * Time: O(n log n), Space: O(1)
 *
 * Production Analogy: Bin-packing network packets into frames with size limit.
 */
import java.util.*;
public class Problem12_BoatsToSavePeople {
    
    public static int numRescueBoats(int[] people, int limit) {
        Arrays.sort(people);
        int lo = 0, hi = people.length - 1, boats = 0;
        while (lo <= hi) {
            if (people[lo] + people[hi] <= limit) lo++;
            hi--;
            boats++;
        }
        return boats;
    }
    
    public static void main(String[] args) {
        System.out.println(numRescueBoats(new int[]{1,2}, 3));       // 1
        System.out.println(numRescueBoats(new int[]{3,2,2,1}, 3));   // 3
        System.out.println(numRescueBoats(new int[]{3,5,3,4}, 5));   // 4
    }
}
