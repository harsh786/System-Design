import java.util.*;

public class Problem46_SubtractionGame {
    // Subtraction Game: Given set S of allowed moves. Compute Grundy values.
    // Period detection: Grundy values eventually become periodic.
    
    public int[] grundyValues(int n, int[] S) {
        int[] g = new int[n + 1];
        for (int i = 1; i <= n; i++) {
            Set<Integer> reach = new HashSet<>();
            for (int s : S) if (i >= s) reach.add(g[i - s]);
            int mex = 0;
            while (reach.contains(mex)) mex++;
            g[i] = mex;
        }
        return g;
    }
    
    // Detect period in Grundy sequence
    public int detectPeriod(int[] grundy) {
        // Try periods starting from some offset
        for (int p = 1; p <= grundy.length / 3; p++) {
            boolean periodic = true;
            for (int i = p; i < Math.min(3 * p, grundy.length); i++) {
                if (grundy[i] != grundy[i % p + p]) { periodic = false; break; }
            }
            if (periodic) return p;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        Problem46_SubtractionGame sol = new Problem46_SubtractionGame();
        int[] g = sol.grundyValues(20, new int[]{1, 3, 4});
        System.out.println("Grundy: " + Arrays.toString(g));
        // For S={1,3,4}: period is 7 with values [0,1,0,1,2,0,2]
    }
}
