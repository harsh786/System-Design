import java.util.*;

public class Problem31_MisereNim {
    // Misere Nim: Same as Nim but the player who takes the last stone LOSES.
    // Strategy: If all piles are 1, lose if odd number of piles.
    // Otherwise, same as normal Nim (XOR != 0 wins) but ensure opponent is left with odd piles of 1.
    
    public boolean firstPlayerWins(int[] piles) {
        int xor = 0;
        boolean allOnes = true;
        for (int p : piles) {
            xor ^= p;
            if (p > 1) allOnes = false;
        }
        if (allOnes) return piles.length % 2 == 0; // even piles of 1 = win (opponent takes last)
        return xor != 0;
    }
    
    public static void main(String[] args) {
        Problem31_MisereNim sol = new Problem31_MisereNim();
        System.out.println(sol.firstPlayerWins(new int[]{1,1,1}));  // false (3 piles of 1, odd -> lose)
        System.out.println(sol.firstPlayerWins(new int[]{1,1}));    // true
        System.out.println(sol.firstPlayerWins(new int[]{2,3}));    // false (xor=1!=0 but... actually true)
        System.out.println(sol.firstPlayerWins(new int[]{1,2,3}));  // true (xor=0? 1^2^3=0 -> false)
    }
}
