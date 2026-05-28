/**
 * Problem 41: Car Pooling (LeetCode 1094)
 *
 * Greedy Choice: Use difference array / sweep line to track passenger count at each stop.
 *
 * Time: O(n + max_stop), Space: O(max_stop)
 *
 * Production Analogy: Checking if server capacity is exceeded at any point given scheduled load changes.
 */
public class Problem41_CarPooling {
    
    public static boolean carPooling(int[][] trips, int capacity) {
        int[] diff = new int[1001];
        for (int[] t : trips) {
            diff[t[1]] += t[0];
            diff[t[2]] -= t[0];
        }
        int passengers = 0;
        for (int d : diff) {
            passengers += d;
            if (passengers > capacity) return false;
        }
        return true;
    }
    
    public static void main(String[] args) {
        System.out.println(carPooling(new int[][]{{2,1,5},{3,3,7}}, 4));   // false
        System.out.println(carPooling(new int[][]{{2,1,5},{3,3,7}}, 5));   // true
        System.out.println(carPooling(new int[][]{{2,1,5},{3,5,7}}, 3));   // true
    }
}
