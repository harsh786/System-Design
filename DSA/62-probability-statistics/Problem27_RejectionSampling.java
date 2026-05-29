import java.util.*;

public class Problem27_RejectionSampling {
    /* Sample from f(x) using uniform proposal over bounding box */
    private Random rand = new Random();

    // Sample from triangle distribution on [0,1] with pdf f(x)=2x
    public double sampleTriangle() {
        while (true) {
            double x = rand.nextDouble(); // proposal uniform [0,1]
            double u = rand.nextDouble() * 2; // uniform [0, max_f]
            if (u <= 2 * x) return x; // accept if under pdf
        }
    }

    public static void main(String[] args) {
        Problem27_RejectionSampling sol = new Problem27_RejectionSampling();
        double sum = 0;
        int n = 100000;
        for (int i = 0; i < n; i++) sum += sol.sampleTriangle();
        System.out.printf("Mean (expected 2/3): %.4f%n", sum / n);
    }
}
