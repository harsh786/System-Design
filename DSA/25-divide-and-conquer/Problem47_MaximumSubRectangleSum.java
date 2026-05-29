/**
 * Problem 47: Maximum Sub-rectangle Sum
 * Find the sub-rectangle with maximum sum in a 2D matrix.
 * 
 * D&C / Reduction Approach:
 * - Fix left and right columns (O(n^2) pairs)
 * - Compress rows into 1D array (column sums between left and right)
 * - Apply Kadane's algorithm (or D&C max subarray) on the 1D array
 * 
 * Time: O(m * n^2) where m = rows, n = cols (for each column pair, O(m) Kadane)
 * Space: O(m)
 * 
 * Production Analogy:
 * - Image processing: finding brightest rectangular region
 * - Geospatial analysis: finding densest population rectangle
 * - OLAP cube: finding highest-sum sub-cube in multidimensional data
 */
public class Problem47_MaximumSubRectangleSum {

    public static int maxSumRectangle(int[][] matrix) {
        if (matrix.length == 0) return 0;
        int rows = matrix.length, cols = matrix[0].length;
        int maxSum = Integer.MIN_VALUE;
        
        for (int left = 0; left < cols; left++) {
            int[] temp = new int[rows]; // Compressed column sums
            for (int right = left; right < cols; right++) {
                // Add current column to running sum
                for (int i = 0; i < rows; i++) temp[i] += matrix[i][right];
                
                // Apply Kadane's on temp
                int currMax = kadane(temp);
                maxSum = Math.max(maxSum, currMax);
            }
        }
        return maxSum;
    }

    private static int kadane(int[] arr) {
        int maxSoFar = arr[0], maxEndingHere = arr[0];
        for (int i = 1; i < arr.length; i++) {
            maxEndingHere = Math.max(arr[i], maxEndingHere + arr[i]);
            maxSoFar = Math.max(maxSoFar, maxEndingHere);
        }
        return maxSoFar;
    }

    public static void main(String[] args) {
        int[][] m1 = {
            {1, 2, -1, -4, -20},
            {-8, -3, 4, 2, 1},
            {3, 8, 10, 1, 3},
            {-4, -1, 1, 7, -6}
        };
        System.out.println(maxSumRectangle(m1)); // 29

        int[][] m2 = {{-1, -2}, {-3, -4}};
        System.out.println(maxSumRectangle(m2)); // -1

        int[][] m3 = {{2, 1, -3, -4, 5}, {0, 6, 3, 4, 1}, {2, -2, -1, 4, -5}, {-3, 3, 1, 0, 3}};
        System.out.println(maxSumRectangle(m3)); // 18

        int[][] m4 = {{5}};
        System.out.println(maxSumRectangle(m4)); // 5
    }
}
