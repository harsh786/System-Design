import java.util.*;

public class Problem37_StreamingAnomalyCounter {
    // Streaming Anomaly Detection: Flag values outside mean +/- k*stddev (using Welford's).
    
    long count = 0;
    double mean = 0, m2 = 0;
    double kSigma;
    
    public Problem37_StreamingAnomalyCounter() { this.kSigma = 3.0; }
    
    public void init(double kSigma) { this.kSigma = kSigma; }
    
    public boolean addAndCheck(double value) {
        boolean anomaly = false;
        if (count > 30) { // need enough data points
            double stddev = Math.sqrt(m2 / (count - 1));
            if (Math.abs(value - mean) > kSigma * stddev) anomaly = true;
        }
        count++;
        double delta = value - mean;
        mean += delta / count;
        m2 += delta * (value - mean);
        return anomaly;
    }
    
    public static void main(String[] args) {
        Problem37_StreamingAnomalyCounter sol = new Problem37_StreamingAnomalyCounter();
        sol.init(2.5);
        Random rand = new Random(0);
        for (int i = 0; i < 100; i++) {
            double val = rand.nextGaussian() * 2 + 10;
            if (i == 50) val = 100; // inject anomaly
            boolean anomaly = sol.addAndCheck(val);
            if (anomaly) System.out.println("ANOMALY at index " + i + ": " + val);
        }
    }
}
