import java.util.*;

/**
 * Problem 29: Rank Transform of a Matrix (LeetCode 1632)
 * 
 * Assign ranks to matrix elements. Same row/col elements with same value get same rank.
 * Rank respects ordering within row and column.
 * 
 * Approach: Process elements in sorted order. Union same-value elements in same row/col.
 * For each group of same-value elements, assign rank = max(row_max, col_max) + 1 for component.
 * 
 * Time: O(m*n * log(m*n) * α(m*n)), Space: O(m*n)
 * 
 * Production Analogy: Priority assignment in multi-dimensional scheduling -
 * tasks sharing resources must be ranked consistently.
 */
public class Problem29_RankTransformOfAMatrix {
    
    int[] parent, rank2;
    
    public int[][] matrixRankTransform(int[][] matrix) {
        int m = matrix.length, n = matrix[0].length;
        int[][] result = new int[m][n];
        
        // Group cells by value
        TreeMap<Integer, List<int[]>> valueMap = new TreeMap<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                valueMap.computeIfAbsent(matrix[i][j], k -> new ArrayList<>()).add(new int[]{i, j});
        
        int[] rowRank = new int[m]; // max rank in each row so far
        int[] colRank = new int[n]; // max rank in each col so far
        
        for (var entry : valueMap.entrySet()) {
            List<int[]> cells = entry.getValue();
            
            // Union cells in same row or col
            parent = new int[m + n]; rank2 = new int[m + n];
            for (int i = 0; i < m + n; i++) parent[i] = i;
            
            for (int[] cell : cells) {
                union(cell[0], cell[1] + m); // union row and col
            }
            
            // For each component, find max rank
            Map<Integer, Integer> compRank = new HashMap<>();
            for (int[] cell : cells) {
                int root = find(cell[0]);
                int curMax = Math.max(rowRank[cell[0]], colRank[cell[1]]);
                compRank.merge(root, curMax, Math::max);
            }
            
            // Assign ranks
            for (int[] cell : cells) {
                int root = find(cell[0]);
                int r = compRank.get(root) + 1;
                result[cell[0]][cell[1]] = r;
                rowRank[cell[0]] = Math.max(rowRank[cell[0]], r);
                colRank[cell[1]] = Math.max(colRank[cell[1]], r);
            }
        }
        return result;
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    private void union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return;
        if (rank2[px] < rank2[py]) parent[px] = py;
        else if (rank2[px] > rank2[py]) parent[py] = px;
        else { parent[py] = px; rank2[px]++; }
    }
    
    public static void main(String[] args) {
        Problem29_RankTransformOfAMatrix sol = new Problem29_RankTransformOfAMatrix();
        int[][] res = sol.matrixRankTransform(new int[][]{{1,2},{3,4}});
        System.out.println(Arrays.deepToString(res)); // [[1,2],[2,3]]
        
        res = sol.matrixRankTransform(new int[][]{{7,7},{7,7}});
        System.out.println(Arrays.deepToString(res)); // [[1,1],[1,1]]
    }
}
