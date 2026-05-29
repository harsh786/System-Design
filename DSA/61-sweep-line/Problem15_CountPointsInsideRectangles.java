import java.util.*;

public class Problem15_CountPointsInsideRectangles {
    public int[] countPoints(int[][] rectangles, int[][] points) {
        int[] res = new int[points.length];
        for (int i = 0; i < points.length; i++) {
            for (int[] r : rectangles) {
                if (points[i][0] >= r[0] && points[i][0] <= r[2] && points[i][1] >= r[1] && points[i][1] <= r[3])
                    res[i]++;
            }
        }
        return res;
    }

    public static void main(String[] args) {
        Problem15_CountPointsInsideRectangles sol = new Problem15_CountPointsInsideRectangles();
        System.out.println(Arrays.toString(sol.countPoints(new int[][]{{1,1,4,4},{2,2,5,5}}, new int[][]{{3,3},{1,1},{6,6}})));
    }
}
