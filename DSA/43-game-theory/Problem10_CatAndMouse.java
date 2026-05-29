import java.util.*;

public class Problem10_CatAndMouse {
    // 913. Cat and Mouse: Graph game. Mouse at node 1, Cat at node 2. Mouse wins at 0.
    // Cat wins if catches mouse. Return 1 (mouse wins), 2 (cat wins), 0 (draw).
    
    public int catMouseGame(int[][] graph) {
        int n = graph.length;
        // state: (mouse_pos, cat_pos, turn) -> 0=draw,1=mouse wins,2=cat wins
        int[][][] result = new int[n][n][2]; // [mouse][cat][0=mouse turn,1=cat turn]
        int[][][] degree = new int[n][n][2];
        
        for (int m = 0; m < n; m++)
            for (int c = 0; c < n; c++) {
                degree[m][c][0] = graph[m].length;
                degree[m][c][1] = graph[c].length;
                for (int next : graph[c]) if (next == 0) degree[m][c][1]--;
            }
        
        Queue<int[]> queue = new LinkedList<>();
        for (int c = 1; c < n; c++) {
            for (int t = 0; t < 2; t++) {
                result[0][c][t] = 1; queue.add(new int[]{0, c, t});
                result[c][c][t] = 2; queue.add(new int[]{c, c, t});
            }
        }
        
        while (!queue.isEmpty()) {
            int[] state = queue.poll();
            int m = state[0], c = state[1], t = state[2];
            int res = result[m][c][t];
            int pt = 1 - t; // previous turn
            if (pt == 0) { // prev was mouse's turn
                for (int pm : graph[m]) {
                    if (result[pm][c][pt] != 0) continue;
                    if (res == 1) { result[pm][c][pt] = 1; queue.add(new int[]{pm, c, pt}); }
                    else { degree[pm][c][pt]--; if (degree[pm][c][pt] == 0) { result[pm][c][pt] = 2; queue.add(new int[]{pm, c, pt}); } }
                }
            } else { // prev was cat's turn
                for (int pc : graph[c]) {
                    if (pc == 0) continue;
                    if (result[m][pc][pt] != 0) continue;
                    if (res == 2) { result[m][pc][pt] = 2; queue.add(new int[]{m, pc, pt}); }
                    else { degree[m][pc][pt]--; if (degree[m][pc][pt] == 0) { result[m][pc][pt] = 1; queue.add(new int[]{m, pc, pt}); } }
                }
            }
        }
        return result[1][2][0];
    }
    
    public static void main(String[] args) {
        Problem10_CatAndMouse sol = new Problem10_CatAndMouse();
        int[][] graph = {{2,5},{3},{0,4,5},{1,4,5},{2,3},{0,2,3}};
        System.out.println(sol.catMouseGame(graph)); // 0
    }
}
