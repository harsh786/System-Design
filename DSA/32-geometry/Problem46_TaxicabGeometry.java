public class Problem46_TaxicabGeometry {
    // Taxicab (Manhattan) distance utilities
    public static int taxicabDist(int[] a, int[] b) { return Math.abs(a[0]-b[0]) + Math.abs(a[1]-b[1]); }
    // Taxicab circle: all points at distance r from center (diamond shape)
    public static int countPointsInTaxicabCircle(int[][] points, int[] center, int radius) {
        int count = 0;
        for (int[] p : points) if (taxicabDist(p, center) <= radius) count++;
        return count;
    }
    // Transform: rotate 45 degrees to convert Manhattan to Chebyshev
    // (x,y) -> (x+y, x-y), then Chebyshev dist = max(|x1-x2|, |y1-y2|)
    public static int chebyshevFromManhattan(int[] a, int[] b) {
        int ax = a[0]+a[1], ay = a[0]-a[1], bx = b[0]+b[1], by = b[0]-b[1];
        return Math.max(Math.abs(ax-bx), Math.abs(ay-by));
    }
    public static void main(String[] args) {
        System.out.println(taxicabDist(new int[]{0,0}, new int[]{3,4})); // 7
        System.out.println(chebyshevFromManhattan(new int[]{0,0}, new int[]{3,4})); // 7 (same as Manhattan)
        int[][] pts = {{0,0},{1,1},{2,2},{3,0},{0,3}};
        System.out.println(countPointsInTaxicabCircle(pts, new int[]{1,1}, 2)); // 3
    }
}
