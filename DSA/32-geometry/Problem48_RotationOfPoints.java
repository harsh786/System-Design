public class Problem48_RotationOfPoints {
    // Rotate point (x,y) around origin by angle theta (radians)
    public static double[] rotate(double x, double y, double theta) {
        double cos = Math.cos(theta), sin = Math.sin(theta);
        return new double[]{x*cos - y*sin, x*sin + y*cos};
    }
    // Rotate around arbitrary center
    public static double[] rotateAround(double x, double y, double cx, double cy, double theta) {
        double[] r = rotate(x - cx, y - cy, theta);
        return new double[]{r[0] + cx, r[1] + cy};
    }
    // Rotate 90 degrees clockwise
    public static int[] rotate90CW(int x, int y) { return new int[]{y, -x}; }
    // Rotate 90 degrees counter-clockwise
    public static int[] rotate90CCW(int x, int y) { return new int[]{-y, x}; }
    public static void main(String[] args) {
        double[] r = rotate(1, 0, Math.PI / 2);
        System.out.printf("(%.4f, %.4f)%n", r[0], r[1]); // ~(0, 1)
        int[] r90 = rotate90CW(1, 0);
        System.out.println(r90[0] + "," + r90[1]); // 0,-1
    }
}
