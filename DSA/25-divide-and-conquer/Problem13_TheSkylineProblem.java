import java.util.*;

/**
 * Problem 13: The Skyline Problem (LeetCode 218)
 * 
 * D&C Approach:
 * - DIVIDE: Split buildings into two halves
 * - CONQUER: Compute skyline for each half
 * - COMBINE: Merge two skylines by scanning left-to-right, tracking max height
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy:
 * - Merging time-range overlapping events (resource scheduling)
 * - Computing aggregate bandwidth across overlapping network reservations
 * - Overlay rendering in graphics pipelines
 */
public class Problem13_TheSkylineProblem {

    public static List<List<Integer>> getSkyline(int[][] buildings) {
        if (buildings.length == 0) return new ArrayList<>();
        return divide(buildings, 0, buildings.length - 1);
    }

    private static List<List<Integer>> divide(int[][] buildings, int lo, int hi) {
        if (lo == hi) {
            List<List<Integer>> res = new ArrayList<>();
            res.add(Arrays.asList(buildings[lo][0], buildings[lo][2]));
            res.add(Arrays.asList(buildings[lo][1], 0));
            return res;
        }
        int mid = lo + (hi - lo) / 2;
        List<List<Integer>> left = divide(buildings, lo, mid);
        List<List<Integer>> right = divide(buildings, mid + 1, hi);
        return merge(left, right);
    }

    private static List<List<Integer>> merge(List<List<Integer>> left, List<List<Integer>> right) {
        List<List<Integer>> result = new ArrayList<>();
        int i = 0, j = 0, lh = 0, rh = 0, maxH = 0;
        
        while (i < left.size() && j < right.size()) {
            int x;
            if (left.get(i).get(0) < right.get(j).get(0)) {
                x = left.get(i).get(0); lh = left.get(i).get(1); i++;
            } else if (left.get(i).get(0) > right.get(j).get(0)) {
                x = right.get(j).get(0); rh = right.get(j).get(1); j++;
            } else {
                x = left.get(i).get(0);
                lh = left.get(i).get(1); rh = right.get(j).get(1);
                i++; j++;
            }
            int curMax = Math.max(lh, rh);
            if (curMax != maxH) {
                result.add(Arrays.asList(x, curMax));
                maxH = curMax;
            }
        }
        while (i < left.size()) { addIfDifferent(result, left.get(i)); i++; }
        while (j < right.size()) { addIfDifferent(result, right.get(j)); j++; }
        return result;
    }

    private static void addIfDifferent(List<List<Integer>> result, List<Integer> point) {
        if (result.isEmpty() || !result.get(result.size()-1).get(1).equals(point.get(1)))
            result.add(point);
    }

    public static void main(String[] args) {
        int[][] b1 = {{2,9,10},{3,7,15},{5,12,12},{15,20,10},{19,24,8}};
        System.out.println(getSkyline(b1));
        
        int[][] b2 = {{0,2,3},{2,5,3}};
        System.out.println(getSkyline(b2));
        
        int[][] b3 = {{1,2,1}};
        System.out.println(getSkyline(b3));
    }
}
