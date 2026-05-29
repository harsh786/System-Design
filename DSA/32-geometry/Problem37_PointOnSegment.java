public class Problem37_PointOnSegment {
    public static boolean onSegment(int[] p, int[] q, int[] r) {
        // Check if q lies on segment pr
        return q[0] <= Math.max(p[0], r[0]) && q[0] >= Math.min(p[0], r[0]) &&
               q[1] <= Math.max(p[1], r[1]) && q[1] >= Math.min(p[1], r[1]) &&
               (long)(q[1]-p[1])*(r[0]-p[0]) == (long)(r[1]-p[1])*(q[0]-p[0]);
    }
    public static void main(String[] args) {
        System.out.println(onSegment(new int[]{0,0}, new int[]{2,2}, new int[]{4,4})); // true
        System.out.println(onSegment(new int[]{0,0}, new int[]{2,3}, new int[]{4,4})); // false
    }
}
