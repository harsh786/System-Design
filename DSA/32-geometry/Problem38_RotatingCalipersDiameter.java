import java.util.*;

public class Problem38_RotatingCalipersDiameter {
    // Find diameter (max distance between any two points) using convex hull + rotating calipers
    public static double diameter(int[][] points) {
        // First get convex hull
        Arrays.sort(points, (a, b) -> a[0] == b[0] ? a[1] - b[1] : a[0] - b[0]);
        List<int[]> hull = new ArrayList<>();
        for (int[] p : points) {
            while (hull.size() >= 2 && cross(hull.get(hull.size()-2), hull.get(hull.size()-1), p) <= 0) hull.remove(hull.size()-1);
            hull.add(p);
        }
        int lower = hull.size();
        for (int i = points.length - 2; i >= 0; i--) {
            while (hull.size() > lower && cross(hull.get(hull.size()-2), hull.get(hull.size()-1), points[i]) <= 0) hull.remove(hull.size()-1);
            hull.add(points[i]);
        }
        hull.remove(hull.size()-1);
        int n = hull.size();
        if (n <= 2) return n < 2 ? 0 : dist(hull.get(0), hull.get(1));
        // Rotating calipers
        int j = 1; double maxDist = 0;
        for (int i = 0; i < n; i++) {
            while (crossVal(hull.get(i), hull.get((i+1)%n), hull.get(j)) < crossVal(hull.get(i), hull.get((i+1)%n), hull.get((j+1)%n)))
                j = (j+1)%n;
            maxDist = Math.max(maxDist, Math.max(dist(hull.get(i), hull.get(j)), dist(hull.get((i+1)%n), hull.get(j))));
        }
        return maxDist;
    }
    static int cross(int[] o, int[] a, int[] b) { return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0]); }
    static double crossVal(int[] o, int[] a, int[] b) { return Math.abs((a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])); }
    static double dist(int[] a, int[] b) { return Math.sqrt((long)(a[0]-b[0])*(a[0]-b[0]) + (long)(a[1]-b[1])*(a[1]-b[1])); }
    public static void main(String[] args) {
        System.out.printf("%.2f%n", diameter(new int[][]{{0,0},{1,0},{0,1},{1,1},{0,2}}));
    }
}
