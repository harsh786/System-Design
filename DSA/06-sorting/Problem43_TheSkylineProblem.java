import java.util.*;

/**
 * Problem 43: The Skyline Problem
 * 
 * Given buildings [left, right, height], output the skyline contour.
 * 
 * Approach: Line sweep with max-heap. Create events at each building start/end.
 * At each x-coordinate, the max height determines the skyline.
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Resource utilization visualization - tracking peak concurrent usage
 * across overlapping allocations (like network bandwidth utilization graph).
 */
public class Problem43_TheSkylineProblem {
    
    public List<List<Integer>> getSkyline(int[][] buildings) {
        List<int[]> events = new ArrayList<>();
        for (int[] b : buildings) {
            events.add(new int[]{b[0], -b[2]}); // start: negative height
            events.add(new int[]{b[1], b[2]});  // end: positive height
        }
        
        // Sort by x; if same x, by height (starts before ends, taller starts first)
        events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        
        TreeMap<Integer, Integer> heights = new TreeMap<>(); // height -> count
        heights.put(0, 1);
        int prevMax = 0;
        List<List<Integer>> result = new ArrayList<>();
        
        for (int[] event : events) {
            if (event[1] < 0) {
                heights.merge(-event[1], 1, Integer::sum);
            } else {
                int cnt = heights.get(event[1]);
                if (cnt == 1) heights.remove(event[1]);
                else heights.put(event[1], cnt - 1);
            }
            
            int curMax = heights.lastKey();
            if (curMax != prevMax) {
                result.add(Arrays.asList(event[0], curMax));
                prevMax = curMax;
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem43_TheSkylineProblem sol = new Problem43_TheSkylineProblem();
        
        int[][] t1 = {{2,9,10},{3,7,15},{5,12,12},{15,20,10},{19,24,8}};
        System.out.println("Test 1: " + sol.getSkyline(t1));
        // [[2,10],[3,15],[7,12],[12,0],[15,10],[20,8],[24,0]]
        
        int[][] t2 = {{0,2,3},{2,5,3}};
        System.out.println("Test 2: " + sol.getSkyline(t2)); // [[0,3],[5,0]]
    }
}
