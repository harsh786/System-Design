public class Problem35_PolygonAreaShoelaceFormula {
    public static double polygonArea(int[][] vertices) {
        int n = vertices.length;
        double area = 0;
        for (int i = 0; i < n; i++) {
            int j = (i + 1) % n;
            area += (long)vertices[i][0] * vertices[j][1];
            area -= (long)vertices[j][0] * vertices[i][1];
        }
        return Math.abs(area) / 2.0;
    }
    public static void main(String[] args) {
        System.out.println(polygonArea(new int[][]{{0,0},{4,0},{4,3},{0,3}})); // 12.0
        System.out.println(polygonArea(new int[][]{{0,0},{4,0},{4,3}})); // 6.0
    }
}
