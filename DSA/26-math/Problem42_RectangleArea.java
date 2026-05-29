/**
 * Problem 42: Rectangle Area
 * Find total area covered by two rectangles on a 2D plane.
 *
 * Approach: Area1 + Area2 - overlap. Overlap = max(0, overlapX) * max(0, overlapY).
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like computing union area in collision detection systems
 * or screen region invalidation in UI rendering.
 */
public class Problem42_RectangleArea {

    public static int computeArea(int ax1, int ay1, int ax2, int ay2,
                                   int bx1, int by1, int bx2, int by2) {
        int area1 = (ax2 - ax1) * (ay2 - ay1);
        int area2 = (bx2 - bx1) * (by2 - by1);

        int overlapX = Math.max(0, Math.min(ax2, bx2) - Math.max(ax1, bx1));
        int overlapY = Math.max(0, Math.min(ay2, by2) - Math.max(ay1, by1));

        return area1 + area2 - overlapX * overlapY;
    }

    public static void main(String[] args) {
        System.out.println(computeArea(-3, 0, 3, 4, 0, -1, 9, 2)); // 45
        System.out.println(computeArea(-2, -2, 2, 2, -2, -2, 2, 2)); // 16
    }
}
