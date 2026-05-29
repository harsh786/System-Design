import java.util.*;

public class Problem24_SegmentIntersectionDetection {
    /* Detect if any two horizontal/vertical segments intersect using sweep line */
    public boolean hasIntersection(int[][] segments) {
        // segments: [x1,y1,x2,y2] - either horizontal or vertical
        List<int[]> events = new ArrayList<>();
        for (int[] s : segments) {
            if (s[1] == s[3]) { // horizontal
                events.add(new int[]{s[0], 0, s[1], 0}); // left endpoint
                events.add(new int[]{s[2], 2, s[1], 0}); // right endpoint
            } else { // vertical
                events.add(new int[]{s[0], 1, Math.min(s[1],s[3]), Math.max(s[1],s[3])}); // vertical segment
            }
        }
        events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        TreeSet<Integer> activeY = new TreeSet<>();
        for (int[] e : events) {
            if (e[1] == 0) activeY.add(e[2]);
            else if (e[1] == 2) activeY.remove(e[2]);
            else { // vertical segment query
                if (!activeY.subSet(e[2], true, e[3], true).isEmpty()) return true;
            }
        }
        return false;
    }

    public static void main(String[] args) {
        Problem24_SegmentIntersectionDetection sol = new Problem24_SegmentIntersectionDetection();
        System.out.println(sol.hasIntersection(new int[][]{{1,3,5,3},{3,1,3,5}})); // true
        System.out.println(sol.hasIntersection(new int[][]{{1,1,5,1},{1,3,5,3}})); // false
    }
}
