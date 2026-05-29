import java.util.*;

/**
 * Problem 29: Sort the Matrix Diagonally
 * 
 * Sort each diagonal of the matrix in ascending order.
 * 
 * Approach: Group elements by diagonal (same i-j value), sort each group, put back.
 * Time Complexity: O(m*n*log(min(m,n)))
 * Space Complexity: O(m*n)
 * 
 * Production Analogy: Sorting data within partitions/shards independently - 
 * each diagonal is an independent partition.
 */
public class Problem29_SortMatrixDiagonally {
    
    public int[][] diagonalSort(int[][] mat) {
        int m = mat.length, n = mat[0].length;
        Map<Integer, List<Integer>> diags = new HashMap<>();
        
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                diags.computeIfAbsent(i - j, k -> new ArrayList<>()).add(mat[i][j]);
            }
        }
        
        for (List<Integer> diag : diags.values()) Collections.sort(diag);
        
        Map<Integer, Integer> idx = new HashMap<>();
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                int key = i - j;
                int pos = idx.getOrDefault(key, 0);
                mat[i][j] = diags.get(key).get(pos);
                idx.put(key, pos + 1);
            }
        }
        return mat;
    }
    
    public static void main(String[] args) {
        Problem29_SortMatrixDiagonally sol = new Problem29_SortMatrixDiagonally();
        
        int[][] t1 = {{3,3,1,1},{2,2,1,2},{1,1,1,2}};
        int[][] r1 = sol.diagonalSort(t1);
        System.out.println("Test 1: " + Arrays.deepToString(r1));
        // [[1,1,1,1],[1,2,2,2],[1,2,3,3]]
        
        int[][] t2 = {{11,25,66,1,69,7},{23,55,17,45,15,52},{75,31,36,44,58,8},{22,27,33,25,68,4},{84,28,14,11,5,50}};
        System.out.println("Test 2: " + Arrays.deepToString(sol.diagonalSort(t2)));
    }
}
