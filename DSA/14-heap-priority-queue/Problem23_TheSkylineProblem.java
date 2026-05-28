import java.util.*;

/**
 * Problem 23: The Skyline Problem (LeetCode 218)
 * 
 * Approach: Process building edges (start/end). Use max-heap for active heights.
 * Record key points when max height changes.
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Network bandwidth allocation visualization - tracking maximum
 * resource usage across overlapping reservation windows.
 */
public class Problem23_TheSkylineProblem {
    
    public List<List<Integer>> getSkyline(int[][] buildings) {
        List<int[]> events = new ArrayList<>();
        for (int[] b : buildings) {
            events.add(new int[]{b[0], -b[2]}); // start: negative height
            events.add(new int[]{b[1], b[2]});  // end: positive height
        }
        events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        
        TreeMap<Integer, Integer> heights = new TreeMap<>(Collections.reverseOrder());
        heights.put(0, 1);
        int prevMax = 0;
        List<List<Integer>> result = new ArrayList<>();
        
        for (int[] e : events) {
            if (e[1] < 0) heights.merge(-e[1], 1, Integer::sum);
            else {
                int cnt = heights.get(e[1]);
                if (cnt == 1) heights.remove(e[1]);
                else heights.put(e[1], cnt - 1);
            }
            int currMax = heights.firstKey();
            if (currMax != prevMax) {
                result.add(Arrays.asList(e[0], currMax));
                prevMax = currMax;
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem23_TheSkylineProblem sol = new Problem23_TheSkylineProblem();
        int[][] buildings = {{2,9,10},{3,7,15},{5,12,12},{15,20,10},{19,24,8}};
        System.out.println(sol.getSkyline(buildings));
        // [[2,10],[3,15],[7,12],[12,0],[15,10],[20,8],[24,0]]
    }
}
