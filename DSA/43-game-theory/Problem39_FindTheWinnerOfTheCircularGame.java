import java.util.*;

public class Problem39_FindTheWinnerOfTheCircularGame {
    // 1823. Find the Winner of the Circular Game (Josephus Problem).
    // n friends in circle, count k, eliminate. Return winner.
    
    public int findTheWinner(int n, int k) {
        int result = 0; // 0-indexed winner for 1 person
        for (int i = 2; i <= n; i++) {
            result = (result + k) % i;
        }
        return result + 1; // 1-indexed
    }
    
    public static void main(String[] args) {
        Problem39_FindTheWinnerOfTheCircularGame sol = new Problem39_FindTheWinnerOfTheCircularGame();
        System.out.println(sol.findTheWinner(5, 2)); // 3
        System.out.println(sol.findTheWinner(6, 5)); // 1
    }
}
