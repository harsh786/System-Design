import java.util.*;

public class Problem33_ExponentialMovingAverage {
    // Exponential Moving Average (EMA): weighted toward recent values.
    // EMA_t = alpha * x_t + (1-alpha) * EMA_{t-1}
    
    double alpha;
    double ema;
    boolean initialized = false;
    
    public Problem33_ExponentialMovingAverage() { this.alpha = 0.3; }
    
    public void init(double alpha) { this.alpha = alpha; initialized = false; }
    
    public double add(double value) {
        if (!initialized) { ema = value; initialized = true; }
        else ema = alpha * value + (1 - alpha) * ema;
        return ema;
    }
    
    public double getEMA() { return ema; }
    
    public static void main(String[] args) {
        Problem33_ExponentialMovingAverage sol = new Problem33_ExponentialMovingAverage();
        sol.init(0.5);
        double[] data = {10, 12, 11, 15, 14, 13, 16};
        for (double d : data) System.out.printf("Input: %.1f, EMA: %.2f%n", d, sol.add(d));
    }
}
