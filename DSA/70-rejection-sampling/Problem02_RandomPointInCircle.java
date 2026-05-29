import java.util.*;

/**
 * Problem 2: Random Point in a Circle (LeetCode 478)
 * 
 * Generate a uniformly random point inside a circle of given radius and center.
 * 
 * Approach 1: Rejection sampling
 * - Generate point in bounding square [-r,r] x [-r,r]
 * - Accept if x^2 + y^2 <= r^2
 * - P(accept) = π*r^2 / (2r)^2 = π/4 ≈ 0.785
 * 
 * Approach 2: Polar coordinates (inverse transform)
 * - θ = uniform [0, 2π)
 * - r = R * sqrt(uniform [0,1])  ← sqrt is critical for uniform area distribution!
 * 
 * Common mistake: r = R * uniform gives more points near center (area ∝ r^2)
 */
public class Problem02_RandomPointInCircle {

    private double radius, xCenter, yCenter;
    private Random rand = new Random();

    public Problem02_RandomPointInCircle(double radius, double xCenter, double yCenter) {
        this.radius = radius;
        this.xCenter = xCenter;
        this.yCenter = yCenter;
    }

    // Rejection sampling approach
    public double[] randPointRejection() {
        while (true) {
            double x = rand.nextDouble() * 2 * radius - radius;
            double y = rand.nextDouble() * 2 * radius - radius;
            if (x * x + y * y <= radius * radius) {
                return new double[]{xCenter + x, yCenter + y};
            }
        }
    }

    // Polar coordinate approach (no rejection needed)
    public double[] randPointPolar() {
        double theta = rand.nextDouble() * 2 * Math.PI;
        double r = radius * Math.sqrt(rand.nextDouble()); // sqrt for uniform area!
        return new double[]{xCenter + r * Math.cos(theta), yCenter + r * Math.sin(theta)};
    }

    public static void main(String[] args) {
        Problem02_RandomPointInCircle circle = new Problem02_RandomPointInCircle(1.0, 0, 0);
        
        int trials = 100000;
        int innerCount = 0; // Points in inner half-radius circle
        
        // Verify uniformity: ratio of points in inner circle (r/2) should be 1/4
        for (int i = 0; i < trials; i++) {
            double[] p = circle.randPointPolar();
            if (p[0]*p[0] + p[1]*p[1] <= 0.25) innerCount++;
        }
        
        System.out.println("LeetCode 478: Random Point in a Circle");
        System.out.printf("Points in inner half-radius: %.2f%% (expected 25%%)%n", 
            100.0 * innerCount / trials);
        
        // Compare approaches
        long t1 = System.nanoTime();
        for (int i = 0; i < trials; i++) circle.randPointRejection();
        long time1 = System.nanoTime() - t1;
        
        long t2 = System.nanoTime();
        for (int i = 0; i < trials; i++) circle.randPointPolar();
        long time2 = System.nanoTime() - t2;
        
        System.out.printf("Rejection: %.2f ms, Polar: %.2f ms%n", time1/1e6, time2/1e6);
        System.out.println("Rejection acceptance rate: π/4 ≈ 78.5%");
    }
}
