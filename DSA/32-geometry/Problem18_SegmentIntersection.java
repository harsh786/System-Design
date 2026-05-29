public class Problem18_SegmentIntersection {
    public static boolean doIntersect(int[] p1, int[] q1, int[] p2, int[] q2) {
        int d1 = orientation(p1, q1, p2), d2 = orientation(p1, q1, q2);
        int d3 = orientation(p2, q2, p1), d4 = orientation(p2, q2, q1);
        if (d1 != d2 && d3 != d4) return true;
        if (d1 == 0 && onSegment(p1, p2, q1)) return true;
        if (d2 == 0 && onSegment(p1, q2, q1)) return true;
        if (d3 == 0 && onSegment(p2, p1, q2)) return true;
        if (d4 == 0 && onSegment(p2, q1, q2)) return true;
        return false;
    }
    static int orientation(int[] p, int[] q, int[] r) {
        int val = (q[1]-p[1])*(r[0]-q[0]) - (q[0]-p[0])*(r[1]-q[1]);
        return val == 0 ? 0 : val > 0 ? 1 : 2;
    }
    static boolean onSegment(int[] p, int[] q, int[] r) {
        return q[0] <= Math.max(p[0],r[0]) && q[0] >= Math.min(p[0],r[0]) && q[1] <= Math.max(p[1],r[1]) && q[1] >= Math.min(p[1],r[1]);
    }
    public static void main(String[] args) {
        System.out.println(doIntersect(new int[]{1,1}, new int[]{10,1}, new int[]{1,2}, new int[]{10,2})); // false
        System.out.println(doIntersect(new int[]{10,0}, new int[]{0,10}, new int[]{0,0}, new int[]{10,10})); // true
    }
}
