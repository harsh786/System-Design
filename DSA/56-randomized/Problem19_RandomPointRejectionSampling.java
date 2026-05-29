import java.util.*;

public class Problem19_RandomPointRejectionSampling {
    // Generate random point in circle using rejection sampling
    double radius, xc, yc;
    Random rand = new Random();

    public Problem19_RandomPointRejectionSampling(double r, double x, double y) {
        radius = r; xc = x; yc = y;
    }

    public double[] randPoint() {
        while (true) {
            double x = xc - radius + rand.nextDouble() * 2 * radius;
            double y = yc - radius + rand.nextDouble() * 2 * radius;
            if ((x-xc)*(x-xc) + (y-yc)*(y-yc) <= radius*radius)
                return new double[]{x, y};
        }
    }

    public static void main(String[] args) {
        Problem19_RandomPointRejectionSampling sol = new Problem19_RandomPointRejectionSampling(2.0, 0, 0);
        for (int i = 0; i < 5; i++) System.out.println(Arrays.toString(sol.randPoint()));
    }
}
