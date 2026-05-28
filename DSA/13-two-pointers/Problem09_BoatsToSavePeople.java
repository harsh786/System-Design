/**
 * Problem 9: Boats to Save People
 * 
 * Each boat carries at most 2 people with weight limit. Minimize boats.
 * 
 * Approach: Sort, pair lightest with heaviest if possible.
 * Time: O(n log n), Space: O(1)
 * 
 * Production Analogy: Like bin-packing requests into server instances -
 * pairing small and large workloads to maximize utilization per instance.
 */
import java.util.Arrays;

public class Problem09_BoatsToSavePeople {
    public static int numRescueBoats(int[] people, int limit) {
        Arrays.sort(people);
        int left = 0, right = people.length - 1, boats = 0;
        while (left <= right) {
            if (people[left] + people[right] <= limit) left++;
            right--;
            boats++;
        }
        return boats;
    }

    public static void main(String[] args) {
        System.out.println(numRescueBoats(new int[]{1,2}, 3)); // 1
        System.out.println(numRescueBoats(new int[]{3,2,2,1}, 3)); // 3
        System.out.println(numRescueBoats(new int[]{3,5,3,4}, 5)); // 4
    }
}
