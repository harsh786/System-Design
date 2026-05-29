import java.util.*;

/**
 * Problem 10: Rejection Sampling for Uniform Disk
 * 
 * Multiple methods to generate uniform points on/in geometric shapes,
 * highlighting when rejection sampling is the simplest correct approach.
 * 
 * Shapes covered:
 * 1. Unit disk (circle interior)
 * 2. Sphere surface
 * 3. Triangle
 * 4. Arbitrary polygon (via triangulation + weighted selection)
 */
public class Problem10_UniformDisk {

    static Random rand = new Random(42);

    // 1. Unit disk - rejection from square
    public static double[] uniformDisk() {
        while (true) {
            double x = 2 * rand.nextDouble() - 1;
            double y = 2 * rand.nextDouble() - 1;
            if (x*x + y*y <= 1) return new double[]{x, y};
        }
        // Acceptance: π/4 ≈ 78.5%
    }

    // 2. Unit sphere surface (3D) - rejection from cube
    public static double[] uniformSphereSurface() {
        while (true) {
            double x = 2*rand.nextDouble()-1;
            double y = 2*rand.nextDouble()-1;
            double z = 2*rand.nextDouble()-1;
            double r2 = x*x + y*y + z*z;
            if (r2 <= 1 && r2 > 0) {
                double r = Math.sqrt(r2);
                return new double[]{x/r, y/r, z/r};
            }
        }
        // Acceptance: (4π/3)/(2³) = π/6 ≈ 52.4%
    }

    // 3. Uniform in triangle with vertices A, B, C
    public static double[] uniformTriangle(double[] A, double[] B, double[] C) {
        double u = rand.nextDouble();
        double v = rand.nextDouble();
        // If u+v > 1, reflect to stay in triangle
        if (u + v > 1) { u = 1 - u; v = 1 - v; }
        double x = A[0] + u*(B[0]-A[0]) + v*(C[0]-A[0]);
        double y = A[1] + u*(B[1]-A[1]) + v*(C[1]-A[1]);
        return new double[]{x, y};
    }

    // 4. Uniform in annulus (ring) r_inner to r_outer - rejection
    public static double[] uniformAnnulus(double rInner, double rOuter) {
        while (true) {
            double x = (2*rand.nextDouble()-1) * rOuter;
            double y = (2*rand.nextDouble()-1) * rOuter;
            double r2 = x*x + y*y;
            if (r2 >= rInner*rInner && r2 <= rOuter*rOuter) {
                return new double[]{x, y};
            }
        }
    }

    public static void main(String[] args) {
        int trials = 1000000;
        
        System.out.println("Rejection Sampling for Geometric Shapes");
        System.out.println("========================================\n");
        
        // Disk: verify uniform distribution by checking quadrant balance
        int[] quadrants = new int[4];
        for (int i = 0; i < trials; i++) {
            double[] p = uniformDisk();
            int q = (p[0]>=0?0:1) + (p[1]>=0?0:2);
            quadrants[q]++;
        }
        System.out.println("Unit Disk - Quadrant distribution (expect 25% each):");
        for (int i = 0; i < 4; i++)
            System.out.printf("  Q%d: %.2f%%%n", i, 100.0*quadrants[i]/trials);
        
        // Sphere: verify by checking if points are actually on unit sphere
        System.out.println("\nSphere Surface - verifying |p| = 1:");
        double maxError = 0;
        for (int i = 0; i < 1000; i++) {
            double[] p = uniformSphereSurface();
            double norm = Math.sqrt(p[0]*p[0]+p[1]*p[1]+p[2]*p[2]);
            maxError = Math.max(maxError, Math.abs(norm - 1));
        }
        System.out.printf("  Max deviation from unit: %.2e%n", maxError);
        
        // Annulus: verify points are in ring
        double rIn = 0.5, rOut = 1.0;
        int validCount = 0;
        for (int i = 0; i < trials; i++) {
            double[] p = uniformAnnulus(rIn, rOut);
            double r = Math.sqrt(p[0]*p[0]+p[1]*p[1]);
            if (r >= rIn && r <= rOut) validCount++;
        }
        System.out.printf("%nAnnulus [%.1f, %.1f] - All valid: %b%n", rIn, rOut, validCount==trials);
        System.out.printf("  Acceptance rate: π(r²_out - r²_in)/(2*r_out)² = %.2f%%%n",
            100*Math.PI*(rOut*rOut-rIn*rIn)/(4*rOut*rOut));
    }
}
