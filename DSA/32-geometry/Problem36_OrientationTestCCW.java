public class Problem36_OrientationTestCCW {
    // Returns: 0 = collinear, 1 = clockwise, 2 = counterclockwise
    public static int orientation(int[] p, int[] q, int[] r) {
        int val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1]);
        if (val == 0) return 0;
        return val > 0 ? 1 : 2;
    }
    public static boolean isCCW(int[] p, int[] q, int[] r) { return orientation(p, q, r) == 2; }
    public static void main(String[] args) {
        System.out.println(orientation(new int[]{0,0}, new int[]{4,4}, new int[]{1,2})); // 2 (CCW)
        System.out.println(orientation(new int[]{0,0}, new int[]{4,4}, new int[]{1,1})); // 0 (collinear)
        System.out.println(isCCW(new int[]{0,0}, new int[]{4,4}, new int[]{1,2})); // true
    }
}
