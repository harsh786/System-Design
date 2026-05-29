import java.util.*;

public class Problem44_CoordinateCompression {
    public static int[][] compress(int[][] points) {
        int[] xs = Arrays.stream(points).mapToInt(p -> p[0]).distinct().sorted().toArray();
        int[] ys = Arrays.stream(points).mapToInt(p -> p[1]).distinct().sorted().toArray();
        Map<Integer, Integer> xMap = new HashMap<>(), yMap = new HashMap<>();
        for (int i = 0; i < xs.length; i++) xMap.put(xs[i], i);
        for (int i = 0; i < ys.length; i++) yMap.put(ys[i], i);
        int[][] result = new int[points.length][2];
        for (int i = 0; i < points.length; i++) {
            result[i][0] = xMap.get(points[i][0]);
            result[i][1] = yMap.get(points[i][1]);
        }
        return result;
    }
    public static void main(String[] args) {
        int[][] pts = {{100, 200}, {300, 400}, {100, 400}};
        int[][] compressed = compress(pts);
        for (int[] p : compressed) System.out.println(Arrays.toString(p));
        // [0,0], [1,1], [0,1]
    }
}
