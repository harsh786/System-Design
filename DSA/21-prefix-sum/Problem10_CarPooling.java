/**
 * Problem 10: Car Pooling (LeetCode 1094)
 * 
 * Pattern: Difference array over locations; check if cumulative passengers <= capacity
 * 
 * Time: O(n + maxLocation), Space: O(maxLocation)
 * 
 * Production Analogy: Checking if a server's connection pool ever exceeds max_connections
 * given scheduled connection open/close events.
 */
public class Problem10_CarPooling {

    public static boolean carPooling(int[][] trips, int capacity) {
        int[] diff = new int[1001];
        for (int[] t : trips) {
            diff[t[1]] += t[0];
            diff[t[2]] -= t[0];
        }
        int curr = 0;
        for (int d : diff) {
            curr += d;
            if (curr > capacity) return false;
        }
        return true;
    }

    public static void main(String[] args) {
        assert carPooling(new int[][]{{2,1,5},{3,3,7}}, 4) == false;
        assert carPooling(new int[][]{{2,1,5},{3,3,7}}, 5) == true;
        assert carPooling(new int[][]{{2,1,5},{3,5,7}}, 3) == true;
        assert carPooling(new int[][]{{9,0,1},{3,3,7}}, 4) == false;
        System.out.println("All tests passed!");
    }
}
