import java.util.*;
public class Problem32_OptimalBucketCount {
    /* Analyze optimal bucket count: sqrt(n) is often good for uniform data */
    public void analyze(int n) {
        System.out.println("n = "+n);
        System.out.println("sqrt(n) buckets: "+(int)Math.sqrt(n));
        System.out.println("n buckets (max parallelism): "+n);
        System.out.println("Optimal for uniform: n buckets gives O(n) expected");
        System.out.println("For k buckets: O(n + n*log(n/k) + k)");
    }
    public static void main(String[] args){ new Problem32_OptimalBucketCount().analyze(10000); }
}
