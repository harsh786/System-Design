public class Problem40_CircleThroughThreePoints {
    public static double[] circumcircle(double x1, double y1, double x2, double y2, double x3, double y3) {
        double D = 2 * (x1*(y2-y3) + x2*(y3-y1) + x3*(y1-y2));
        double ux = ((x1*x1+y1*y1)*(y2-y3) + (x2*x2+y2*y2)*(y3-y1) + (x3*x3+y3*y3)*(y1-y2)) / D;
        double uy = ((x1*x1+y1*y1)*(x3-x2) + (x2*x2+y2*y2)*(x1-x3) + (x3*x3+y3*y3)*(x2-x1)) / D;
        double r = Math.sqrt((ux-x1)*(ux-x1) + (uy-y1)*(uy-y1));
        return new double[]{ux, uy, r};
    }
    public static void main(String[] args) {
        double[] c = circumcircle(0, 0, 1, 0, 0, 1);
        System.out.printf("Center: (%.2f, %.2f), Radius: %.2f%n", c[0], c[1], c[2]);
    }
}
