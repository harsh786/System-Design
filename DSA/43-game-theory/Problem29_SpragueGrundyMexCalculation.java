import java.util.*;

public class Problem29_SpragueGrundyMexCalculation {
    // Sprague-Grundy with MEX: Multiple independent games. XOR of Grundy values.
    // If XOR != 0, first player wins.
    
    public int mex(Set<Integer> set) {
        int m = 0;
        while (set.contains(m)) m++;
        return m;
    }
    
    // Example: multiple piles with allowed moves {1,2,3}
    public boolean canFirstPlayerWin(int[] piles, int[] moves) {
        int maxPile = 0;
        for (int p : piles) maxPile = Math.max(maxPile, p);
        int[] grundy = new int[maxPile + 1];
        for (int i = 1; i <= maxPile; i++) {
            Set<Integer> reachable = new HashSet<>();
            for (int m : moves) if (i - m >= 0) reachable.add(grundy[i - m]);
            grundy[i] = mex(reachable);
        }
        int xor = 0;
        for (int p : piles) xor ^= grundy[p];
        return xor != 0;
    }
    
    public static void main(String[] args) {
        Problem29_SpragueGrundyMexCalculation sol = new Problem29_SpragueGrundyMexCalculation();
        System.out.println(sol.canFirstPlayerWin(new int[]{3,4,5}, new int[]{1,2,3})); // true
        System.out.println(sol.canFirstPlayerWin(new int[]{4,4}, new int[]{1,2,3}));   // false (same grundy XOR=0)
    }
}
