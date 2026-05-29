import java.util.*;

public class Problem06_ErectTheFenceConvexHull {
    public static int[][] outerTrees(int[][] trees) {
        int n = trees.length;
        if (n <= 3) return trees;
        Arrays.sort(trees, (a, b) -> a[0] == b[0] ? a[1] - b[1] : a[0] - b[0]);
        List<int[]> hull = new ArrayList<>();
        // Lower hull
        for (int[] p : trees) {
            while (hull.size() >= 2 && cross(hull.get(hull.size()-2), hull.get(hull.size()-1), p) < 0) hull.remove(hull.size()-1);
            hull.add(p);
        }
        // Upper hull
        int lower = hull.size();
        for (int i = n - 2; i >= 0; i--) {
            while (hull.size() > lower && cross(hull.get(hull.size()-2), hull.get(hull.size()-1), trees[i]) < 0) hull.remove(hull.size()-1);
            hull.add(trees[i]);
        }
        Set<String> seen = new HashSet<>();
        List<int[]> res = new ArrayList<>();
        for (int[] p : hull) { if (seen.add(p[0]+","+p[1])) res.add(p); }
        return res.toArray(new int[0][]);
    }
    static int cross(int[] o, int[] a, int[] b) { return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0]); }
    public static void main(String[] args) {
        int[][] res = outerTrees(new int[][]{{1,1},{2,2},{2,0},{2,4},{3,3},{4,2}});
        System.out.println(res.length);
    }
}
