import java.util.*;

public class Problem34_GameOnTreeWinningState {
    // Game on Tree: Token at root. Move to child. Can't move = loses.
    // Grundy number of a node = XOR of (grundy(child) + 1) for all children.
    // Alternative: node is winning if any child is losing.
    
    List<List<Integer>> adj;
    
    public boolean isWinning(int n, int[][] edges, int root) {
        adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); }
        return dfs(root, -1);
    }
    
    private boolean dfs(int node, int parent) {
        // A position is winning if there exists at least one child that is a losing position
        for (int child : adj.get(node)) {
            if (child == parent) continue;
            if (!dfs(child, node)) return true; // found losing child -> current is winning
        }
        return false; // leaf or all children are winning -> current is losing
    }
    
    // Grundy approach for combining multiple tree games
    public int grundy(int node, int parent) {
        int g = 0;
        for (int child : adj.get(node)) {
            if (child == parent) continue;
            g ^= (grundy(child, node) + 1);
        }
        return g;
    }
    
    public static void main(String[] args) {
        Problem34_GameOnTreeWinningState sol = new Problem34_GameOnTreeWinningState();
        // Tree: 0-1, 0-2, 1-3, 1-4
        System.out.println(sol.isWinning(5, new int[][]{{0,1},{0,2},{1,3},{1,4}}, 0)); // true
    }
}
