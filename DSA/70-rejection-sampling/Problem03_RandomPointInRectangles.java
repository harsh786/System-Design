import java.util.*;

/**
 * Problem 3: Generate Random Point in Non-overlapping Rectangles (LeetCode 497)
 * 
 * Given a list of non-overlapping axis-aligned rectangles, randomly pick a point
 * inside the space covered by the rectangles. Each point must be equally likely.
 * 
 * Approach: Weighted selection + uniform point within rectangle
 * 1. Weight each rectangle by its area
 * 2. Select a rectangle with probability proportional to area
 * 3. Generate uniform random point within selected rectangle
 * 
 * Uses prefix sums + binary search for weighted selection (not rejection sampling,
 * but demonstrates the concept of "acceptance" within a target area).
 */
public class Problem03_RandomPointInRectangles {

    private int[][] rects;
    private int[] prefixArea;
    private int totalArea;
    private Random rand;

    public Problem03_RandomPointInRectangles(int[][] rects) {
        this.rects = rects;
        this.rand = new Random();
        this.prefixArea = new int[rects.length];
        
        // Calculate areas (number of integer points: (x2-x1+1)*(y2-y1+1))
        for (int i = 0; i < rects.length; i++) {
            int area = (rects[i][2] - rects[i][0] + 1) * (rects[i][3] - rects[i][1] + 1);
            prefixArea[i] = (i > 0 ? prefixArea[i-1] : 0) + area;
        }
        totalArea = prefixArea[rects.length - 1];
    }

    public int[] pick() {
        // Step 1: Choose rectangle with probability proportional to area
        int target = rand.nextInt(totalArea);
        int rectIdx = binarySearch(target);
        
        // Step 2: Uniform random point within chosen rectangle
        int[] r = rects[rectIdx];
        int x = r[0] + rand.nextInt(r[2] - r[0] + 1);
        int y = r[1] + rand.nextInt(r[3] - r[1] + 1);
        return new int[]{x, y};
    }

    private int binarySearch(int target) {
        int lo = 0, hi = prefixArea.length - 1;
        while (lo < hi) {
            int mid = (lo + hi) / 2;
            if (prefixArea[mid] <= target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    public static void main(String[] args) {
        // Two rectangles: small (1x1=1 area) and large (3x3=9 area)
        int[][] rects = {{-2,-2,-1,-1}, {1,0,3,2}};
        // First rect: 2x2=4 points, Second rect: 3x3=9 points
        
        Problem03_RandomPointInRectangles solution = new Problem03_RandomPointInRectangles(rects);
        
        int trials = 100000;
        int inFirst = 0;
        for (int i = 0; i < trials; i++) {
            int[] p = solution.pick();
            if (p[0] <= -1) inFirst++;
        }
        
        System.out.println("LeetCode 497: Random Point in Non-overlapping Rectangles");
        System.out.printf("Rect 1 (area 4): %.1f%% (expected %.1f%%)%n", 
            100.0*inFirst/trials, 100.0*4/13);
        System.out.printf("Rect 2 (area 9): %.1f%% (expected %.1f%%)%n", 
            100.0*(trials-inFirst)/trials, 100.0*9/13);
    }
}
