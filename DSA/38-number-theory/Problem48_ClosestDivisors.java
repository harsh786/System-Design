package numbertheory;

/**
 * Problem 48: Closest Divisors (LeetCode 1362)
 * 
 * Approach: For num+1 and num+2, find pair of factors closest to sqrt.
 * 
 * Time Complexity: O(sqrt(num))
 * Space Complexity: O(1)
 */
public class Problem48_ClosestDivisors {
    
    public int[] closestDivisors(int num) {
        int[] best = {1, num + 1};
        for (int target : new int[]{num + 1, num + 2}) {
            for (int i = (int) Math.sqrt(target); i >= 1; i--) {
                if (target % i == 0) {
                    int j = target / i;
                    if (j - i < best[1] - best[0]) best = new int[]{i, j};
                    break;
                }
            }
        }
        return best;
    }
    
    public static void main(String[] args) {
        Problem48_ClosestDivisors sol = new Problem48_ClosestDivisors();
        int[] res = sol.closestDivisors(8);
        System.out.println(res[0] + " " + res[1]); // 3 3
    }
}
