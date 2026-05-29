import java.util.*;

public class Problem24_CatAndMouseII {
    // 1728. Cat and Mouse II: Grid game. Mouse moves up to mouseJump, Cat up to catJump.
    // Mouse wins if reaches food. Cat wins if catches mouse or mouse can't reach food in 1000 turns.
    
    static int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
    
    public boolean canMouseWin(String[] grid, int catJump, int mouseJump) {
        int rows = grid.length, cols = grid[0].length();
        int mR = 0, mC = 0, cR = 0, cC = 0;
        for (int i = 0; i < rows; i++)
            for (int j = 0; j < cols; j++) {
                if (grid[i].charAt(j) == 'M') { mR = i; mC = j; }
                if (grid[i].charAt(j) == 'C') { cR = i; cC = j; }
            }
        // State: (mousePos, catPos, turn) with max 128 turns
        Map<Long, Boolean> memo = new HashMap<>();
        return dfs(grid, mR, mC, cR, cC, 0, mouseJump, catJump, rows, cols, memo);
    }
    
    private boolean dfs(String[] grid, int mR, int mC, int cR, int cC, int turns,
                        int mJ, int cJ, int rows, int cols, Map<Long, Boolean> memo) {
        if (turns >= 128) return false;
        if (mR == cR && mC == cC) return false;
        if (grid[mR].charAt(mC) == 'F') return true;
        if (grid[cR].charAt(cC) == 'F') return false;
        
        long key = ((long)mR*cols+mC)*rows*cols*256 + ((long)cR*cols+cC)*256 + turns;
        if (memo.containsKey(key)) return memo.get(key);
        
        boolean mouseTurn = turns % 2 == 0;
        boolean result;
        if (mouseTurn) {
            result = false;
            outer: for (int[] d : dirs) {
                for (int k = 1; k <= mJ; k++) {
                    int nr = mR + d[0]*k, nc = mC + d[1]*k;
                    if (nr < 0 || nr >= rows || nc < 0 || nc >= cols || grid[nr].charAt(nc) == '#') break;
                    if (dfs(grid, nr, nc, cR, cC, turns+1, mJ, cJ, rows, cols, memo)) { result = true; break outer; }
                }
            }
            // mouse stays
            if (!result) result = dfs(grid, mR, mC, cR, cC, turns+1, mJ, cJ, rows, cols, memo);
        } else {
            result = true;
            for (int[] d : dirs) {
                for (int k = 1; k <= cJ; k++) {
                    int nr = cR + d[0]*k, nc = cC + d[1]*k;
                    if (nr < 0 || nr >= rows || nc < 0 || nc >= cols || grid[nr].charAt(nc) == '#') break;
                    if (!dfs(grid, mR, mC, nr, nc, turns+1, mJ, cJ, rows, cols, memo)) { result = false; break; }
                }
                if (!result) break;
            }
            // cat stays
            if (result) result = dfs(grid, mR, mC, cR, cC, turns+1, mJ, cJ, rows, cols, memo);
        }
        memo.put(key, result);
        return result;
    }
    
    public static void main(String[] args) {
        Problem24_CatAndMouseII sol = new Problem24_CatAndMouseII();
        System.out.println(sol.canMouseWin(new String[]{"####F","#C...","M...."}, 1, 2)); // true
    }
}
