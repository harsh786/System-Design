import java.util.*;

public class Problem35_MinimaxWithAlphaBetaPruning {
    // Minimax with Alpha-Beta Pruning for game tree evaluation.
    
    // Simulated game tree as array (complete binary tree of depth d)
    // leaves contain heuristic values
    
    int[] leaves;
    int leafIndex;
    
    public int alphaBeta(int depth, boolean isMax, int alpha, int beta) {
        if (depth == 0) return leaves[leafIndex++];
        
        if (isMax) {
            int val = Integer.MIN_VALUE;
            for (int i = 0; i < 2; i++) { // binary tree
                val = Math.max(val, alphaBeta(depth - 1, false, alpha, beta));
                alpha = Math.max(alpha, val);
                if (beta <= alpha) break; // prune
            }
            return val;
        } else {
            int val = Integer.MAX_VALUE;
            for (int i = 0; i < 2; i++) {
                val = Math.min(val, alphaBeta(depth - 1, true, alpha, beta));
                beta = Math.min(beta, val);
                if (beta <= alpha) break; // prune
            }
            return val;
        }
    }
    
    public static void main(String[] args) {
        Problem35_MinimaxWithAlphaBetaPruning sol = new Problem35_MinimaxWithAlphaBetaPruning();
        sol.leaves = new int[]{3, 5, 6, 9, 1, 2, 0, -1};
        sol.leafIndex = 0;
        int result = sol.alphaBeta(3, true, Integer.MIN_VALUE, Integer.MAX_VALUE);
        System.out.println("Optimal value: " + result); // 5
    }
}
