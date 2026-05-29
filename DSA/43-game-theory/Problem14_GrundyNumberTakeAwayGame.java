import java.util.*;

public class Problem14_GrundyNumberTakeAwayGame {
    // Grundy Number (Sprague-Grundy): Take-away game with set of allowed moves.
    // Compute Grundy number for each position. Position loses iff Grundy == 0.
    
    public int[] computeGrundy(int n, int[] moves) {
        int[] grundy = new int[n + 1];
        for (int i = 1; i <= n; i++) {
            Set<Integer> reachable = new HashSet<>();
            for (int m : moves) {
                if (i - m >= 0) reachable.add(grundy[i - m]);
            }
            // mex: minimum excludant
            int mex = 0;
            while (reachable.contains(mex)) mex++;
            grundy[i] = mex;
        }
        return grundy;
    }
    
    public static void main(String[] args) {
        Problem14_GrundyNumberTakeAwayGame sol = new Problem14_GrundyNumberTakeAwayGame();
        int[] grundy = sol.computeGrundy(10, new int[]{1, 3, 4});
        System.out.println("Grundy numbers for moves {1,3,4}:");
        System.out.println(Arrays.toString(grundy));
        // Position is losing if grundy[pos] == 0
    }
}
