import java.util.*;

public class Problem32_GameOfNimWithPiles {
    // Classic Nim with multiple piles. XOR of all pile sizes != 0 => first player wins.
    
    public boolean firstPlayerWins(int[] piles) {
        int xor = 0;
        for (int p : piles) xor ^= p;
        return xor != 0;
    }
    
    // Find a winning move: reduce pile i so that XOR becomes 0
    public int[] winningMove(int[] piles) {
        int xor = 0;
        for (int p : piles) xor ^= p;
        if (xor == 0) return null; // no winning move
        for (int i = 0; i < piles.length; i++) {
            int target = piles[i] ^ xor;
            if (target < piles[i]) {
                return new int[]{i, piles[i] - target}; // remove (piles[i]-target) from pile i
            }
        }
        return null;
    }
    
    public static void main(String[] args) {
        Problem32_GameOfNimWithPiles sol = new Problem32_GameOfNimWithPiles();
        int[] piles = {3, 4, 5};
        System.out.println("First player wins: " + sol.firstPlayerWins(piles));
        int[] move = sol.winningMove(piles);
        if (move != null) System.out.println("Remove " + move[1] + " from pile " + move[0]);
    }
}
