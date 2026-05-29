public class Problem14_LargestTriangleArea {
    public static double largestTriangleArea(int[][] points) {
        double max = 0;
        for (int i = 0; i < points.length; i++)
            for (int j = i+1; j < points.length; j++)
                for (int k = j+1; k < points.length; k++)
                    max = Math.max(max, area(points[i], points[j], points[k]));
        return max;
    }
    static double area(int[] a, int[] b, int[] c) {
        return 0.5 * Math.abs((b[0]-a[0])*(c[1]-a[1]) - (c[0]-a[0])*(b[1]-a[1]));
    }
    public static void main(String[] args) {
        System.out.println(largestTriangleArea(new int[][]{{0,0},{0,1},{1,0},{0,2},{2,0}})); // 2.0
    }
}
