import java.util.*;

public class Problem24_CoinWeighingProblem {
    // Find the counterfeit (lighter) coin using a balance
    static int counterfeit = 5;
    static int n = 9;
    
    // Returns: -1 (left lighter), 0 (equal), 1 (right lighter)
    static int weigh(int[] left, int[] right) {
        int lw = 0, rw = 0;
        for (int c : left) lw += (c == counterfeit) ? 9 : 10;
        for (int c : right) rw += (c == counterfeit) ? 9 : 10;
        return Integer.compare(rw, lw);
    }
    
    static int findCounterfeit() {
        // Ternary search: split into 3 groups
        int[] g1 = {0,1,2}, g2 = {3,4,5}, g3 = {6,7,8};
        int res = weigh(g1, g2);
        int[] suspect;
        if (res == -1) suspect = g1;
        else if (res == 1) suspect = g2;
        else suspect = g3;
        // Second weighing
        int r2 = weigh(new int[]{suspect[0]}, new int[]{suspect[1]});
        if (r2 == -1) return suspect[0];
        else if (r2 == 1) return suspect[1];
        else return suspect[2];
    }
    
    public static void main(String[] args) {
        System.out.println("Counterfeit coin: " + findCounterfeit()); // 5
    }
}
