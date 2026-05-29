import java.util.*;

public class Problem15_InteractiveMatrixRowSearch {
    static int[][] matrix = {{1,3,5},{7,9,11},{13,15,17}};
    static int query(int r, int c) { return matrix[r][c]; }
    
    static int[] search(int rows, int cols, int target) {
        int r = 0, c = cols - 1;
        while (r < rows && c >= 0) {
            int val = query(r, c);
            if (val == target) return new int[]{r, c};
            else if (val < target) r++;
            else c--;
        }
        return new int[]{-1, -1};
    }
    
    public static void main(String[] args) {
        System.out.println(Arrays.toString(search(3, 3, 9))); // [1,1]
    }
}
