import java.util.*;

public class Problem20_EqualRowAndColumnPairs {
    public int equalPairs(int[][] grid) {
        int n = grid.length, count = 0;
        Map<String, Integer> rowMap = new HashMap<>();
        for (int[] row : grid) rowMap.merge(Arrays.toString(row), 1, Integer::sum);
        for (int c = 0; c < n; c++) {
            int[] col = new int[n];
            for (int r = 0; r < n; r++) col[r] = grid[r][c];
            count += rowMap.getOrDefault(Arrays.toString(col), 0);
        }
        return count;
    }

    public static void main(String[] args) {
        Problem20_EqualRowAndColumnPairs sol = new Problem20_EqualRowAndColumnPairs();
        System.out.println(sol.equalPairs(new int[][]{{3,2,1},{1,7,6},{2,7,7}})); // 1
    }
}
