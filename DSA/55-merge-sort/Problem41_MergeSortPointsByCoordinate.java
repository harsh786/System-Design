import java.util.*;

public class Problem41_MergeSortPointsByCoordinate {
    static int[][] sortPoints(int[][] points, boolean byX) {
        Arrays.sort(points, (a, b) -> byX ? a[0] - b[0] : a[1] - b[1]);
        return points;
    }
    
    public static void main(String[] args) {
        int[][] pts = {{3,4},{1,2},{5,1},{2,3}};
        sortPoints(pts, true);
        for (int[] p : pts) System.out.println(Arrays.toString(p));
    }
}
