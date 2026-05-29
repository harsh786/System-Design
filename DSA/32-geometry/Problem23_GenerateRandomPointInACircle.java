import java.util.*;

public class Problem23_GenerateRandomPointInACircle {
    double radius, xCenter, yCenter; Random rand = new Random();
    public Problem23_GenerateRandomPointInACircle(double radius, double x_center, double y_center) {
        this.radius = radius; xCenter = x_center; yCenter = y_center;
    }
    public double[] randPoint() {
        double r = Math.sqrt(rand.nextDouble()) * radius;
        double theta = rand.nextDouble() * 2 * Math.PI;
        return new double[]{xCenter + r * Math.cos(theta), yCenter + r * Math.sin(theta)};
    }
    public static void main(String[] args) {
        Problem23_GenerateRandomPointInACircle sol = new Problem23_GenerateRandomPointInACircle(1.0, 0.0, 0.0);
        System.out.println(Arrays.toString(sol.randPoint()));
    }
}
