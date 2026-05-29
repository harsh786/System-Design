public class Problem47_ReflectionAcrossLine {
    // Reflect point (px, py) across line ax + by + c = 0
    public static double[] reflect(double px, double py, double a, double b, double c) {
        double d = (a*px + b*py + c) / (a*a + b*b);
        return new double[]{px - 2*a*d, py - 2*b*d};
    }
    // Reflect across y=x
    public static int[] reflectAcrossYEqualsX(int x, int y) { return new int[]{y, x}; }
    // Reflect across x-axis
    public static int[] reflectAcrossXAxis(int x, int y) { return new int[]{x, -y}; }
    // Reflect across y-axis
    public static int[] reflectAcrossYAxis(int x, int y) { return new int[]{-x, y}; }
    public static void main(String[] args) {
        // Reflect (1,2) across x-axis (line y=0, i.e., 0x+1y+0=0)
        double[] r = reflect(1, 2, 0, 1, 0);
        System.out.printf("(%.1f, %.1f)%n", r[0], r[1]); // (1.0, -2.0)
        // Reflect across line y=x (i.e., x-y=0, a=1,b=-1,c=0)
        r = reflect(3, 1, 1, -1, 0);
        System.out.printf("(%.1f, %.1f)%n", r[0], r[1]); // (1.0, 3.0)
    }
}
