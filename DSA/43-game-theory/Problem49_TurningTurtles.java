import java.util.*;

public class Problem49_TurningTurtles {
    // Turning Turtles: Row of coins. Flip rightmost coin (must go face-down) and optionally
    // flip any one coin to its left. Nim-value of face-up coin at position i is i.
    // XOR of positions of all face-up coins determines winner.
    
    public boolean firstPlayerWins(boolean[] coins) {
        int xor = 0;
        for (int i = 0; i < coins.length; i++) {
            if (coins[i]) xor ^= i;
        }
        return xor != 0;
    }
    
    // Find a winning move
    public int[] findWinningMove(boolean[] coins) {
        int xor = 0;
        for (int i = 0; i < coins.length; i++) if (coins[i]) xor ^= i;
        if (xor == 0) return null;
        
        // Find rightmost face-up coin to flip that helps
        for (int i = coins.length - 1; i >= 0; i--) {
            if (!coins[i]) continue;
            int newXor = xor ^ i; // flip coin at i (remove from XOR)
            if (newXor == 0) return new int[]{i, -1}; // just flip i
            // Find j < i to also flip
            for (int j = 0; j < i; j++) {
                int afterJ = coins[j] ? (newXor ^ j) : (newXor ^ j); // toggle j in set
                // Actually: if j is face-up, removing it: newXor ^ j; if face-down, adding it: newXor ^ j
                if ((newXor ^ j) == 0) return new int[]{i, j};
            }
        }
        return null;
    }
    
    public static void main(String[] args) {
        Problem49_TurningTurtles sol = new Problem49_TurningTurtles();
        boolean[] coins = {true, false, true, false, true}; // positions 0,2,4
        System.out.println("XOR = 0^2^4 = " + (0^2^4) + ", wins: " + sol.firstPlayerWins(coins));
    }
}
