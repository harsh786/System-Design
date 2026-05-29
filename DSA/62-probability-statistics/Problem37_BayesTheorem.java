import java.util.*;

public class Problem37_BayesTheorem {
    /* P(Disease|Positive) given P(Positive|Disease), P(Disease), P(Positive|NoDis) */
    public double bayesPosterior(double sensitivity, double prevalence, double falsePositiveRate) {
        double pPositive = sensitivity * prevalence + falsePositiveRate * (1 - prevalence);
        return sensitivity * prevalence / pPositive;
    }

    public static void main(String[] args) {
        Problem37_BayesTheorem sol = new Problem37_BayesTheorem();
        // Test: sensitivity=0.99, prevalence=0.01, false positive rate=0.05
        System.out.printf("P(Disease|Positive): %.4f%n", sol.bayesPosterior(0.99, 0.01, 0.05));
    }
}
