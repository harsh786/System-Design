public class Problem13_ConvexPolygonCheck {
    public static boolean isConvex(int[][] points) {
        int n = points.length; boolean pos = false, neg = false;
        for (int i = 0; i < n; i++) {
            int[] a = points[i], b = points[(i+1)%n], c = points[(i+2)%n];
            int cross = (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0]);
            if (cross > 0) pos = true;
            if (cross < 0) neg = true;
            if (pos && neg) return false;
        }
        return true;
    }
    public static void main(String[] args) {
        System.out.println(isConvex(new int[][]{{0,0},{1,0},{1,1},{0,1}})); // true
    }
}
