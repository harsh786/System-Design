/**
 * Problem: Find the Winner of the Circular Game (LeetCode 1823)
 * Approach: Josephus problem - iterative simulation
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Round-robin elimination in leader election protocols
 */
public class Problem27_FindWinnerCircularGame {
    public int findTheWinner(int n, int k) {
        int winner = 0;
        for (int i = 2; i <= n; i++) winner = (winner + k) % i;
        return winner + 1;
    }
    public static void main(String[] args) {
        System.out.println(new Problem27_FindWinnerCircularGame().findTheWinner(5, 2)); // 3
    }
}
