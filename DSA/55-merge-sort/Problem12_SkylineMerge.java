import java.util.*;

public class Problem12_SkylineMerge {
    static List<List<Integer>> getSkyline(int[][] buildings) {
        return divide(buildings, 0, buildings.length - 1);
    }
    
    static List<List<Integer>> divide(int[][] b, int lo, int hi) {
        if (lo > hi) return new ArrayList<>();
        if (lo == hi) { List<List<Integer>> r = new ArrayList<>(); r.add(Arrays.asList(b[lo][0], b[lo][2])); r.add(Arrays.asList(b[lo][1], 0)); return r; }
        int mid = (lo + hi) / 2;
        return mergeSkylines(divide(b, lo, mid), divide(b, mid + 1, hi));
    }
    
    static List<List<Integer>> mergeSkylines(List<List<Integer>> a, List<List<Integer>> b) {
        List<List<Integer>> res = new ArrayList<>();
        int i = 0, j = 0, ha = 0, hb = 0;
        while (i < a.size() && j < b.size()) {
            int x; int h;
            if (a.get(i).get(0) < b.get(j).get(0)) { x = a.get(i).get(0); ha = a.get(i).get(1); i++; }
            else if (a.get(i).get(0) > b.get(j).get(0)) { x = b.get(j).get(0); hb = b.get(j).get(1); j++; }
            else { x = a.get(i).get(0); ha = a.get(i).get(1); hb = b.get(j).get(1); i++; j++; }
            h = Math.max(ha, hb);
            if (res.isEmpty() || res.get(res.size()-1).get(1) != h) res.add(Arrays.asList(x, h));
        }
        while (i < a.size()) { if (res.isEmpty() || !res.get(res.size()-1).get(1).equals(a.get(i).get(1))) res.add(a.get(i)); i++; }
        while (j < b.size()) { if (res.isEmpty() || !res.get(res.size()-1).get(1).equals(b.get(j).get(1))) res.add(b.get(j)); j++; }
        return res;
    }
    
    public static void main(String[] args) {
        int[][] buildings = {{2,9,10},{3,7,15},{5,12,12}};
        System.out.println(getSkyline(buildings));
    }
}
