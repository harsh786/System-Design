import java.util.*;

public class Problem04_ValidSquare {
    public static boolean validSquare(int[] p1, int[] p2, int[] p3, int[] p4) {
        Set<Integer> dists = new HashSet<>();
        int[][] pts = {p1, p2, p3, p4};
        List<Integer> all = new ArrayList<>();
        for (int i = 0; i < 4; i++) for (int j = i + 1; j < 4; j++) {
            int d = dist(pts[i], pts[j]);
            if (d == 0) return false;
            all.add(d);
            dists.add(d);
        }
        if (dists.size() != 2) return false;
        Collections.sort(all);
        return all.get(0).equals(all.get(3)) && all.get(4).equals(all.get(5));
    }
    static int dist(int[] a, int[] b) { return (a[0]-b[0])*(a[0]-b[0]) + (a[1]-b[1])*(a[1]-b[1]); }
    public static void main(String[] args) {
        System.out.println(validSquare(new int[]{0,0}, new int[]{1,1}, new int[]{1,0}, new int[]{0,1})); // true
    }
}
