import java.util.*;

public class Problem11_RandomPointInCircle {
    private double radius, x_center, y_center;
    private Random rand = new Random();

    public Problem11_RandomPointInCircle(double radius, double x, double y) {
        this.radius = radius; x_center = x; y_center = y;
    }

    public double[] randPoint() {
        double r = radius * Math.sqrt(rand.nextDouble());
        double theta = 2 * Math.PI * rand.nextDouble();
        return new double[]{x_center + r * Math.cos(theta), y_center + r * Math.sin(theta)};
    }

    public static void main(String[] args) {
        Problem11_RandomPointInCircle sol = new Problem11_RandomPointInCircle(1.0, 0.0, 0.0);
        for (int i = 0; i < 5; i++) System.out.println(Arrays.toString(sol.randPoint()));
    }
}
