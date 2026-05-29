import java.util.*;

public class Problem39_MinimumEnclosingCircle {
    static double[] minCircle(double[][] points) {
        List<double[]> P = new ArrayList<>(Arrays.asList(points));
        Collections.shuffle(P);
        double[] circle = {P.get(0)[0], P.get(0)[1], 0};
        for (int i = 1; i < P.size(); i++) {
            if (dist(circle, P.get(i)) > circle[2] + 1e-10) {
                circle = new double[]{P.get(i)[0], P.get(i)[1], 0};
                for (int j = 0; j < i; j++) {
                    if (dist(circle, P.get(j)) > circle[2] + 1e-10) {
                        circle = circleFrom2(P.get(i), P.get(j));
                        for (int k = 0; k < j; k++) {
                            if (dist(circle, P.get(k)) > circle[2] + 1e-10)
                                circle = circleFrom3(P.get(i), P.get(j), P.get(k));
                        }
                    }
                }
            }
        }
        return circle;
    }
    static double dist(double[] c, double[] p) { return Math.sqrt((c[0]-p[0])*(c[0]-p[0])+(c[1]-p[1])*(c[1]-p[1])); }
    static double[] circleFrom2(double[] a, double[] b) { return new double[]{(a[0]+b[0])/2, (a[1]+b[1])/2, dist(new double[]{(a[0]+b[0])/2,(a[1]+b[1])/2,0}, a)}; }
    static double[] circleFrom3(double[] a, double[] b, double[] c) {
        double ax=a[0],ay=a[1],bx=b[0],by=b[1],cx=c[0],cy=c[1];
        double D = 2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by));
        double ux = ((ax*ax+ay*ay)*(by-cy)+(bx*bx+by*by)*(cy-ay)+(cx*cx+cy*cy)*(ay-by))/D;
        double uy = ((ax*ax+ay*ay)*(cx-bx)+(bx*bx+by*by)*(ax-cx)+(cx*cx+cy*cy)*(bx-ax))/D;
        return new double[]{ux, uy, dist(new double[]{ux,uy,0}, a)};
    }
    public static void main(String[] args) {
        double[] c = minCircle(new double[][]{{0,0},{1,0},{0,1},{1,1}});
        System.out.printf("Center: (%.2f, %.2f), Radius: %.2f%n", c[0], c[1], c[2]);
    }
}
