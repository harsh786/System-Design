package numbertheory;

/**
 * Problem 37: Arranging Coins (LeetCode 441)
 * 
 * Approach: Find k where k*(k+1)/2 <= n. Use quadratic formula or binary search.
 * 
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 */
public class Problem37_ArrangingCoins {
    
    public int arrangeCoins(int n) {
        return (int) (Math.sqrt(2.0 * n + 0.25) - 0.5);
    }
    
    public static void main(String[] args) {
        Problem37_ArrangingCoins sol = new Problem37_ArrangingCoins();
        System.out.println(sol.arrangeCoins(5));  // 2
        System.out.println(sol.arrangeCoins(8));  // 3
    }
}
