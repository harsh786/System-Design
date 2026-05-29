/**
 * Problem: Spiral Matrix (LeetCode 54)
 * Approach: Layer-by-layer traversal with boundary shrinking
 * Complexity: O(m*n) time, O(1) space (excluding output)
 * Production Analogy: Sequential data scanning patterns in memory-mapped I/O
 */
import java.util.*;
public class Problem02_SpiralMatrix {
    public List<Integer> spiralOrder(int[][] matrix) {
        List<Integer> res = new ArrayList<>();
        int top=0, bottom=matrix.length-1, left=0, right=matrix[0].length-1;
        while (top<=bottom && left<=right) {
            for (int j=left; j<=right; j++) res.add(matrix[top][j]);
            top++;
            for (int i=top; i<=bottom; i++) res.add(matrix[i][right]);
            right--;
            if (top<=bottom) { for (int j=right; j>=left; j--) res.add(matrix[bottom][j]); bottom--; }
            if (left<=right) { for (int i=bottom; i>=top; i--) res.add(matrix[i][left]); left++; }
        }
        return res;
    }
    public static void main(String[] args) {
        System.out.println(new Problem02_SpiralMatrix().spiralOrder(new int[][]{{1,2,3},{4,5,6},{7,8,9}}));
    }
}
