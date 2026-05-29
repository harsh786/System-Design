import java.util.*;

public class Problem50_ImportanceSampling {
    /*
     * Estimate E[f(x)] under target distribution p(x) using proposal q(x)
     * E_p[f(x)] = E_q[f(x) * p(x)/q(x)]
     * Example: estimate P(X > 3) for standard normal using shifted exponential proposal
     */
    public double estimateTailProb(int samples) {
        Random rand = new Random();
        double sum = 0, sumW = 0;
        double shift = 3.0, lambda = 1.0;
        for (int i = 0; i < samples; i++) {
            double x = shift - Math.log(1 - rand.nextDouble()) / lambda; // sample from shifted exp
            double px = Math.exp(-x*x/2) / Math.sqrt(2*Math.PI); // target: standard normal pdf
            double qx = lambda * Math.exp(-lambda*(x-shift)); // proposal: shifted exp pdf
            double w = px / qx; // importance weight
            sum += w; // f(x) = 1 (indicator x > 3, always true by construction)
            sumW += 1;
        }
        return sum / sumW;
    }

    public static void main(String[] args) {
        Problem50_ImportanceSampling sol = new Problem50_ImportanceSampling();
        System.out.printf("P(X>3) for N(0,1): %.6f (exact: 0.001350)%n", sol.estimateTailProb(1000000));
    }
}
