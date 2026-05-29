import java.util.*;

public class Problem16_MonteCarloPi {
    public double estimatePi(int samples) {
        Random rand = new Random();
        int inside = 0;
        for (int i = 0; i < samples; i++) {
            double x = rand.nextDouble(), y = rand.nextDouble();
            if (x*x + y*y <= 1.0) inside++;
        }
        return 4.0 * inside / samples;
    }

    public static void main(String[] args) {
        Problem16_MonteCarloPi sol = new Problem16_MonteCarloPi();
        System.out.println("Pi estimate (1M samples): " + sol.estimatePi(1000000));
    }
}
