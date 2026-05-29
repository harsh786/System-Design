import java.util.*;
public class Problem16_BucketSortMemoryAnalysis {
    /* Analyze memory usage of bucket sort */
    public void analyze(int n, int numBuckets) {
        System.out.println("Input size: "+n);
        System.out.println("Num buckets: "+numBuckets);
        System.out.println("Expected items/bucket: "+(double)n/numBuckets);
        System.out.println("Memory: O(n + k) = O("+n+" + "+numBuckets+") = O("+(n+numBuckets)+")");
        System.out.println("Time: O(n + k + n*log(n/k)) average for uniform distribution");
    }
    public static void main(String[] args){ new Problem16_BucketSortMemoryAnalysis().analyze(1000000, 1000); }
}
