public class Problem19_PointInPolygonRayCasting {
    public static boolean isInside(int[][] polygon, int[] point) {
        int n = polygon.length, count = 0;
        int px = point[0], py = point[1];
        for (int i = 0, j = n - 1; i < n; j = i++) {
            int xi = polygon[i][0], yi = polygon[i][1], xj = polygon[j][0], yj = polygon[j][1];
            if ((yi > py) != (yj > py) && px < (xj - xi) * (py - yi) / (double)(yj - yi) + xi) count++;
        }
        return count % 2 == 1;
    }
    public static void main(String[] args) {
        int[][] polygon = {{0,0},{10,0},{10,10},{0,10}};
        System.out.println(isInside(polygon, new int[]{5,5}));  // true
        System.out.println(isInside(polygon, new int[]{15,5})); // false
    }
}
