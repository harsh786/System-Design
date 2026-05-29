import java.util.*;

public class Problem01_NimGame {
    // Nim Game: You are playing a Nim Game with another player.
    // There is a heap of stones. You take turns removing 1-3 stones.
    // The one who removes the last stone wins. Return true if you can win.
    // Key insight: If n % 4 == 0, the first player loses.
    
    public boolean canWinNim(int n) {
        return n % 4 != 0;
    }
    
    // Generalized Nim: can remove 1..k stones
    public boolean canWinNimGeneralized(int n, int k) {
        return n % (k + 1) != 0;
    }
    
    public static void main(String[] args) {
        Problem01_NimGame sol = new Problem01_NimGame();
        System.out.println("n=4: " + sol.canWinNim(4));   // false
        System.out.println("n=5: " + sol.canWinNim(5));   // true
        System.out.println("n=8: " + sol.canWinNim(8));   // false
        System.out.println("n=7, k=3: " + sol.canWinNimGeneralized(7, 3)); // true
    }
}
