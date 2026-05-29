import java.util.*;

/**
 * Problem 50: Lucky Numbers in a Matrix
 * 
 * Find elements that are minimum in their row AND maximum in their column.
 *
 * Approach: Find min of each row, max of each column. Check intersections.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m + n)
 *
 * Production Analogy: Finding optimal resource allocation points - elements that are
 * cheapest in their category (row) but highest performing in their metric (column).
 * Like finding a server that's cheapest in its tier but has highest uptime in its region.
 */
public class Problem50_LuckyNumbersInAMatrix {

    public static List<Integer> luckyNumbers(int[][] matrix) {
        int m = matrix.length, n = matrix[0].length;
        int[] rowMin = new int[m], colMax = new int[n];
        Arrays.fill(rowMin, Integer.MAX_VALUE);
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                rowMin[i] = Math.min(rowMin[i], matrix[i][j]);
                colMax[j] = Math.max(colMax[j], matrix[i][j]);
            }
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (matrix[i][j] == rowMin[i] && matrix[i][j] == colMax[j])
                    result.add(matrix[i][j]);
        return result;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + luckyNumbers(new int[][]{{3,7,8},{9,11,13},{15,16,17}})); // [15]
        System.out.println("Test 2: " + luckyNumbers(new int[][]{{1,10,4,2},{9,3,8,7},{15,16,17,12}})); // [12]
        System.out.println("Test 3: " + luckyNumbers(new int[][]{{7,8},{1,2}})); // [7]
    }
}
