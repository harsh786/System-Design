import java.util.*;

public class Problem09_GenerateRandomPointInCircle {
    // Rejection sampling or sqrt method
    double radius, xCenter, yCenter;
    Random rand;

    public Problem09_GenerateRandomPointInCircle(double radius, double x, double y) {
        this.radius = radius; xCenter = x; yCenter = y;
        rand = new Random();
    }

    public double[] randPoint() {
        double r = radius * Math.sqrt(rand.nextDouble());
        double theta = rand.nextDouble() * 2 * Math.PI;
        return new double[]{xCenter + r * Math.cos(theta), yCenter + r * Math.sin(theta)};
    }

    public static void main(String[] args) {
        Problem09_GenerateRandomPointInCircle sol = new Problem09_GenerateRandomPointInCircle(1.0, 0.0, 0.0);
        for (int i = 0; i < 5; i++) System.out.println(Arrays.toString(sol.randPoint()));
    }
}
