import java.util.*;

public class Problem50_GeometricHashing {
    // Spatial hashing for fast proximity queries
    static class SpatialHash {
        double cellSize;
        Map<Long, List<int[]>> grid = new HashMap<>();
        SpatialHash(double cellSize) { this.cellSize = cellSize; }
        long hash(int x, int y) {
            long cx = (long) Math.floor(x / cellSize), cy = (long) Math.floor(y / cellSize);
            return cx * 1_000_000_007L + cy;
        }
        void insert(int[] point) { grid.computeIfAbsent(hash(point[0], point[1]), k -> new ArrayList<>()).add(point); }
        List<int[]> queryNeighbors(int[] point, double radius) {
            List<int[]> result = new ArrayList<>();
            int cx = (int) Math.floor(point[0] / cellSize), cy = (int) Math.floor(point[1] / cellSize);
            int range = (int) Math.ceil(radius / cellSize);
            for (int dx = -range; dx <= range; dx++) for (int dy = -range; dy <= range; dy++) {
                long h = (long)(cx+dx) * 1_000_000_007L + (cy+dy);
                List<int[]> cell = grid.get(h);
                if (cell == null) continue;
                for (int[] p : cell) {
                    double d = Math.sqrt((long)(p[0]-point[0])*(p[0]-point[0]) + (long)(p[1]-point[1])*(p[1]-point[1]));
                    if (d <= radius) result.add(p);
                }
            }
            return result;
        }
    }
    public static void main(String[] args) {
        SpatialHash sh = new SpatialHash(10);
        int[][] points = {{5,5},{15,15},{25,25},{6,6},{100,100}};
        for (int[] p : points) sh.insert(p);
        List<int[]> neighbors = sh.queryNeighbors(new int[]{5,5}, 5);
        System.out.println("Neighbors within radius 5 of (5,5): " + neighbors.size()); // 2: (5,5) and (6,6)
        for (int[] p : neighbors) System.out.println(Arrays.toString(p));
    }
}
