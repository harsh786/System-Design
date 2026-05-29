/**
 * Problem 43: Rectangle Overlap
 * Return true if two axis-aligned rectangles overlap.
 *
 * Approach: Overlap exists iff x-ranges and y-ranges both overlap.
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like bounding-box intersection tests in spatial indexing
 * (R-trees) for geospatial queries.
 */
public class Problem43_RectangleOverlap {

    public static boolean isRectangleOverlap(int[] rec1, int[] rec2) {
        return rec1[0] < rec2[2] && rec2[0] < rec1[2] &&
               rec1[1] < rec2[3] && rec2[1] < rec1[3];
    }

    public static void main(String[] args) {
        System.out.println(isRectangleOverlap(new int[]{0,0,2,2}, new int[]{1,1,3,3})); // true
        System.out.println(isRectangleOverlap(new int[]{0,0,1,1}, new int[]{1,0,2,1})); // false (edge touch)
        System.out.println(isRectangleOverlap(new int[]{0,0,1,1}, new int[]{2,2,3,3})); // false
    }
}
