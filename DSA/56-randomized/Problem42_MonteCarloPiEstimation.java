import java.util.*;

public class Problem42_MonteCarloPiEstimation {
    public static double estimatePi(int samples) {
        Random rand = new Random();
        int inside = 0;
        for (int i = 0; i < samples; i++) {
            double x = rand.nextDouble(), y = rand.nextDouble();
            if (x*x + y*y <= 1) inside++;
        }
        return 4.0 * inside / samples;
    }

    public static void main(String[] args) {
        for (int n : new int[]{1000, 10000, 100000, 1000000})
            System.out.printf("n=%d: pi≈%.6f%n", n, estimatePi(n));
    }
}
